from langchain_openai import ChatOpenAI
from langgraph.types import StreamWriter
from langchain_core.prompts import ChatPromptTemplate

from aiq_aira.prompts import (
    report_extender,
    summarizer_instructions
)

from aiq_aira.constants import ASYNC_TIMEOUT
from aiq_aira.utils import update_system_prompt
from aiq_aira.llm_utils import stream_llm_response_with_reasoning, remove_reasoning_tokens
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
        user_input = report_extender.format(report=existing_summary, source=new_source)
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

    # Stream the result using the new LLM utility
    input_payload = {"input": user_input}
    
    writer({"summarize_sources": "\n Starting summary \n"})
    
    result, success = await stream_llm_response_with_reasoning(
        chain=chain,
        llm=llm,
        input_data=input_payload,
        writer=writer,
        writer_key="summarize_sources",
        timeout=ASYNC_TIMEOUT,
        stream_usage=True
    )
    
    if not success:
        return user_input

    # Remove reasoning tokens
    result = remove_reasoning_tokens(result, llm)

    # Return the final updated summary
    return result