# SPDX-FileCopyrightText: Copyright (c) 2025, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
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
import html
import logging
import re
import xml.etree.ElementTree as ET
from typing import List

import aiohttp
from langchain_core.runnables import RunnableConfig
from langchain_core.utils.json import parse_json_markdown
from langchain_openai import ChatOpenAI
from langgraph.types import StreamWriter

from aiq_aira.constants import ASYNC_TIMEOUT
from aiq_aira.prompts import relevancy_checker
from aiq_aira.schema import GeneratedQuery
from aiq_aira.tools import search_rag
from aiq_aira.tools import search_tavily, search_eci
from aiq_aira.utils import _escape_markdown
from aiq_aira.utils import dummy

logger = logging.getLogger(__name__)


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
            response = await llm.ainvoke(relevancy_checker.format(document=answer, query=query))
            score = parse_json_markdown(response.content)
            writer({
                "relevancy_checker":
                    f""" =
    ---
    Relevancy score: {score.get("score")}  
    Query: {query}
    Answer: {processed_answer_for_display}
    """
            })

            return score

    except asyncio.TimeoutError as e:
        writer({
            "relevancy_checker":
                f""" 
----------                
LLM time out evaluating relevancy. Query: {query} \n \n Answer: {processed_answer_for_display} 
----------
"""
        })
    except Exception as e:
        writer({
            "relevancy_checker":
                f"""
---------
Error checking relevancy. Query: {query} \n \n Answer: {processed_answer_for_display} 
---------
"""
        })
        logger.debug(f"Error parsing relevancy JSON: {e}")

    # default if fails
    return {"score": "yes"}


async def fetch_query_results(rag_url: str, prompt: str, writer: StreamWriter, collection: str):
    """
    Calls the search_rag tool in parallel for each prompt in parallel.
    Returns a list of tuples (answer, citations).
    """
    async with aiohttp.ClientSession() as session:
        result = await search_rag(session, rag_url, prompt, writer, collection)
        return result



def deduplicate_and_format_sources(
    sources: List[str],
    generated_answers: List[str],
    queries: List[GeneratedQuery]
):
    """
    Convert RAG and fallback results into an XML structure <sources><source>...</source></sources>.
    Each <source> has <query> and <answer>.
    If 'relevant_list' says "score": "no", we fallback to 'web_results' if present.
    """
    logger.info("DEDUPLICATE RESULTS")
    root = ET.Element("sources")

    for q_json, src, gen_ans in zip(
        queries, sources, generated_answers
    ):
        source_elem = ET.SubElement(root, "source")
        query_elem = ET.SubElement(source_elem, "query")
        query_elem.text = q_json.query
        answer_elem = ET.SubElement(source_elem, "answer")
        answer_elem.text = gen_ans
        section_elem = ET.SubElement(source_elem, "section")
        section_elem.text = q_json.report_section

        citation_elem = ET.SubElement(source_elem, "citation")
        citation_elem.text = src

    logger.info(f"DEDUPLICATE RESULTS {ET.tostring(root, encoding='unicode')}")

    return ET.tostring(root, encoding="unicode")


async def process_single_query(
        query: str,
        config: RunnableConfig,
        writer: StreamWriter,
        collection,
        llm,
        search_web: bool, 
):
    """
    Process a single query:
      - RAG search
      - ECI search
      - Web search
      - Relevancy checks between each step
    """

    rag_url = config["configurable"].get("rag_url")

    rag_answer, rag_citation = await fetch_query_results(rag_url, query, writer, collection)
    
    writer({"rag_answer": rag_citation}) # citation includes the answer
    logger.info(f"RAG ANSWER: {rag_citation}")
    
    rag_relevancy = await check_relevancy(llm, query, rag_answer, writer)

    if rag_relevancy["score"] == "no":
        logger.info("RAG NOT RELEVANT, SEARCHING ECI")
        eci_answer, eci_citation = await search_eci(query, writer)
        writer({"eci_answer": eci_citation})
        logger.info(f"ECI ANSWER: {eci_citation}")
        eci_relevancy = await check_relevancy(llm, query, eci_answer, writer)


        if eci_relevancy["score"] == "no" and search_web:
            logger.info("ECI NOT RELEVANT, SEARCHING WEB")
            web_answer, web_citation = await search_tavily(query, writer)
            writer({"web_answer": web_citation})
            logger.info(f"WEB ANSWER: {eci_citation}")

    if rag_relevancy["score"] == "yes":
        return rag_answer, rag_citation
    
    if rag_relevancy["score"] == "no" and eci_relevancy["score"] == "yes":
        return eci_answer, eci_citation
    
    if rag_relevancy["score"] == "no" and eci_relevancy["score"] == "no" and search_web:
        return web_answer, web_citation
    
    return "", ""