
import aiohttp
import asyncio
import json
from urllib.parse import urljoin
from aiq_aira.constants import ASYNC_TIMEOUT, RAG_API_KEY, TAVILY_INCLUDE_DOMAINS
from langgraph.types import StreamWriter
from aiq_aira.utils import get_domain
from langchain_community.tools import TavilySearchResults
from urllib.parse import urljoin
import logging

logger = logging.getLogger(__name__)

async def search_rag(
    session: aiohttp.ClientSession,
    url: str,
    prompt: str,
    writer: StreamWriter,
    collection: str
):
    """
    Calls a RAG endpoint at `url`, passing `prompt` and referencing `collection`.
    Returns a tuple (content, citations).
    """ 
    writer({"rag_answer": "\n Performing RAG search \n"})
    logger.info("RAG SEARCH")
    headers = {
        "accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {RAG_API_KEY}"
    }
    data = {
        "messages": [
            {"role": "user", "content": prompt}
        ],
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
                                cited_docs = [
                                    (
                                        f"{c['document_name']}"
                                        if c['document_type'] == 'text'
                                        else ""
                                    )
                                    for c in citations_raw
                                ]
                                citations += ",".join(cited_docs)

                citations = f"""
---
QUERY: 
{prompt}

ANSWER: 
{content}

CITATIONS:
{citations}

""" 
                return (content, citations)
    except asyncio.TimeoutError:
        writer({"rag_answer": f"""
-------------
Timeout getting RAG answer for question {prompt} 
"""
                })
        return (f"Timeout fetching {req_url}:", "")        
    except Exception as e:
        writer({"rag_answer": f"""
-------------
Error getting RAG answer for question {prompt} 
"""
                })
        return (f"Error fetching {req_url}: {e}", "")

async def search_tavily(prompt: str, writer: StreamWriter):
    """
    Example of a fallback web search using Tavily Search Tool
    """
    logger.info("TAVILY SEARCH")
    writer({"web_answer": "\n Performing web search \n"})
    try: 
        all_results = []

        # explicitly query sets of domains
        if len(TAVILY_INCLUDE_DOMAINS) > 0:
            domain_chunks = [TAVILY_INCLUDE_DOMAINS[i:i+5] for i in range(0, len(TAVILY_INCLUDE_DOMAINS), 5)]
            for domain_chunk in domain_chunks:
                tool = TavilySearchResults(
                    max_results=2,  # optimization try more than one search result
                    search_depth="advanced",
                    include_answer=True,
                    include_raw_content=False,
                    include_images=False,
                    include_domains=domain_chunk,
                    # exclude_domains=[...], 
                )
                try:
                    async with asyncio.timeout(ASYNC_TIMEOUT):
                        chunk_results = await tool.ainvoke({"query": prompt})
                        all_results.extend(chunk_results)
                except asyncio.TimeoutError:
                    writer({"web_answer": f"""
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
                    writer({"web_answer": f"""
        --------
        The Tavily request for {prompt} to domains {domain_chunk} timed out
        --------                                
                    """
                    })
        
        return all_results
    
    except Exception as e:
        writer({"web_answer": f"""
--------
Error searching web for {prompt} using Tavily with {TAVILY_INCLUDE_DOMAINS}
--------                                
                """
                })
        logger.warning(f"TAVILY SEARCH FAILED {e}")
        return [{"url": "", "content": ""}]