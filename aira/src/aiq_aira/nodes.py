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
import logging
import os
import re
import xml.etree.ElementTree as ET
from typing import List

import aiohttp
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableConfig
from langchain_core.stores import InMemoryByteStore
from langchain_core.utils.json import parse_json_markdown
from langgraph.types import StreamWriter

from aiq_aira.constants import ASYNC_TIMEOUT
from aiq_aira.prompts import finalize_report
from aiq_aira.prompts import query_writer_instructions
from aiq_aira.prompts import reflection_instructions
from aiq_aira.report_gen_utils import summarize_report
from aiq_aira.schema import AIRAState
from aiq_aira.schema import GeneratedQuery
from aiq_aira.search_utils import deduplicate_and_format_sources
from aiq_aira.search_utils import process_single_query
from aiq_aira.utils import format_sources
from aiq_aira.utils import update_system_prompt
from aiq_aira.utils import async_gen
from aiq_aira.utils import handle_stream_and_think_tags
from aiq.profiler.decorators.function_tracking import track_function


logger = logging.getLogger(__name__)
store = InMemoryByteStore()

@track_function(metadata={"source": "generate_queries"})
async def generate_query(state: AIRAState, config: RunnableConfig, writer: StreamWriter):
    """
    Node for generating a research plan as a list of queries. 
    Takes in a topic and desired report organization. 
    Returns the list of query objects. 
    """
    logger.info("GENERATE QUERY")
    writer({"generating_questions": "\n Generating queries \n"
            })  # send something to initialize the UI so the timeout shows

    # Generate a query
    llm = config["configurable"].get("llm")
    number_of_queries = config["configurable"].get("number_of_queries")
    report_organization = config["configurable"].get("report_organization")
    topic = config["configurable"].get("topic")

    system_prompt = "you are a helpful assistant"
    system_prompt = update_system_prompt(system_prompt, llm)

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{input}"),
    ])
    chain = prompt | llm

    input = {
        "topic":
            topic,
        "report_organization":
            report_organization,
        "number_of_queries":
            number_of_queries,
        "input":
            query_writer_instructions.format(topic=topic,
                                             report_organization=report_organization,
                                             number_of_queries=number_of_queries)
    }

    answer_agg = await handle_stream_and_think_tags(chain, input, writer, "generating_questions")

    # Log the full response for debugging
    logger.info(f"Full response length: {len(answer_agg)}")
    logger.info(f"Response contains <think>: {'<think>' in answer_agg}")
    logger.info(f"Response contains </think>: {'</think>' in answer_agg}")
    
    # Try to parse with </think> tags first (for nemotron models)
    if "</think>" in answer_agg:
        splitted = answer_agg.split("</think>")
        if len(splitted) >= 2:
            json_str = splitted[1].strip()
        else:
            # If splitting fails, the response is malformed
            logger.error("Found <think> but failed to properly split on </think>")
            queries = []
            return {"queries": queries}
    else:
        # For instruct models that don't use think tags, use the full response
        # But for nemotron models, this indicates an incomplete response
        if "nemotron" in str(type(llm)).lower() or (hasattr(llm, 'model_name') and "nemotron" in llm.model_name):
            logger.error("Nemotron model response missing </think> tag - response incomplete")
            queries = []
            return {"queries": queries}
        else:
            # Direct JSON parsing (for instruct models)
            json_str = answer_agg

    try:
        queries = parse_json_markdown(json_str)
        
        # Validate that we have a list of properly formatted queries
        if not isinstance(queries, list):
            logger.error(f"Expected list of queries, got {type(queries)}")
            queries = []
        else:
            # Validate each query has required fields
            validated_queries = []
            for i, query in enumerate(queries):
                if isinstance(query, dict) and all(field in query for field in ["query", "report_section", "rationale"]):
                    validated_queries.append(query)
                else:
                    logger.warning(f"Query {i} missing required fields: {query}")
            queries = validated_queries
            
            logger.info(f"Successfully parsed {len(queries)} queries")
            
    except Exception as e:
        logger.error(f"Error parsing queries as JSON: {e}")
        logger.info(f"Raw response: {answer_agg}")
        queries = []

    return {"queries": queries}


async def web_research(state: AIRAState, config: RunnableConfig, writer: StreamWriter):
    """
    Node for performing research based on the queries returned by generate_query.
    Research is performed deterministically by running RAG (and optionally a web search) on each query.
    The function extracts the queries from the state, processes each one via process_single_query,
    and finally formats the sources into an aggregated XML structure.
    A separate list of source citations is also maintained, tracking the query, answer, and sources for each query.
    """

    logger.info("STARTING WEB RESEARCH")
    llm = config["configurable"].get("llm")
    eci_search_tool = config["configurable"].get("eci_search_tool")
    search_web = config["configurable"].get("search_web")
    collection = config["configurable"].get("collection")

    # Determine the queries and state queries based on the type of state.
    # If the state is a list of queries, use them directly.
    queries = [q.query for q in state.queries]
    state_queries = state.queries

    # Process each query concurrently.
    results = await asyncio.gather(*[
        process_single_query(query, config, writer, collection, llm, eci_search_tool, search_web) for query in queries
    ])

    # Unpack results.
    generated_answers = [result[0] for result in results]
    citations = [result[1] if result[1] is not None else "" for result in results]

    # Format the sources (producing a combined XML <sources> structure).
    search_str = deduplicate_and_format_sources(citations, generated_answers, state_queries)

    unique_citations = set(citations)  # remove duplicates
    citation_str = "\n".join(unique_citations)
    return {"citations": citation_str, "web_research_results": [search_str]}

