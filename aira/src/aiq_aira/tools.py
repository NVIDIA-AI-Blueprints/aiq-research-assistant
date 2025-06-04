import aiohttp
import asyncio
import json
import logging
import os
from urllib.parse import urljoin
from langchain_community.tools import TavilySearchResults
from langgraph.types import StreamWriter
from aiq.cli.register_workflow import register_function
from pydantic import BaseModel, Field
from aiq.builder.builder import Builder
from aiq.builder.function_info import FunctionInfo
from aiq.data_models.function import FunctionBaseConfig
from aiq_aira.utils import format_citation, format_warning
from aiq_aira.constants import RAG_API_KEY, ASYNC_TIMEOUT


async def search_rag(
    session: aiohttp.ClientSession,
    url: str,
    prompt: str,
    collection: str
):
    """
    Calls a RAG endpoint at `url`, passing `prompt` and referencing `collection`.
    Returns a citation with query, answer and pdf name
    """ 
    logger = logging.getLogger(__name__)
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
                
                citations = format_citation(prompt, content, citations)

                return citations
    except asyncio.TimeoutError:
        logger.info(format_warning(f"Timeout getting RAG answer for question {prompt} "))
        return format_citation(prompt, f"Timeout fetching {req_url}", "")
    except Exception as e:
        logger.info(format_warning(f"Error getting RAG answer for question {prompt} "))
        return format_citation(prompt, f"Error finding answer in RAG: {e}","")


class RagSearchTool(FunctionBaseConfig, name="rag_search"):
    rag_url: str

@register_function(config_type=RagSearchTool)
async def rag_search(config: RagSearchTool, builder: Builder):
    """
    Calls a RAG endpoint at `url`, passing `prompt` and referencing `collection`.
    """

    async def _response_fn(prompt: str, collection: str) -> str:
        session = aiohttp.ClientSession()
        return await search_rag(
            session=session, 
            url=config.rag_url, 
            prompt=prompt, 
            collection=collection
        )

    yield FunctionInfo.from_fn(
        _response_fn,
        description="Search a RAG endpoint for answers to the prompt with information from the internal knowledge base.",
    )

async def search_tavily(
        prompt: str, 
        max_results: int,
        exclude_domains: list[str] | None = Field(default=None),
        include_domains: list[str] | None = Field(default=None)
):
    """
    Example of a web search using Tavily Search Tool
    Returns a citation with query, answer and url
    """
    logger = logging.getLogger(__name__)
    logger.info("TAVILY SEARCH")
    try: 
        all_results = []  
        
        tool = TavilySearchResults(
            max_results=max_results,  # optimization try more than one search result
            search_depth="advanced",
            include_answer=True,
            include_raw_content=False,
            include_images=False,
            exclude_domains=exclude_domains if exclude_domains else [],
            include_domains=include_domains if include_domains else []
        )
        try:
            async with asyncio.timeout(ASYNC_TIMEOUT):
                chunk_results = await tool.ainvoke({"query": prompt})
                all_results.extend(chunk_results)
        except asyncio.TimeoutError:
            logger.info(format_warning(f"The Tavily request for {prompt} timed out"))

        web_answers = [ 
            res['content'] if 'score' in res and float(res['score']) > 0.6 else "" 
            for res in all_results
        ]

        web_citations = [ 
            format_citation(prompt, res['content'], res['url'])
            if 'score' in res and float(res['score']) > 0.6 else "" 
            for res in all_results
        ]

        return "\n".join(web_citations)
    
    except Exception as e:
        logger.warning(f"TAVILY SEARCH FAILED {e}")
        return format_citation(prompt, f"Error finding answer in web search: {e}", "")


class TavilySearchTool(FunctionBaseConfig, name="tavily_search"):
    max_results: int
    exclude_domains: list[str] | None = Field(default=None)
    include_domains: list[str] | None = Field(default=None)

@register_function(config_type=TavilySearchTool)
async def tavily_search(config: TavilySearchTool, builder: Builder):
    """
    Calls a Tavily Search endpoint at `url`, passing `prompt`
    """

    async def _response_fn(prompt: str) -> str:
        return await search_tavily(
            prompt=prompt,
            max_results=config.max_results,
            exclude_domains=config.exclude_domains,
            include_domains=config.include_domains
        )

    yield FunctionInfo.from_fn(
        _response_fn,
        description="Perform a web search. Returns answers to the prompt with information from the web.",
    )