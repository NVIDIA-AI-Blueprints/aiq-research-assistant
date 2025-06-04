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

import logging
import os
import json
import asyncio

from typing import Any, AsyncGenerator
from pydantic import BaseModel
from aiq.builder.builder import Builder
from aiq.cli.register_workflow import register_function
from aiq.data_models.component_ref import LLMRef
from aiq.data_models.component_ref import FunctionRef
from aiq.data_models.function import FunctionBaseConfig
from aiq.builder.function_info import FunctionInfo
from aiq.data_models.api_server import AIQChatResponseChunk
from aiq_aira.functions import generate_summary, generate_queries, artifact_qa
from aiq.builder.framework_enum import LLMFrameworkEnum
from aiq.plugins.langchain import register
from aiq_aira.tools import tavily_search, rag_search
from aiq_aira.search_agent.register import search_agent_workflow
logger = logging.getLogger(__name__)

os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY", "ollama")  # needed if you are using OLLAMA


################################################
# Default Collections
################################################
class DefaultCollection(BaseModel):
    name: str
    topic: str
    report_organization: str

class DefaultCollectionsConfig(FunctionBaseConfig, name="default_collections"):
    collections: list[DefaultCollection]

@register_function(config_type=DefaultCollectionsConfig)
async def default_collections(config: DefaultCollectionsConfig, builder: Builder):
    """
    Returns information about the example collections used by the AIRA demo frontend
    """
    async def _default_collections(request: None = None) -> list[DefaultCollection]:
        return config.collections

    yield FunctionInfo.from_fn(
        _default_collections,
        description="Information about the example collections used by the AIRA demo frontend"
    )

################################################
# Health Check
################################################
class HealthCheckConfig(FunctionBaseConfig, name="health_check"):
    pass

@register_function(config_type=HealthCheckConfig)
async def health_check(config: HealthCheckConfig, builder: Builder):
    """
    Health check for the AIQ AIRA backend service
    """
    async def _health_check(request: None = None) -> dict:
        return {"status": "OK"}

    yield FunctionInfo.from_fn(
        _health_check,
        description="Health check for the AIQ AIRA service"
    )

################################################
# Additional Data Models
################################################
class AIResearcherInput(BaseModel):
    topic: str
    report_organization: str
    search_web: bool
    rag_collection: str
    num_queries: int
    llm_name: str

################################################
# End to end research workflow
################################################
# note the component parts generate_queries, generate_summary, and artifact_qa 
# are used in the AIRA demo frontend
# the ai_researcher workflow is not used in the AIRA demo frontend
# the components are registered for AIQ serve by importing them in this file

class AIResearcherWorkflowConfig(FunctionBaseConfig, name="ai_researcher"):
    """
    Run the entire research pipeline to generate a query plan and a report without human in the loop intervention
    This workflow is not used in the AIRA demo frontend
    """
    rag_url: str = ""

@register_function(config_type=AIResearcherWorkflowConfig)
async def ai_researcher(config: AIResearcherWorkflowConfig, builder: Builder):
    """
    Orchestrates:
      1) Generate queries
      2) Generate summary

    So the user only has to call one endpoint to get from raw topic -> final report.
    """

    generate_queries = builder.get_function(name="generate_query")  
    generate_summary = builder.get_function(name="generate_summary") 

    async def _response_stream_fn(input_message: str) -> AsyncGenerator[AIQChatResponseChunk, None]:
        """
        If we want streaming chunk output, we run each stage, yielding chunks along the way.
        """
        logger.debug("Starting ai_researcher orchestrated pipeline (stream)")

        # Parse user input
        user_input = json.loads(input_message)
        data = AIResearcherInput.model_validate(user_input)

        # Stage 1: Generate queries
        queries_result = await generate_queries.ainvoke({
            "topic": data.topic,
            "report_organization": data.report_organization,
            "search_web": data.search_web,
            "num_queries": data.num_queries,
            "llm_name": data.llm_name
        })
        # Streams from generate_queries are not shown unless you stream them directly
        # We'll yield a chunk with the queries
        yield AIQChatResponseChunk.from_string(f"Queries: {json.dumps(queries_result.queries)}")

        # Stage 2: Generate summary
        summary_result = await generate_summary.ainvoke({
            "topic": data.topic,
            "report_organization": data.report_organization,
            "queries": queries_result.queries,
            "search_web": data.search_web,
            "rag_collection": data.rag_collection,
            "llm_name": data.llm_name
        })

        # yield final
        final_report = summary_result.final_report
        yield AIQChatResponseChunk.from_string(final_report)

        logger.debug("Finished ai_researcher orchestrated pipeline (stream)")

    async def _response_single_fn(input_message: str) -> str:
        """
        If you want a single synchronous-style response (non-stream),
        we run both stages, then return only the final text.
        """
        logger.debug("Starting ai_researcher orchestrated pipeline (single)")

        user_input = json.loads(input_message)
        data = AIResearcherInput.model_validate(user_input)

        # Stage 1
        queries_result = await generate_queries.ainvoke({
            "topic": data.topic,
            "report_organization": data.report_organization,
            "search_web": data.search_web,
            "num_queries": data.num_queries,
            "llm_name": data.llm_name
        })
        # Stage 2
        summary_result = await generate_summary.ainvoke({
            "topic": data.topic,
            "report_organization": data.report_organization,
            "queries": queries_result.queries,
            "search_web": data.search_web,
            "rag_collection": data.rag_collection,
            "llm_name": data.llm_name
        })

        final_report = summary_result.final_report

        logger.debug("Finished ai_researcher orchestrated pipeline (single)")
        return final_report

    yield FunctionInfo.create(
        stream_fn=_response_stream_fn,
        single_fn=_response_single_fn
    )
