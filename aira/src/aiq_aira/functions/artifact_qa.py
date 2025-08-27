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

import logging
import os
from typing import AsyncGenerator

from aiq.builder.builder import Builder
from aiq.builder.framework_enum import LLMFrameworkEnum
from aiq.builder.function_info import FunctionInfo
from aiq.cli.register_workflow import register_function
from aiq.data_models.component_ref import FunctionRef
from aiq.data_models.component_ref import LLMRef
from aiq.data_models.function import FunctionBaseConfig

from aiq_aira.artifact_utils import artifact_chat_handler
from aiq_aira.artifact_utils import check_relevant
from aiq_aira.schema import ArtifactQAInput
from aiq_aira.schema import ArtifactQAOutput
from aiq_aira.schema import ArtifactRewriteMode
from aiq_aira.schema import GeneratedQuery
from aiq_aira.search_utils import deduplicate_and_format_sources
from aiq_aira.search_utils import process_single_query
from aiq_aira.utils import format_sources
from aiq_aira.utils import get_max_source_number

logger = logging.getLogger(__name__)


class ArtifactQAConfig(FunctionBaseConfig, name="artifact_qa"):
    """
    Configuration for an artifact Q&A function/endpoint.
    """
    llm_name: LLMRef = "instruct_llm"
    rag_url: str = ""
    eci_search_tool_name: FunctionRef | None = None


@register_function(config_type=ArtifactQAConfig)
async def artifact_qa_fn(config: ArtifactQAConfig, aiq_builder: Builder):
    """
    Registers a single-node graph to handle Q&A about a previously generated artifact.
    Exposed as 'artifact_qa' in config.yml
    The endpoint handles both report edits and general Q&A.
    Report edits are indicated by the 'rewrite_mode' parameter, set by the UI.
    For each case, the single query search endpoint is called with the user query and added as additional context.
    The search result, current report, and user query are then processed.
    The search is done to enable questions or edit requests that go beyond the
    scope of the original report contents.
    """

    # Acquire the LLM from the builder
    llm = await aiq_builder.get_llm(llm_name=config.llm_name, wrapper_type=LLMFrameworkEnum.LANGCHAIN)
    eci_search_tool = aiq_builder.get_function(
        name=config.eci_search_tool_name) if config.eci_search_tool_name else None

    async def _artifact_qa(query_message: ArtifactQAInput) -> ArtifactQAOutput:
        """
        Run the Q&A logic for a single user question about an artifact.
        """

        if eci_search_tool is None and query_message.use_eci:
            raise ValueError("ECI search is enabled but no ECI search tool is provided")

        apply_guardrail = os.getenv("AIRA_APPLY_GUARDRAIL", "false")

        if apply_guardrail.lower() == "true":

            relevancy_check = await check_relevant(llm=llm,
                                                   artifact=query_message.artifact,
                                                   question=query_message.question,
                                                   chat_history=query_message.chat_history)

            if relevancy_check == 'no':
                return ArtifactQAOutput(
                    updated_artifact=query_message.artifact,
                    assistant_reply="Sorry, I am not able to help answer that question. Please try again.")

        # Split sources from report
        current_artifact = query_message.artifact
        sources_marker = "## Sources"
        sources_pos = current_artifact.find(sources_marker)
        if sources_pos != -1:
            # Split the artifact into content and sources
            content = current_artifact[:sources_pos].strip()
            sources = current_artifact[sources_pos:].strip()
            source_num_start = get_max_source_number(sources) + 1
        else:
            # If no sources found, treat entire artifact as content
            content = current_artifact
            sources = ""
            source_num_start = None

        # Only enabled when not rewrite mode or rewrite mode is "entire"
        graph_config = {"configurable": {"rag_url": config.rag_url, }}

        def writer(message):
            """
            The RAG search expects a stream writer function.
            This is a temporary placeholder to satisfy the type checker.
            """
            logger.debug(f"Writing message: {message}")

        search_answer, search_citation = await process_single_query(
            query=query_message.question,
            config=graph_config,
            writer=writer,
            collection=query_message.rag_collection,
            llm=llm,
            eci_search_tool=eci_search_tool,
            search_web=query_message.use_internet,
            eci_search_bool=query_message.use_eci
        )

        gen_query = GeneratedQuery(query=query_message.question, report_section="user query", rationale="Q/A")

        query_message.additional_context = "\n\n --- ADDITIONAL CONTEXT --- \n" + deduplicate_and_format_sources(
            [search_citation], [search_answer], [gen_query])

        query_message.artifact = content

        # add sources to the report if we are re-writing, otherwise keep the original sources
        query_message.sources = sources

        if query_message.rewrite_mode:
            # if sources are empty we are handling Q&A for report plan so dont add sources
            if query_message.rewrite_mode == ArtifactRewriteMode.ENTIRE and sources != "":
                query_message.sources = sources + "\n" + format_sources(search_citation, source_num_start)

        return await artifact_chat_handler(llm, query_message)

    async def _artifact_qa_streaming(query_message: ArtifactQAInput) -> AsyncGenerator[ArtifactQAOutput, None]:
        """
        Run the Q&A logic for a single user question about an artifact, streaming the response.
        """

        # This is a placeholder async generator that raises NotImplementedError
        raise NotImplementedError("Streaming is not implemented for artifact_qa")
        # The following yield is unreachable but makes this a proper async generator
        yield ArtifactQAOutput(updated_artifact="", assistant_reply="")

    yield FunctionInfo.create(
        single_fn=_artifact_qa,
        stream_fn=_artifact_qa_streaming,
        description="Chat-based Q&A about a previously generated artifact, optionally doing additional RAG lookups.")