@track_function(metadata={"source": "write_report"})
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
    updated_report = await summarize_report(existing_summary=existing_summary,
                                            new_source=most_recent_web_research,
                                            report_organization=report_organization,
                                            llm=llm,
                                            writer=writer)

    state.running_summary = updated_report

    writer({"running_summary": updated_report})
    return {"running_summary": updated_report}

@track_function(metadata={"source": "reflection"})
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
    eci_search_tool = config["configurable"].get("eci_search_tool")
    num_reflections = config["configurable"].get("num_reflections")
    report_organization = config["configurable"].get("report_organization")
    search_web = config["configurable"].get("search_web")
    collection = config["configurable"].get("collection")

    logger.info(f"REFLECTING {num_reflections} TIMES")

    for i in range(num_reflections):
        input = {
            "input":
                reflection_instructions.format(report_organization=report_organization,
                                               topic=config["configurable"].get("topic"),
                                               report=state.running_summary)
        }
        system_prompt = "You are a helpful assistant"
        system_prompt = update_system_prompt(system_prompt, llm)

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human",
             "Using report organization as a guide identify a knowledge gap and generate a follow-up web search query based on our existing knowledge. \n \n {input}"
             ),
        ])
        chain = prompt | llm

        writer({"reflect_on_summary": "\n Starting reflection \n"})
        result = await handle_stream_and_think_tags(chain, input, writer, "reflect_on_summary")

        # Try to parse with </think> tags first (for nemotron models)
        if "</think>" in result:
            splitted = result.split("</think>")
            if len(splitted) >= 2:
                reflection_json = splitted[1].strip()
            else:
                # If splitting fails, the response is malformed
                logger.error("Found <think> but failed to properly split on </think> in reflection")
                running_summary = state.running_summary
                writer({"running_summary": running_summary})
                return {"running_summary": running_summary}
        else:
            # For instruct models that don't use think tags, use the full response
            # But for nemotron models, this indicates an incomplete response
            if "nemotron" in str(type(llm)).lower() or (hasattr(llm, 'model_name') and "nemotron" in llm.model_name):
                logger.error("Nemotron model reflection response missing </think> tag - response incomplete")
                running_summary = state.running_summary
                writer({"running_summary": running_summary})
                return {"running_summary": running_summary}
            else:
                # Direct JSON parsing (for instruct models)
                reflection_json = result

        if not reflection_json.strip():
            # If we can't parse anything, return current state
            running_summary = state.running_summary
            writer({"running_summary": running_summary})
            return {"running_summary": running_summary}

        try:
            reflection_obj = parse_json_markdown(reflection_json)
            gen_query = GeneratedQuery(
                query=reflection_obj["query"] if "query" in reflection_obj else str(reflection_obj),
                report_section="All",
                rationale="Reflection-based query")
        except Exception as e:
            logger.warning(f"Error parsing reflection JSON: {e}")
            reflection_obj = reflection_json
            gen_query = GeneratedQuery(query=reflection_obj, report_section="All", rationale="Reflection-based query")


        rag_answer, rag_citation = await process_single_query(
            query=gen_query.query,
            config=config,
            writer=writer,
            collection=collection,
            llm=llm,
            eci_search_tool=eci_search_tool,
            search_web=search_web
        )

        search_str = deduplicate_and_format_sources([rag_citation], [rag_answer], [gen_query])

        state.web_research_results.append(search_str)
        state.citations = "\n".join([state.citations, rag_citation])

        # Most recent web research
        existing_summary = state.running_summary
        most_recent_web_research = state.web_research_results[-1]

        updated_report = await summarize_report(existing_summary=existing_summary,
                                                new_source=most_recent_web_research,
                                                report_organization=report_organization,
                                                llm=llm,
                                                writer=writer)

        state.running_summary = updated_report

        writer({"running_summary": updated_report})

    running_summary = state.running_summary
    writer({"running_summary": running_summary})
    return {"running_summary": running_summary, "citations": state.citations}

@track_function(metadata={"source": "finalize_summary"})
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
    
    # Check if LLM has streaming disabled
    llm_stream_enabled = not getattr(llm, 'disable_streaming', False)
    logger.debug(f"LLM streaming enabled: {llm_stream_enabled}")
    
    try:
        async with asyncio.timeout(ASYNC_TIMEOUT*3):
            if llm_stream_enabled:
                # Use streaming for LLMs that support it
                async for chunk in finalizer.astream({
                    "report": state.running_summary,
                    "report_organization": report_organization,
                }):
                    final_buf += chunk.content
                    writer({"final_report": chunk.content})
            else:
                # Use non-streaming for LLMs with streaming disabled (like nemotron)
                logger.debug("Using non-streaming mode for finalize LLM")
                response = await finalizer.ainvoke({
                    "report": state.running_summary,
                    "report_organization": report_organization,
                })
                final_buf = response.content
                writer({"final_report": final_buf})
    except asyncio.TimeoutError as e:
        writer({
            "final_report":
                " \n \n --------------- \n Timeout error from reasoning LLM during final report creation. Consider restarting report generation. \n \n "
        })
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
