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
import json
import logging
import re
from urllib.parse import urljoin

import aiohttp
from langchain_community.tools import TavilySearchResults
from langgraph.types import StreamWriter

from aiq_aira.constants import ASYNC_TIMEOUT
from aiq_aira.constants import RAG_API_KEY
from aiq_aira.constants import TAVILY_INCLUDE_DOMAINS
from aiq_aira.functions.eci.content_search_response import ContentSearchResponse
from aiq_aira.functions.eci.content_search_response import SearchResult
from aiq_aira.functions.eci.content_search_response import SearchResultSnippet
from aiq_aira.functions.eci.eci_search_fn import eci_search_fn
from aiq_aira.utils import get_domain

logger = logging.getLogger(__name__)


async def search_rag(session: aiohttp.ClientSession, url: str, prompt: str, writer: StreamWriter, collection: str):
    """
    Calls a RAG endpoint at `url`, passing `prompt` and referencing `collection`.
    Returns a tuple (content, citations).
    """
    writer({"rag_answer": "\n Performing RAG search \n"})
    logger.info("RAG SEARCH")
    headers = {
        "accept": "application/json", "Content-Type": "application/json", "Authorization": f"Bearer {RAG_API_KEY}"
    }
    data = {
        "messages": [{
            "role": "user", "content": prompt
        }],
        "use_knowledge_base": True,
        "enable_citations": True,
        "collection_name": collection
    }
    req_url = urljoin(url, "generate")
    try:
        citations = ""
        async with asyncio.timeout(ASYNC_TIMEOUT):
            async with session.post(req_url, headers=headers, json=data) as response:
                logger.info(f"RAG SEARCH with {req_url} and {data}")
                response.raise_for_status()
                raw_result = await response.text()
                content = ""
                # Parse line-by-line, as RAG might stream
                for line in raw_result.splitlines():
                    if line.startswith("data: "):
                        event_data = line[6:]  # Remove "data: "
                        full_result = json.loads(event_data)
                        content += full_result["choices"][0]["message"]["content"]
                        if "citations" in full_result:
                            if "results" in full_result["citations"]:
                                citations_raw = full_result["citations"]["results"]
                                cited_docs = [(f"{c['document_name']}" if c['document_type'] == 'text' else "")
                                              for c in citations_raw]
                                citations += ",".join(cited_docs)
                citations = f"""
---
QUERY: 
{prompt}

ANSWER: 
{content}

CITATION:
{citations}

"""
                return (content, citations)
    except asyncio.TimeoutError:
        writer({"rag_answer": f"""
-------------
Timeout getting RAG answer for question {prompt} 
"""})
        return (f"Timeout fetching {req_url}:", "")
    except Exception as e:
        writer({"rag_answer": f"""
-------------
Error getting RAG answer for question {prompt} 
"""})
        return (f"Error fetching {req_url}: {e}", "")


async def search_tavily(prompt: str, writer: StreamWriter):
    """
    Web search using Tavily Search Tool
    Returns a tuple (content, citations).
    """
    logger.info("TAVILY SEARCH")
    writer({"web_answer": "\n Performing web search \n"})
    try:
        all_results = []

        # explicitly query sets of domains
        if len(TAVILY_INCLUDE_DOMAINS) > 0:
            domain_chunks = [TAVILY_INCLUDE_DOMAINS[i:i + 5] for i in range(0, len(TAVILY_INCLUDE_DOMAINS), 5)]
            for domain_chunk in domain_chunks:
                tool = TavilySearchResults(
                    max_results=2,  # optimization try more than one search result
                    search_depth="advanced",
                    include_answer=True,
                    include_raw_content=False,
                    include_images=False,
                    include_domains=domain_chunk,  # exclude_domains=[...],
                )
                try:
                    async with asyncio.timeout(ASYNC_TIMEOUT):
                        chunk_results = await tool.ainvoke({"query": prompt})
                        all_results.extend(chunk_results)
                except asyncio.TimeoutError:
                    writer({
                        "web_answer":
                            f"""
    --------
    The Tavily request for {prompt} to domains {domain_chunk} timed out
    --------                                
                    """
                    })

        # query at least a few different domains
        if len(TAVILY_INCLUDE_DOMAINS) == 0:
            seen_domains = []
            for i in range(2):
                tool = TavilySearchResults(
                    max_results=2,  # optimization try more than one search result
                    search_depth="advanced",
                    include_answer=True,
                    include_raw_content=False,
                    include_images=False,
                    exclude_domains=seen_domains,
                )
                try:
                    async with asyncio.timeout(ASYNC_TIMEOUT):
                        chunk_results = await tool.ainvoke({"query": prompt})
                        all_results.extend(chunk_results)
                        seen_domains.extend([get_domain(r["url"]) for r in chunk_results])
                except asyncio.TimeoutError:
                    writer({
                        "web_answer":
                            f"""
        --------
        The Tavily request for {prompt} to domains {domain_chunk} timed out
        --------                                
                    """
                    })
        
        # format results for deep researcher
        if all_results is not None:
        
            web_answers = [ 
                res['content'] if 'score' in res and float(res['score']) > 0.6 else "" 
                for res in all_results
            ]

            web_citations = [
                f"""
---
QUERY: 
{prompt}

ANSWER: 
{res['content']}

CITATION:
{res['url'].strip()}

"""
                if 'score' in res and float(res['score']) > 0.6 else "" 
                for res in all_results
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

        web_result_to_stream = web_citation if web_citation != "" else f"--- \n {web_answer} \n "
        writer({"web_answer": web_result_to_stream})

        return (web_answer, web_citation)
    
    except Exception as e:
        writer({
            "web_answer":
                f"""
--------
Error searching web for {prompt} using Tavily with {TAVILY_INCLUDE_DOMAINS}
--------                                
                """
        })
        logger.warning(f"TAVILY SEARCH FAILED {e}")
        return ("", "")
    

async def search_eci(prompt: str, writer: StreamWriter, eci_search_tool):
    """
    Search using ECI
    """
    
    logger.info(f"ECI SEARCH: {prompt}")

    try:
        # todo call eci search tool 
        content_search_response: ContentSearchResponse = await eci_search_tool.acall_invoke({"query": prompt})
        return documents_from_eci_response(prompt, content_search_response)

    except Exception as e:
        logger.error(f"ECI SEARCH FAILED {e}")
        writer({"eci_answer": f"""
--------
Failed ECI search for: {prompt} 
--------
        """
        })

    
    return ("", "")


def documents_from_eci_response(query, response: ContentSearchResponse):
    """
    Create a formatted string of documents from a Glean response
    """
    answers = []
    citations = []
    
    for result in response.results:
        snippet_text =""
        for snippet in result.snippets:
            if snippet.text: 
                snippet_text = snippet_text + "\n" + snippet.text

        document_answer = result.title + "\n" + snippet_text
        document_citation = format_citation(query, document_answer, result.url)
        answers.append(document_answer)
        citations.append(document_citation)
    
    return "\n".join(answers), "\n".join(citations)


def format_citation(query, answer, urls):
    """ Combine query, answer, and tools into a formatted source string """
    return f"""
---
QUERY: 
{query}

ANSWER: 
{answer}

CITATION:
{urls}

"""
