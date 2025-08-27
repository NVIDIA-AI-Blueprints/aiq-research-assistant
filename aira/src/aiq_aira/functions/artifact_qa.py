import logging
from typing import AsyncGenerator
from aiq.data_models.function import FunctionBaseConfig
from aiq.builder.builder import Builder
from aiq.cli.register_workflow import register_function
from aiq.builder.function_info import FunctionInfo
from aiq.builder.framework_enum import LLMFrameworkEnum
from aiq.data_models.component_ref import FunctionRef, LLMRef
import os

from aiq_aira.schema import (
    ArtifactQAInput,
    ArtifactQAOutput,
    GeneratedQuery
)

from aiq_aira.artifact_utils import artifact_chat_handler, check_relevant
from aiq_aira.nodes import process_single_query, deduplicate_and_format_sources

logger = logging.getLogger(__name__)


class ArtifactQAConfig(FunctionBaseConfig, name="artifact_qa"):
    """
    Configuration for an artifact Q&A function/endpoint.
    """
    llm_name: LLMRef = "instruct_llm"
    rag_url: str = ""


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

    async def _artifact_qa(query_message: ArtifactQAInput) -> ArtifactQAOutput:
        """
        Run the Q&A logic for a single user question about an artifact.
        """

        apply_guardrail = os.getenv("AIRA_APPLY_GUARDRAIL", "false")

        if apply_guardrail.lower() == "true":
        
            relevancy_check = await check_relevant(
                llm=llm,
                artifact=query_message.artifact,
                question=query_message.question,
                chat_history=query_message.chat_history
            )

            if relevancy_check == 'no':
                return ArtifactQAOutput(
                    updated_artifact=query_message.artifact,
                    assistant_reply="Sorry, I am not able to help answer that question. Please try again."
                )
            
        # Only enabled when not rewrite mode or rewrite mode is "entire"
        graph_config = {
            "configurable" :{
                "rag_url": config.rag_url,
            }
        }

        def writer(message):
            """
            The RAG search expects a stream writer function. 
            This is a temporary placeholder to satisfy the type checker.
            """
            logger.debug(f"Writing message: {message}")

        rag_answer, rag_citation, relevancy, web_answer, web_citation = await process_single_query(
            query=query_message.question,
            config=graph_config,
            writer=writer,
            collection=query_message.rag_collection,
            llm=llm,
            search_web=query_message.use_internet
        )

        gen_query = GeneratedQuery(
            query=query_message.question,
            report_section=query_message.artifact,
            rationale="Q/A"
        )

        query_message.question += "\n\n --- ADDITIONAL CONTEXT --- \n" + deduplicate_and_format_sources(
            [rag_citation], [rag_answer], [relevancy], [web_answer], [gen_query]
        )

        logger.info(f"Artifact QA Query message: {query_message}")

        return await artifact_chat_handler(llm, query_message)

    async def _artifact_qa_streaming(query_message: ArtifactQAInput) -> AsyncGenerator[ArtifactQAOutput, None]:
        """
        Run the Q&A logic for a single user question about an artifact, streaming the response.
        """

        apply_guardrail = os.getenv("AIRA_APPLY_GUARDRAIL", "false")

        if apply_guardrail.lower() == "true":
        
            relevancy_check = await check_relevant(
                llm=llm,
                artifact=query_message.artifact,
                question=query_message.question,
                chat_history=query_message.chat_history
            )

            if relevancy_check == 'no':
                yield ArtifactQAOutput(
                    updated_artifact=query_message.artifact,
                    assistant_reply="Sorry, I am not able to help answer that question. Please try again."
                )
                return
            
        # Only enabled when not rewrite mode or rewrite mode is "entire"
        graph_config = {
            "configurable": {
                "rag_url": config.rag_url,
            }
        }

        def writer(message):
            """
            The RAG search expects a stream writer function. 
            This is a temporary placeholder to satisfy the type checker.
            """
            logger.debug(f"Writing message: {message}")

        rag_answer, rag_citation, relevancy, web_answer, web_citation = await process_single_query(
            query=query_message.question,
            config=graph_config,
            writer=writer,
            collection=query_message.rag_collection,
            llm=llm,
            search_web=query_message.use_internet
        )

        gen_query = GeneratedQuery(
            query=query_message.question,
            report_section=query_message.artifact,
            rationale="Q/A"
        )

        query_message.question += "\n\n --- ADDITIONAL CONTEXT --- \n" + deduplicate_and_format_sources(
            [rag_citation], [rag_answer], [relevancy], [web_answer], [gen_query]
        )

        logger.info(f"Artifact QA Query message: {query_message}")

        yield await artifact_chat_handler(llm, query_message)

    yield FunctionInfo.create(
        single_fn=_artifact_qa,
        stream_fn=_artifact_qa_streaming,
        description="Chat-based Q&A about a previously generated artifact, optionally doing additional RAG lookups."
    )
