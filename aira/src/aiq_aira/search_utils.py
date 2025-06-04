import xml.etree.ElementTree as ET
from typing import List
from langchain_core.runnables import RunnableConfig
from langgraph.types import StreamWriter
import logging
from langchain_core.utils.json import parse_json_markdown
from aiq_aira.schema import GeneratedQuery
from aiq_aira.utils import format_citation, log_both
from aiq_aira.prompts import search_agent_instructions
from langchain_core.messages import HumanMessage

logger = logging.getLogger(__name__)

def deduplicate_and_format_sources(
    sources: List[str],
    generated_answers: List[str],
    queries: List[GeneratedQuery]
):
    """
    Convert search agent results into an XML structure <sources><source>...</source></sources>.
    Each <source> has <query> and <answer>.
    """
    logger.info("FORMATTING RESULTS")
    root = ET.Element("sources")

    for q_json, src, gen_ans in zip(
        queries, sources, generated_answers
    ):
        source_elem = ET.SubElement(root, "source")
        query_elem = ET.SubElement(source_elem, "query")
        query_elem.text = q_json.query
        answer_elem = ET.SubElement(source_elem, "answer")
        section_elem = ET.SubElement(source_elem, "section")
        section_elem.text = q_json.report_section
        answer_elem.text = gen_ans
        citation_elem = ET.SubElement(source_elem, "citation")
        citation_elem.text = src

        
    return ET.tostring(root, encoding="unicode")


async def process_single_query(
        query: str,
        config: RunnableConfig,
        writer: StreamWriter,
        collection,
):
    """
    Uses an agent to call tools for a single query.
    The agent returns a tuple of (answers, citations)
    Where answers and citations are concatenated strings of answers and citations
    """

    search_agent = config["configurable"].get("search_agent")
    log_both(f"Agent searching for: {query}", writer, "search_agent")
    messages = [
        HumanMessage(
            content=search_agent_instructions.format(
                prompt=query, 
                collection=collection
            )
        ),
    ]

    # Convert messages to string format
    messages_str = "\n".join([f"{msg.type}: {msg.content}" for msg in messages])
    response = await search_agent.ainvoke({"input_message": messages_str})
    
    
    try:
        parsed_response = parse_json_markdown(response)
    except Exception as e:
        log_both(f"Error parsing agent response for {query}: {e}", writer, "search_agent")
        return ("No answer found", format_citation(query=query, answer="No answer found", citations="No answer found"))

    answer = parsed_response.get("answer")
    citations = parsed_response.get("citation")
    formatted_citation = format_citation(
        query=query,
        answer=answer,
        citations="".join([
            f" \n \n *{citation.get("tool_name")}* \n ``` \n {citation.get("tool_response")} \n  *Origin*: {citation.get("url")} \n ``` \n \n"
            for citation in citations
        ])
    )

    log_both(formatted_citation, writer, "search_agent")

    return (answer, formatted_citation)