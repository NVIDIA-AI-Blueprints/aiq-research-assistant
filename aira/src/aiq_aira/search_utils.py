# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import asyncio
import json
import aiohttp
import re
import xml.etree.ElementTree as ET
from typing import List
from langchain_openai import ChatOpenAI
from langchain_core.runnables import RunnableConfig
from aiq_aira.constants import ASYNC_TIMEOUT
from langgraph.types import StreamWriter
import logging
from langchain_core.utils.json import parse_json_markdown
from aiq_aira.schema import GeneratedQuery
from aiq_aira.prompts import relevancy_checker
from aiq_aira.tools import search_rag, search_tavily
from aiq_aira.utils import dummy, _escape_markdown
import html
import os
from textwrap import dedent

logger = logging.getLogger(__name__)
use_vast = os.getenv('USE_VAST_RAG', 'false').lower() == 'true'

async def check_relevancy(llm: ChatOpenAI, query: str, answer: str, writer: StreamWriter):
    """
    Checks if an answer is relevant to the query using the 'relevancy_checker' prompt, returning JSON
    like { "score": "yes" } or { "score": "no" }.
    """
    logger.info("CHECK RELEVANCY")    
    writer({"relevancy_checker": "\n Starting relevancy check \n"})
    processed_answer_for_display = html.escape(_escape_markdown(answer))

    try:
        async with asyncio.timeout(ASYNC_TIMEOUT):
            response = await llm.ainvoke(
                relevancy_checker.format(document=answer, query=query)
            )
            score = parse_json_markdown(response.content) # type: ignore 
            writer({"relevancy_checker": f"""

    ---
    Relevancy score: {score.get("score")}  
    Query: {query}
    Answer: {processed_answer_for_display}

    """})

            return score
    
    except asyncio.TimeoutError as e:
             writer({"relevancy_checker": f""" 
----------                
LLM time out evaluating relevancy. Query: {query} \n \n Answer: {processed_answer_for_display} 
----------
"""})   
    except Exception as e:
        writer({"relevancy_checker": f"""
---------
Error checking relevancy. Query: {query} \n \n Answer: {processed_answer_for_display} 
---------
"""})
        logger.debug(f"Error parsing relevancy JSON: {e}")

    # default if fails
    return {"score": "yes"}


async def perform_conversation_api_search(prompt: str, collection: str, writer: StreamWriter):
    """
    Performs conversation API search using the vast backend.
    """
    writer({"rag_answer": "\n Performing conversation API search \n"})
    logger.info("CONVERSATION API SEARCH")

    base_url = os.getenv("VAST_RAG_BASE_URL", "http://langchain-backend:8080")
    logger.info(f"Using VAST RAG base URL: {base_url}")
    # Create a new session for API calls
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
        try:
            # Step 1: Try to get authentication from AIQ context first
            from nat.builder.context import Context
            aiq_context = Context.get()
            headers = dict(aiq_context.metadata.headers) if aiq_context.metadata.headers else {}
            auth_header = headers.get("authorization") or headers.get("Authorization")

            headers = {"accept": "application/json", "Content-Type": "application/json"}

            # Check for existing auth header from context
            if auth_header:
                if not auth_header.startswith("Bearer "):
                    auth_header = f"Bearer {auth_header}"
                headers["Authorization"] = auth_header
                logger.info(f"Using authentication header from AIQ context: {auth_header}...")
            else:
                logger.error("No authentication header found in AIQ context, falling back to token-based authentication.")
                raise ValueError("No authentication header found in AIQ context")

            logger.info(f"Using headers: {headers}")
            # Create a new conversation
            create_conv_url = f"{base_url}/api/v1/conversations"
            logger.info(f"Creating conversation with URL: {create_conv_url}")
            async with session.post(
                create_conv_url,
                headers=headers,
                json={"title": f"Query: {prompt[:30]}...", "collection_name": collection},
            ) as response:
                response.raise_for_status()
                conversation_data = await response.json()
                conversation_id = conversation_data["id"]

            # Step 2: Send the prompt to the conversation
            prompt_url = f"{base_url}/api/v1/conversations/{conversation_id}/prompt"
            prompt_data = {
                "prompt": prompt,
                "extra_metadata_fields": ["confluence-page-url"],
            }

            async with asyncio.timeout(ASYNC_TIMEOUT):
                logger.info(f"Sending prompt to conversation with URL: {prompt_url}")
                async with session.post(
                    prompt_url, headers=headers, json=prompt_data
                ) as response:
                    response.raise_for_status()
                    result = await response.json()
                    logger.info(f"Received response from conversation API: {result}")
                    # Extract the content from the response
                    content = result.get("content", "")

                    # Format citations similar to search_rag
                    sources = result.get("sources", [])
                    citations_urls = set()
                    for source in sources:
                        logger.info(f"Processing source: {source}")
                        md = source.get("extra_metadata", '{}')
                        if md:
                            md = json.loads(md)
                            cit = md.get(
                                "confluence-page-url", ""
                            )
                        cit = source.get("doc_path", "")
                        citations_urls.add(cit)
                        urls = "\n".join(f"- {url}" for url in citations_urls)  
                        citations = dedent(
                            f"""

    ---
    QUERY:
    {prompt}

    ANSWER:
    {content}

    CITATION:
    {urls}

                            """
                        )
                        return (content, citations)

        except asyncio.TimeoutError:
            logger.exception("Error during conversation API search")
            writer(
                {
                    "rag_answer": dedent(f"""
                        -------------
                        Timeout getting conversation API answer for question {prompt}
                        """).strip()
                }
            )
            return ("Timeout fetching conversation API:", "")
        except Exception as e:
            logger.exception("Error during conversation API search")
            writer(
                {
                    "rag_answer": dedent(f"""
                        -------------
                        Error getting conversation API answer for question {prompt}: {str(e)}
                        """).strip()
                }
            )
            return (f"Error with conversation API: {e}", "")


