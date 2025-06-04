import asyncio
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
from aiq_aira.utils import dummy

logger = logging.getLogger(__name__)


async def check_relevancy(llm: ChatOpenAI, query: str, answer: str, writer: StreamWriter):
    """
    Checks if an answer is relevant to the query using the 'relevancy_checker' prompt, returning JSON
    like { "score": "yes" } or { "score": "no" }.
    """
    logger.info("CHECK RELEVANCY")    
    writer({"relevancy_checker": "\n Starting relevancy check \n"})
    try:
        async with asyncio.timeout(ASYNC_TIMEOUT):
            response = await llm.ainvoke(
                relevancy_checker.format(document=answer, query=query)
            )
            score = parse_json_markdown(response.content)
            writer({"relevancy_checker": f""" 
    ----------                
    Relevancy score: {score}  
    Query: {query}
    Answer: {answer}
    ----------
    """})

            return score
    
    except asyncio.TimeoutError as e:
             writer({"relevancy_checker": f""" 
----------                
LLM time out evaluating relevancy. Query: {query} \n \n Answer: {answer} 
----------
"""})   
    except Exception as e:
        writer({"relevancy_checker": f"""
---------
Error checking relevancy. Query: {query} \n \n Answer: {answer} 
---------
"""})
        logger.debug(f"Error parsing relevancy JSON: {e}")

    # default if fails
    return {"score": "yes"}


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
        section_elem = ET.SubElement(source_elem, "section")
        section_elem.text = q_json.report_section

        # If the RAG doc was relevant, use gen_ans; else fallback to 'fallback_ans'
        if relevant_info["score"] == "yes" or fallback_ans is None:
            answer_elem.text = gen_ans
        else:
            answer_elem.text = fallback_ans
        
        citation_elem = ET.SubElement(source_elem, "citation")
        citation_elem.text = src

        
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

    rag_url = config["configurable"].get("rag_url")
    # Process RAG search
    rag_answer, rag_citation = await fetch_query_results(rag_url, query, writer, collection)
    # For a single query, we take the first result.
    writer({"rag_answer": rag_citation})

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
ANSWER: 
{res['content']}

CITATION: 
{res['url']}
"""
                if 'score' in res and float(res['score']) > 0.6 else "" 
                for res in result
            ]


            web_answer = "\n".join(web_answers)
            web_answers_citations = "\n".join(web_citations)

            web_citation = f"""
---
QUERY: 
{query}
"""
            web_citation = web_citation + web_answers_citations
            
            # guard against the case where no relevant answers are found
            if bool(re.fullmatch(r"\n*", web_answer)):
                web_answer = "No relevant result found in web search"
                web_citation = ""

        else:
            web_answer = "Web not searched since RAG provided relevant answer for query"
            web_citation = ""

        web_result_to_stream = web_citation if web_citation != "" else f"--- \n {web_answer} \n ---"
        writer({"web_answer": web_result_to_stream})

    return rag_answer, rag_citation, relevancy, web_answer, web_citation