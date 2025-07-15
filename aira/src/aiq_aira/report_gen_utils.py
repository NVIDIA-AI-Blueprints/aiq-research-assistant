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

    # Stream the result
    result = ""
    in_think_section = False
    input_payload = {"input": user_input}
    
    # Check if LLM has streaming disabled
    llm_stream_enabled = not getattr(llm, 'disable_streaming', False)
    logger.debug(f"LLM streaming enabled: {llm_stream_enabled}")
    
    try: 
        writer({"summarize_sources": "\n Starting summary \n"})
        async with asyncio.timeout(ASYNC_TIMEOUT):
            if llm_stream_enabled:
                # Use streaming for LLMs that support it
                async for chunk in chain.astream(input_payload):
                    result += chunk.content
                    
                    # Track if we're in a think section to avoid showing reasoning to users
                    if "<think>" in chunk.content:
                        in_think_section = True
                    if "</think>" in chunk.content:
                        in_think_section = False
                        # Don't stream the closing think tag
                        continue
                    
                    # Only stream content that's not in think sections
                    if not in_think_section:
                        writer({"summarize_sources": chunk.content})
            else:
                # Use non-streaming for LLMs with streaming disabled (like nemotron)
                logger.debug("Using non-streaming mode for summarize LLM")
                response = await chain.ainvoke(input_payload)
                result = response.content
                
                # For non-streaming, we need to filter out think sections before showing to user
                if "<think>" in result and "</think>" in result:
                    # Show everything after </think>
                    think_end = result.find("</think>")
                    if think_end != -1:
                        user_content = result[think_end + len("</think>"):].strip()
                        if user_content:
                            writer({"summarize_sources": user_content})
                else:
                    # No think tags, show everything
                    writer({"summarize_sources": result})
    except asyncio.TimeoutError as e:
        writer({"summarize_sources": " \n \n ---------------- \n \n Timeout error from reasoning LLM. Consider running report generation again. \n \n "})
        return user_input

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
