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
import logging
import xml.etree.ElementTree as ET
import re
from langchain_core.runnables import RunnableConfig
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.utils.json import parse_json_markdown
from langchain_core.stores import InMemoryByteStore
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.types import StreamWriter
from aiq_aira.schema import  GeneratedQuery

from aiq_aira.schema import AIRAState, Section, Sections
from aiq_aira.prompts import (
    query_writer_instructions,
    reflection_instructions,
    section_writer_instructions,
    intro_writer,
)


from aiq_aira.utils import async_gen, format_sources, update_system_prompt
from aiq_aira.constants import ASYNC_TIMEOUT

from aiq_aira.search_utils import process_single_query, deduplicate_and_format_sources
from aiq_aira.report_gen_utils import summarize_report

logger = logging.getLogger(__name__)
store = InMemoryByteStore()

async def generate_query(state: AIRAState, config: RunnableConfig, writer: StreamWriter):
    """
    Node for generating a research plan as a list of queries. 
    Takes in a topic and desired report organization. 
    Returns the list of query objects. 
    """
    logger.info("GENERATE QUERY")
    writer({"generating_questions": "\n Generating queries \n"}) # send something to initialize the UI so the timeout shows

    # Generate a query
    llm = config["configurable"].get("llm")
    number_of_queries = config["configurable"].get("number_of_queries")
    report_organization = config["configurable"].get("report_organization")
    topic = config["configurable"].get("topic")

    system_prompt = ""
    system_prompt = update_system_prompt(system_prompt, llm)

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system", system_prompt
            ),
            (
                "human", "{input}"
            ),
        ]
    )
    chain = prompt | llm

    input = {
        "topic": topic,
        "report_organization": report_organization,
        "number_of_queries": number_of_queries,
        "input": query_writer_instructions.format(topic=topic, report_organization=report_organization, number_of_queries=number_of_queries)
    }

    answer_agg = ""
    stop = False

    try: 
        async with asyncio.timeout(ASYNC_TIMEOUT):
            async for chunk in chain.astream(input, stream_usage=True):
                answer_agg += chunk.content
                if "</think>" in chunk.content:
                    stop = True
                if not stop:
                    writer({"generating_questions": chunk.content})
    except asyncio.TimeoutError as e: 
        writer({"generating_questions": " \n \n ---------------- \n \n Timeout error from reasoning LLM, please try again"})
        queries = []
        return {"queries": queries}

    # Split to get the final JSON after </think>
    splitted = answer_agg.split("</think>")
    if len(splitted) < 2:
        writer({"generating_questions": " \n \n ---------------- \n \n Timeout error from reasoning LLM, please try again"})
        logger.info(f"Error processing query response. No </think> tag. Response: {answer_agg}")
        queries = []
        return {"queries": queries}

    json_str = splitted[1].strip()
    try:
        queries = parse_json_markdown(json_str)
    except Exception as e:
        logger.error(f"Error parsing queries as JSON: {e}")
        queries = []

    return {"queries": queries}