async def fetch_query_results(
    rag_url: str,
    prompt: str,
    writer: StreamWriter,
    collection: str
):
    """
    Calls the search_rag tool in parallel for each prompt in parallel.
    Returns a list of tuples (answer, citations).
    """
    if use_vast:
        return await perform_conversation_api_search(prompt, collection, writer)

    async with aiohttp.ClientSession() as session:
        result =  await search_rag(session, rag_url, prompt, writer, collection)
        return result


def deduplicate_and_format_sources(
    sources: List[str],
    generated_answers: List[str],
    relevant_list: List[dict],
    web_results: List[str],
    queries: List[GeneratedQuery]
):
    """
    Convert RAG and fallback results into an XML structure <sources><source>...</source></sources>.
    Each <source> has <query> and <answer>.
    If 'relevant_list' says "score": "no", we fallback to 'web_results' if present.
    """
    logger.info("DEDUPLICATE RESULTS")
    root = ET.Element("sources")

    for q_json, src, relevant_info, fallback_ans, gen_ans in zip(
        queries, sources, relevant_list, web_results, generated_answers
    ):
        source_elem = ET.SubElement(root, "source")
        query_elem = ET.SubElement(source_elem, "query")
        query_elem.text = q_json.query
        answer_elem = ET.SubElement(source_elem, "answer")

        # If the RAG doc was relevant, use gen_ans; else fallback to 'fallback_ans'
        if relevant_info["score"] == "yes" or fallback_ans is None:
            answer_elem.text = gen_ans
        else:
            answer_elem.text = fallback_ans

    return ET.tostring(root, encoding="unicode")


async def process_single_query(
        query: str,
        config: RunnableConfig,
        writer: StreamWriter,
        collection,
        llm,
        search_web: bool
):
    """
    Process a single query:
      - Fetches RAG results.
      - Writes the RAG answer and citation.
      - Checks relevancy.
      - Optionally performs a web search.
      - Writes the web answer and citation.
    Returns a tuple of:
      (rag_answer, rag_citation, relevancy, web_answer, web_citation)
    """

    rag_url = config["configurable"].get("rag_url")  # type: ignore
    # Process RAG search
    rag_answer, rag_citation = await fetch_query_results(rag_url, query, writer, collection)  # type: ignore

    writer({"rag_answer": rag_citation}) # citation includes the answer

    # Check relevancy for this query's answer.
    relevancy = await check_relevancy(llm, query, rag_answer, writer)

    # Optionally run a web search if the query is not relevant.
    web_answer, web_citation = None, None
    if search_web:
        
        if relevancy["score"] == "no":
            result = await search_tavily(query, writer)
        else:
            result = await dummy()
        if result is not None:
        
            web_answers = [ 
                res['content'] if 'score' in res and float(res['score']) > 0.6 else "" 
                for res in result
            ]

            web_citations = [
                f"""
---
QUERY: 
{query}

ANSWER: 
{res['content']}

CITATION:
{res['url'].strip()}

"""
                if 'score' in res and float(res['score']) > 0.6 else "" 
                for res in result
            ]

            web_answer = "\n".join(web_answers)
            web_citation = "\n".join(web_citations)

            # guard against the case where no relevant answers are found
            if bool(re.fullmatch(r"\n*", web_answer)):
                web_answer = "No relevant result found in web search"
                web_citation = ""

        else:
            web_answer = "Web not searched since RAG provided relevant answer for query"
            web_citation = ""

        # citation includes the answer
        web_result_to_stream = web_citation if web_citation != "" else f"--- \n {web_answer} \n "
        
        writer({"web_answer": web_result_to_stream})

    return rag_answer, rag_citation, relevancy, web_answer, web_citation
