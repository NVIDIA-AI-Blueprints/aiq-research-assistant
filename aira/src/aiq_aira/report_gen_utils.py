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
import logging

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langgraph.types import StreamWriter

from aiq_aira.constants import ASYNC_TIMEOUT
from aiq_aira.prompts import report_extender
from aiq_aira.prompts import summarizer_instructions
from aiq_aira.utils import update_system_prompt
from aiq_aira.utils import handle_stream_and_think_tags

logger = logging.getLogger(__name__)


async def summarize_report(existing_summary: str,
                           new_source: str,
                           report_organization: str,
                           llm: ChatOpenAI,
                           writer: StreamWriter) -> str:
    """
    Takes the web research results and writes a report draft.
    If an existing summary is provided, the report is extended.
    """
    # Decide which prompt to use
    if existing_summary:
        # We have an existing summary; use the 'report_extender' prompt
        user_input = report_extender.format(report=existing_summary, source=new_source)
    else:
        # No existing summary; use the 'summarizer_instructions' prompt
        user_input = summarizer_instructions.format(report_organization=report_organization, source=new_source)
    system_prompt = "you are a helpful assistant"
    system_prompt = update_system_prompt(system_prompt, llm)

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{input}"),
    ])
    chain = prompt | llm
    input_payload = {"input": user_input}
    
    writer({"summarize_sources": "\n Starting summary \n"})
    result = await handle_stream_and_think_tags(chain, input_payload, writer, "summarize_sources")

    # Handle both think tag and direct text responses properly
    if "<think>" in result and "</think>" in result:
        # Remove <think>...</think> sections for nemotron models
        while "<think>" in result and "</think>" in result:
            start = result.find("<think>")
            end = result.find("</think>") + len("</think>")
            result = result[:start] + result[end:]
        
        # Handle case where opening <think> tag might be missing
        while "</think>" in result:
            end = result.find("</think>") + len("</think>")
            result = result[end:]
    elif "<think>" in result and "</think>" not in result:
        # Incomplete think response - this is an error something has gone wrong
        if "nemotron" in str(type(llm)).lower() or (hasattr(llm, 'model_name') and "nemotron" in llm.model_name):
            logger.error("Nemotron model response has <think> but missing </think> tag - response incomplete")
            return user_input  # Return original input as fallback
        else:
            # For instruct models, just remove the incomplete think tag
            result = result.replace("<think>", "")
    # If no think tags at all, use the response as-is (normal for instruct models)

    # Return the final updated summary
    return result