async def web_research(
        state: AIRAState,
        config: RunnableConfig,
        writer: StreamWriter
):
    """
    Node for performing research based on the queries returned by generate_query.
    Research is performed deterministically by running RAG (and optionally a web search) on each query.
    The function extracts the queries from the state, processes each one via process_single_query,
    and finally formats the sources into an aggregated XML structure.
    A separate list of source citations is also maintained, tracking the query, answer, and sources for each query.
    """

    logger.info("STARTING WEB RESEARCH")
    llm = config["configurable"].get("llm")
    writer_llm = config["configurable"].get("writer_llm")
    search_web = config["configurable"].get("search_web")
    collection = config["configurable"].get("collection")
    report_structure = config["configurable"].get("report_organization")
    topic = config["configurable"].get("topic")
    global_source_counter = state.source_counter

    # Determine the queries and state queries based on the type of state.
    # If the state is a list of queries, use them directly.
    queries = [q.query for q in state.queries]
    state_queries = state.queries
    existing_citations =  state.citations

    # Process each query concurrently.
    results = await asyncio.gather(*[
        process_single_query(query, config, writer, collection, llm, search_web)
        for query in queries
    ])

    # Unpack results.
    generated_answers = [result[0] for result in results]
    citations = [result[1] if result[1] is not None else "" for result in results]
    relevancy_list = [result[2] for result in results]
    web_results = [result[3] for result in results]
    citations_web = [result[4] if result[4] is not None else "" for result in results]


    all_citations = []
    for idx, citation in enumerate(citations):
        if relevancy_list[idx]["score"] == "yes":
            all_citations.append(citation)
        if relevancy_list[idx]["score"] != "yes" and citations_web[idx] not in ["N/A", ""]:
            all_citations.append(citations_web[idx])
        if relevancy_list[idx]["score"] != "yes" and citations_web[idx] in ["N/A", ""]:
            all_citations.append(f"""
---
QUERY:
{queries[idx]}

ANSWER:
No relevant answer found in sources

""")

    numbered_citations = []
    for citation in all_citations:
        numbered_citation = re.sub(r'QUERY:', f'SOURCE {global_source_counter} QUERY:', citation)
        global_source_counter += 1
        numbered_citations.append(numbered_citation)
    
    citation_str = "\n".join(numbered_citations)

    if existing_citations:
        citation_str = existing_citations + "\n" + citation_str

    # Format the sources (producing a combined XML <sources> structure).
    logger.info("Deduplicating lengths:")
    logger.info(f"numbered_citations: {len(numbered_citations)}")
    logger.info(f"generated_answers: {len(generated_answers)}")
    logger.info(f"relevancy_list: {len(relevancy_list)}")
    logger.info(f"web_results: {len(web_results)}")
    logger.info(f"state_queries: {len(state_queries)}")
   
    search_str = deduplicate_and_format_sources(
        numbered_citations, generated_answers, relevancy_list, web_results, state_queries
    )

    # Create a dictionary to track unique sections by name
    unique_sections = {}
    for query in state.queries:
        section_name = query.report_section
        if section_name not in unique_sections:
            unique_sections[section_name] = Section(
                name=section_name,
                description="",
                plan="",
                research=False,
                content=""
            )
    
    # Convert dictionary values to list
    sections = list(unique_sections.values())
    return {"research_results": [search_str], "sections": sections, "queries": state.queries, "filled_sections": state.filled_sections, "citations": citation_str, "source_counter": global_source_counter}


async def write_section(section: Section, context: str, writer_llm: ChatOpenAI):
    """ Write a section of the report """
    
    logger.info(f"--- \n\n Writing Section \n \n {section.name} \n \n")
    
    # Parse the XML context
    root = ET.fromstring(context)
    
    # Create a new root for filtered sources
    filtered_root = ET.Element("sources")
    
    # Filter sources to only include those matching the current section
    for source in root.findall("source"):
        section_elem = source.find("section")
        if section_elem is not None and section_elem.text == section.name:
            filtered_root.append(source)
    
    # Convert filtered XML back to string
    filtered_context = ET.tostring(filtered_root, encoding="unicode")
    
    # Extract source numbers from citations
    source_numbers = set()
    for source in filtered_root.findall("source"):
        citation = source.find("citation")
        if citation is not None and citation.text:
            # Find all occurrences of "SOURCE X" where X is a number
            matches = re.findall(r'SOURCE\s+(\d+)', citation.text)
            source_numbers.update(int(match) for match in matches)
    
    # Convert to sorted list for consistent ordering
    source_numbers_in_context = sorted(source_numbers)
    
    # Format system instructions with filtered context
    system_instructions = section_writer_instructions.format(
        section_topic=section.name, 
        context=filtered_context,
        possible_citation_numbers=source_numbers_in_context
    )
    

    # Generate section  
    section_content = writer_llm.invoke([SystemMessage(content=system_instructions)]+[HumanMessage(content="Generate a report section based on the provided sources.")])
    
    # Write the updated section to completed sections
    return section_content.content


async def write_report(
        source: str,
        sections: Sections,
        writer_llm: ChatOpenAI,
) -> str:
    """
    Summarizes or extends an existing summary with new_source using the correct prompt.
    Returns the updated summary as a string.
    """
    # Decide which prompt to use
    logger.info("WRITING SECTIONS")

    tasks = [write_section(section, source, writer_llm) for section in sections]
    results = []
    batch_size = 2
    for i in range(0, len(tasks), batch_size):
        batch = tasks[i:i + batch_size]
        res = await asyncio.gather(*batch)
        results.extend(res)    
        
    # Return the final updated summary
    return results


