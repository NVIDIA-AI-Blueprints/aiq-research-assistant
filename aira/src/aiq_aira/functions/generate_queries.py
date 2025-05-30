from typing import AsyncGenerator
import typing
from aiq.data_models.api_server import AIQChatResponseChunk
from aiq.data_models.component_ref import LLMRef
from aiq.data_models.function import FunctionBaseConfig
from aiq.builder.builder import Builder
from aiq.cli.register_workflow import register_function
from aiq.builder.function_info import FunctionInfo
from aiq.builder.framework_enum import LLMFrameworkEnum
import json

from aiq_aira.nodes import generate_query
from aiq_aira.schema import (
    ConfigSchema,
    GenerateQueryStateInput,
    GenerateQueryStateOutput,
    AIRAState,
)
from langchain_core.runnables import RunnableConfig
from langgraph.graph import START, END, StateGraph
import logging

logger = logging.getLogger(__name__)

class AIRAGenerateQueriesConfig(FunctionBaseConfig, name="generate_queries"):
    """
    Configuration for the generate_queries function/endpoint
    """

@register_function(config_type=AIRAGenerateQueriesConfig)
async def generate_queries_fn(config: AIRAGenerateQueriesConfig, aiq_builder: Builder):
    """
    The main function for report planning, representing /generate_queries in config.yml
    """
    # Build a simple graph from START -> generate_query -> END
    builder = StateGraph(
        AIRAState,
        config_schema=ConfigSchema
    )

    builder.add_node("generate_query", generate_query)
    builder.add_edge(START, "generate_query")
    builder.add_edge("generate_query", END)

    graph = builder.compile()

    async def _generate_queries_single(message: GenerateQueryStateInput) -> GenerateQueryStateOutput:
        """
        This function runs the graph to generate queries for a given topic/report structure
        """
        # Acquire the LLM from the builder
        llm = await aiq_builder.get_llm(llm_name=message.llm_name, wrapper_type=LLMFrameworkEnum.LANGCHAIN)
        llm.model_kwargs["stream_options"] = {"include_usage": True, "continuous_usage_stats": True}

        response = await graph.ainvoke(
            input={"queries": [], "web_research_results": [], "running_summary": ""},
            config={
                "llm": llm,
                "number_of_queries": message.num_queries,
                "report_organization": message.report_organization,
                "topic": message.topic
            }
        )
        return GenerateQueryStateOutput.model_validate(response)

    # ------------------------------------------------------------------
    # STREAMING VERSION
    # ------------------------------------------------------------------
    async def _generate_queries_stream(
            message: GenerateQueryStateInput
    ) -> AsyncGenerator[GenerateQueryStateOutput, None]:
        """
        This function runs the graph to generate queries for a given topic/report structure, streaming the response
        """
        # Acquire the LLM from the builder
        llm = await aiq_builder.get_llm(llm_name=message.llm_name, wrapper_type=LLMFrameworkEnum.LANGCHAIN)

        async for _t, val in graph.astream(
            input={"queries": [], "web_research_results": [], "running_summary": ""},
            stream_mode=['custom', 'values'],
            config={
                "llm": llm,
                "number_of_queries": message.num_queries,
                "report_organization": message.report_organization,
                "topic": message.topic
            }
        ):

            if _t == "values":
                if "queries" not in val:
                    yield GenerateQueryStateOutput(intermediate_step=json.dumps(val))
                else:
                    yield GenerateQueryStateOutput(
                        queries=val['queries']
                    )
            else:
                yield GenerateQueryStateOutput(intermediate_step=json.dumps(val))

    yield FunctionInfo.create(
        single_fn=_generate_queries_single,
        stream_fn=_generate_queries_stream,
        description="Generate multiple web-search queries (Stage 1) given a topic and a desired report organization (supports streaming)."
    )
