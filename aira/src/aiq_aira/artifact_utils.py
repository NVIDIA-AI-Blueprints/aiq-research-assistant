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

from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_core.utils.json import parse_json_markdown

from aiq_aira.artifact_prompts import (
    UPDATE_ENTIRE_ARTIFACT_PROMPT,
    RELEVANCY_CHECK
)

from aiq_aira.schema import ArtifactQAInput, ArtifactQAOutput, ArtifactRewriteMode
from aiq_aira.llm_utils import remove_reasoning_tokens

logger = logging.getLogger(__name__)

##############################
# Helper functions for rewriting
##############################


# Use the imported remove_reasoning_tokens function from llm_utils
async def check_relevant(llm, artifact, question, chat_history: list[str]):
    
    try:
        prompt = PromptTemplate.from_template(RELEVANCY_CHECK)
        relevancy_checker = prompt | llm 
        result =  await relevancy_checker.ainvoke({"artifact": artifact,"prompt": question})

        
        response = parse_json_markdown(result.content)
        if 'relevant' not in response:
            return 'no'
        
    except Exception as e:
        logger.info(f"Failed to apply guardrails with {question} and {result}")
        return 'no'
    
    return response['relevant']


async def do_entire_artifact_rewrite(llm, artifact_content: str, user_message: str):
    """
    Rewrites the entire artifact using the prompt: UPDATE_ENTIRE_ARTIFACT_PROMPT
    If the user wants a new artifact type or title, we can also incorporate GET_TITLE_TYPE_REWRITE_ARTIFACT or similar.
    """
    updateMetaPrompt = ""  # Optionally insert dynamic meta prompt
    rewrite_prompt = UPDATE_ENTIRE_ARTIFACT_PROMPT.format(
        artifactContent=artifact_content,
        reflections="N/A",  # or user-specific reflections
        updateMetaPrompt=updateMetaPrompt
    )
    # The user request is appended to the end.
    user_facing_prompt = rewrite_prompt + f"\n\nUser request:\n{user_message}"

    # Use the new LLM streaming utility with proper system prompt
    from aiq_aira.llm_utils import stream_llm_response_with_reasoning, update_system_prompt_for_reasoning
    from langchain_core.prompts import ChatPromptTemplate
    
    # Create a proper system prompt
    system_prompt = "You are a helpful AI assistant that can rewrite artifacts based on user requests."
    system_prompt = update_system_prompt_for_reasoning(system_prompt, llm)
    
    # Create a proper chat prompt template
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{input}")
    ])
    chain = prompt | llm
    
    final_text, _ = await stream_llm_response_with_reasoning(
        chain=chain,
        llm=llm,
        input_data={"input": user_facing_prompt},
        writer=lambda x: None,  # No streaming needed for this function
        writer_key="",
        timeout=None,
        stream_usage=False
    )

    # strip out reasoning tokens if present
    final_text = remove_reasoning_tokens(final_text, llm)

    return final_text.strip()


##############################
# The main chat function
##############################

async def artifact_chat_handler(llm, input_data: ArtifactQAInput) -> ArtifactQAOutput:
    """
    1) If user asked for a rewrite (rewrite_mode is set), call the correct rewriting routine.
    2) Else do normal Q&A with the artifact as context.
    3) Return updated artifact + assistant message.
    """

    current_artifact = input_data.artifact
    user_message = input_data.question
    chat_history = input_data.chat_history or []
    rewrite_mode: ArtifactRewriteMode = input_data.rewrite_mode
    additional_context = input_data.additional_context

    def add_context_to_user_message(msg):
        context = additional_context
        if not context:
            return msg

        return f"{msg}\n\nAdditional context:\n{context}"

    # 1) If user specifically wants a rewrite:
    if input_data.rewrite_mode:

        if rewrite_mode == ArtifactRewriteMode.ENTIRE:

            updated = await do_entire_artifact_rewrite(llm, current_artifact,
                                                       add_context_to_user_message(user_message))

            return ArtifactQAOutput(
                updated_artifact=updated,
                assistant_reply="Here is the updated artifact (entire rewrite)."
            )

        else:
            # Unrecognized rewrite mode
            return ArtifactQAOutput(
                updated_artifact=current_artifact,
                assistant_reply=(
                    f"I do not recognize rewrite_mode={rewrite_mode}. "
                    f"No changes made. Q/A session is available if needed."
                )
            )

    # 2) Otherwise, do normal Q&A with the artifact
    # We build a system + conversation + user approach
    # We'll stuff the artifact in a system message for context
    system_context = (
        "<app-context>\n"
        "You are a helpful AI assistant. The user has an artifact (text, doc, or code) in front of them. "
        "You can refer to it as needed to answer questions or provide clarifications. "
        "When writing code, do not wrap with triple backticks, as the UI doesn't want them. "
        "Follow the user requests carefully.\n"
        "</app-context>\n\n"
        f"<artifact>\n{current_artifact}\n</artifact>"
    )

    # Convert chat_history to a list of Human/AI messages.
    # We'll just do a naive approach: even indices are user, odd indices are assistant.
    conversation_messages = [HumanMessage(content=system_context)]
    for i, text in enumerate(chat_history):
        if i % 2 == 0:
            conversation_messages.append(HumanMessage(content=text))
        else:
            conversation_messages.append(AIMessage(content=text))

    # Add the new user message
    conversation_messages.append(HumanMessage(content=user_message))

    # Build a ChatPromptTemplate
    prompt = ChatPromptTemplate.from_messages(conversation_messages).format_messages()

    # Call the LLM using the new utility with proper system prompt
    from aiq_aira.llm_utils import stream_llm_response_with_reasoning, update_system_prompt_for_reasoning
    
    # Create a proper system prompt
    system_prompt = "You are a helpful AI assistant that can answer questions about artifacts."
    system_prompt = update_system_prompt_for_reasoning(system_prompt, llm)
    
    # Create a proper chat prompt template
    chat_prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{input}")
    ])
    chain = chat_prompt | llm
    
    answer_buf, _ = await stream_llm_response_with_reasoning(
        chain=chain,
        llm=llm,
        input_data={"input": user_message},
        writer=lambda x: None,  # No streaming needed for this function
        writer_key="",
        timeout=None,
        stream_usage=False
    )

    # Remove reasoning tokens if present
    answer_buf = remove_reasoning_tokens(answer_buf, llm)

    assistant_reply = answer_buf.strip()

    return ArtifactQAOutput(
        updated_artifact=current_artifact,
        assistant_reply=assistant_reply
    )
