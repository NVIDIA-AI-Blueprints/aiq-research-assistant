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

from langchain_openai import ChatOpenAI
from langgraph.types import StreamWriter
from langchain_core.prompts import ChatPromptTemplate

from aiq_aira.prompts import (
    report_extender,
    summarizer_instructions
)

from aiq_aira.constants import ASYNC_TIMEOUT
from aiq_aira.utils import update_system_prompt
import asyncio
import logging

logger = logging.getLogger(__name__)

async def summarize_report(
        existing_summary: str,
        new_source: str,
        report_organization: str,
        llm: ChatOpenAI,
        writer: StreamWriter
) -> str:
    """
    Takes the web research results and writes a report draft.
    If an existing summary is provided, the report is extended.
    """
    # Decide which prompt to use
    if existing_summary:
        # We have an existing summary; use the 'report_extender' prompt
        user_input = report_extender.format(report=existing_summary, source=new_source, report_organization=report_organization)
    else:
        # No existing summary; use the 'summarizer_instructions' prompt
        user_input = summarizer_instructions.format(
            report_organization=report_organization,
            source=new_source
        )
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

    # Stream the result
    result = ""
    stop = False
    input_payload = {"input": user_input}
    try: 
        writer({"summarize_sources": "\n Starting summary \n"})
        async with asyncio.timeout(ASYNC_TIMEOUT):
            async for chunk in chain.astream(input_payload, stream_usage=True):
                result += chunk.content
                if chunk.content == "</think>":
                    stop = True
                if not stop:
                    writer({"summarize_sources": chunk.content})
    except asyncio.TimeoutError as e:
        writer({"summarize_sources": " \n \n ---------------- \n \n Timeout error from reasoning LLM. Consider running report generation again. \n \n "})

        return user_input

    # Remove <think>...</think> sections
    while "<think>" in result and "</think>" in result:
        start = result.find("<think>")
        end = result.find("</think>") + len("</think>")
        result = result[:start] + result[end:]
    
    # Handle case where opening <think> tag might be missing
    while "</think>" in result:
        end = result.find("</think>") + len("</think>")
        result = result[end:]

    # Return the final updated summary
    return result