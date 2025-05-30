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
import aiohttp
import json
import os
import logging
import xml.etree.ElementTree as ET
from typing import List
import re
from langchain_core.runnables import RunnableConfig
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_core.utils.json import parse_json_markdown
from langchain_core.stores import InMemoryByteStore
from langgraph.types import StreamWriter
from aiq_aira.schema import  GeneratedQuery

from aiq_aira.schema import AIRAState
from aiq_aira.prompts import (
    finalize_report,
    query_writer_instructions,
    reflection_instructions,
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
    search_web = config["configurable"].get("search_web")
    collection = config["configurable"].get("collection")

    # Determine the queries and state queries based on the type of state.
    # If the state is a list of queries, use them directly.
    queries = [q.query for q in state.queries]
    state_queries = state.queries
   

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

    # Format the sources (producing a combined XML <sources> structure).
    search_str = deduplicate_and_format_sources(
        citations, generated_answers, relevancy_list, web_results, state_queries
    )

    all_citations = []
    for idx, citation in enumerate(citations):
        if relevancy_list[idx]["score"] == "yes":
            all_citations.append(citation)
        if relevancy_list[idx]["score"] != "yes" and citations_web[idx] not in ["N/A", ""]:
            all_citations.append(citations_web[idx])

    all_citations = set(all_citations) # remove duplicates
    citation_str = "\n".join(all_citations)
    return {"citations": citation_str, "web_research_results": [search_str]}


async def summarize_sources(
        state: AIRAState,
        config: RunnableConfig,
        writer: StreamWriter
):
    """
    Node for summarizing or extending an existing summary. Takes the web research report and writes a report draft.
    """
    logger.info("SUMMARIZE")
    llm = config["configurable"].get("llm")
    report_organization = config["configurable"].get("report_organization")

    # The most recent web research
    most_recent_web_research = state.web_research_results[-1]
    existing_summary = state.running_summary

    # -- Call the helper function here --
    updated_report = await summarize_report(
        existing_summary=existing_summary,
        new_source=most_recent_web_research,
        report_organization=report_organization,
        llm=llm,
        writer=writer
    )

    state.running_summary = updated_report

    writer({"running_summary": updated_report})
    return {"running_summary": updated_report}


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
    num_reflections = config["configurable"].get("num_reflections")
    report_organization = config["configurable"].get("report_organization")
    search_web = config["configurable"].get("search_web")
    collection = config["configurable"].get("collection")

    logger.info(f"REFLECTING {num_reflections} TIMES")

    for i in range(num_reflections):
        input = {
            "input": reflection_instructions.format(report_organization=report_organization, topic=config["configurable"].get("topic"), report=state.running_summary)

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
            running_summary = state.running_summary
            writer({"running_summary": running_summary})
            return {"running_summary": running_summary}

        reflection_json = splitted[1].strip()
        try:
            reflection_obj = parse_json_markdown(reflection_json)
            gen_query = GeneratedQuery(
                query=reflection_obj["query"] if "query" in reflection_obj else str(reflection_obj),
                report_section="All",
                rationale="Reflection-based query"
            )
        except Exception as e:
            logger.warning(f"Error parsing reflection JSON: {e}")
            reflection_obj = reflection_json
            gen_query = GeneratedQuery(
                query=reflection_obj,
                report_section="All",
                rationale="Reflection-based query"
            )


        rag_answer, rag_citation, relevancy, web_answer, web_citation = await process_single_query(
            query=gen_query.query,
            config=config,
            writer=writer,
            collection=collection,
            llm=llm,
            search_web=search_web
        )


        search_str = deduplicate_and_format_sources(
            [rag_citation], [rag_answer], [relevancy], [web_answer], [gen_query]
        )

        state.web_research_results.append(search_str)
        
        if relevancy['score'] == "yes" and rag_citation is not None:
            state.citations = "\n".join([state.citations, rag_citation])

        if relevancy['score'] != "yes" and web_citation not in ["N/A", ""] and web_citation is not None:
            state.citations = "\n".join([state.citations, web_citation])

        # Most recent web research
        existing_summary = state.running_summary
        most_recent_web_research = state.web_research_results[-1]

        updated_report = await summarize_report(
            existing_summary=existing_summary,
            new_source=most_recent_web_research,
            report_organization=report_organization,
            llm=llm,
            writer=writer
        )


        state.running_summary = updated_report

        writer({"running_summary": updated_report})

    running_summary = state.running_summary
    writer({"running_summary": running_summary})
    return {"running_summary": running_summary, "citations": state.citations}

async def finalize_summary(state: AIRAState, config: RunnableConfig, writer: StreamWriter):
    """
    Node for double checking the final summary is valid markdown
    and manually adding the sources list to the end of the report.
    """
    logger.info("FINALZING REPORT")
    llm = config["configurable"].get("llm")
    report_organization = config["configurable"].get("report_organization")

    
    writer({"final_report": "\n Starting finalization \n"})

    sources_formatted = format_sources(state.citations)
    
    # Final report creation, used to remove any remaing model commentary from the report draft
    finalizer = PromptTemplate.from_template(finalize_report) | llm
    final_buf = ""
    try:
        async with asyncio.timeout(ASYNC_TIMEOUT*3):
            async for chunk in finalizer.astream({
                "report": state.running_summary,
                "report_organization": report_organization,
            }, stream_usage=True):
                final_buf += chunk.content
                writer({"final_report": chunk.content})
    except asyncio.TimeoutError as e:
        writer({"final_report": " \n \n --------------- \n Timeout error from reasoning LLM during final report creation. Consider restarting report generation. \n \n "})
        state.running_summary = f"{state.running_summary} \n\n ---- \n\n {sources_formatted}"
        writer({"finalized_summary": state.running_summary})
        return {"final_report": state.running_summary, "citations": sources_formatted}
    
    # Strip out <think> sections
    while "<think>" in final_buf and "</think>" in final_buf:
        start = final_buf.find("<think>")
        end = final_buf.find("</think>") + len("</think>")
        final_buf = final_buf[:start] + final_buf[end:]
    
    # Handle case where opening <think> tag might be missing
    while "</think>" in final_buf:
        end = final_buf.find("</think>") + len("</think>")
        final_buf = final_buf[end:]
        
    state.running_summary = f"{final_buf} \n\n ## Sources \n\n{sources_formatted}"    
    writer({"finalized_summary": state.running_summary})
    return {"final_report": state.running_summary, "citations": sources_formatted}