async def summarize_sources(
        state: AIRAState,
        config: RunnableConfig,
        writer: StreamWriter
):
    """
    Node for summarizing or extending an existing summary. Takes the web research report and writes a report draft.
    """
    logger.info("SUMMARIZE")
    writer_llm = config["configurable"].get("writer_llm")
    report_organization = config["configurable"].get("report_organization")

    # The most recent web research
    most_recent_web_research = state.research_results[-1]
    existing_report = state.filled_sections
    sections = state.sections
    
    # -- Call the helper function here --
    writer({"summarize_sources": "Summarizing sources"})
    updated_report = await write_report(
        source=most_recent_web_research,
        sections =sections,
        writer_llm=writer_llm
    )

    # we call this here to update the UI, we dont stream the section writing since it happens in parallel 
    writer({"summarize_sources": updated_report})

    if len(existing_report) and len(updated_report) > 2:
        for elem in updated_report[1:-1]:
            existing_report.insert(-1, elem)
    else:
        existing_report.extend(updated_report)

    current_report = "\n\n".join(existing_report)

    writer({"running_summary": current_report})
    return {"current_report": current_report, "filled_sections": existing_report, "queries": state.queries, "citations": state.citations}


async def check_final_summary(
    state: AIRAState
):
    queries = state.queries
    if len(queries) and "Reflection-based query" in queries[0].rationale:
        return "finalize_summary"
    return "reflect_on_summary"


async def reflect_on_summary(state: AIRAState, config: RunnableConfig, writer: StreamWriter):
    """
    Node for reflecting on the summary to find knowledge gaps. 
    Identified gaps are added as new queries.
    Number of new queries is determined by the num_reflections parameter.
    For each new query, the node performs web research and report extension.
    The extended report and additional citations are added to the state.
    """
    logger.info("REFLECTING")
    llm = config["configurable"].get("llm")
    report_organization = config["configurable"].get("report_organization")
    search_web = config["configurable"].get("search_web")
    collection = config["configurable"].get("collection")
    num_reflections = config["configurable"].get("num_reflections")

    logger.info(f"REFLECTING {num_reflections} TIMES")

    generated_queries = []

    for i in range(num_reflections):
        input = {
            "input": reflection_instructions.format(report_organization=report_organization, topic=config["configurable"].get("topic"), current_report=state.current_report)

        }
        system_prompt = ""
        system_prompt = update_system_prompt(system_prompt, llm)

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system", system_prompt
                ),
                (
                    "human", "Using report organization as a guide identify a knowledge gap and generate a follow-up web search query based on our existing knowledge. \n \n {input}"
                ),
            ]
        )
        chain = prompt | llm

        writer({"reflect_on_summary": "\n Starting reflection \n"})
        async for i in async_gen(1):
            result = ""
            stop = False
            async for chunk in chain.astream(input, stream_usage=True):
                result = result + chunk.content
                if chunk.content == "</think>":
                    stop = True
                if not stop:
                    writer({"reflect_on_summary": chunk.content})

        splitted = result.split("</think>")
        if len(splitted) < 2:
            # If we can't parse anything, just fallback
            writer({"running_summary": state.current_report})
            return {"current_report": state.current_report}

        reflection_json = splitted[1].strip()
        try:
            reflection_obj = parse_json_markdown(reflection_json)
            gen_query = GeneratedQuery(
                query=reflection_obj["query"] if "query" in reflection_obj else str(reflection_obj),
                report_section=reflection_obj["report_section"] if "query" in reflection_obj else str(reflection_obj),
                rationale="Reflection-based query"
            )

        except Exception as e:
            logger.warning(f"Error parsing reflection JSON: {e}")
            reflection_obj = reflection_json
            gen_query = GeneratedQuery(
                query=reflection_obj,
                report_section=reflection_obj,
                rationale="Reflection-based query"
            )        
        generated_queries.append(gen_query)
    
    return {"queries": generated_queries, "filled_sections": state.filled_sections, "citations": state.citations}


async def finalize_summary(state: AIRAState, config: RunnableConfig, writer: StreamWriter):
    """
    Node for double checking the final summary is valid markdown
    and manually adding the sources list to the end of the report.
    """
    logger.info("FINALIZING REPORT")
    writer_llm = config["configurable"].get("writer_llm")
    
    intro = writer_llm.invoke([SystemMessage(content=intro_writer.format(report=state.current_report))] + [HumanMessage(content="Generate an executive summary for the report")])
    topic = config["configurable"].get("topic")
    current_report = f"# {topic} \n\n" + intro.content + "\n\n" + state.current_report + "\n\n ## Sources \n\n" + format_sources(state.citations)
    writer({"finalized_summary": current_report})
    return {"final_report": current_report}

