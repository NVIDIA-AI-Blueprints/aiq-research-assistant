import typing
from typing import AsyncGenerator
import json

from aiq.data_models.api_server import AIQChatResponseChunk
from aiq.data_models.component_ref import LLMRef
from aiq.data_models.function import FunctionBaseConfig
from aiq.builder.builder import Builder
from aiq.cli.register_workflow import register_function
from aiq.builder.function_info import FunctionInfo
from aiq.builder.framework_enum import LLMFrameworkEnum
import json

from aiq_aira.nodes import web_research, summarize_sources, reflect_on_summary, finalize_summary, check_final_summary
from aiq_aira.schema import (
    ConfigSchema,
    GenerateSummaryStateInput,
    GenerateSummaryStateOutput,
    AIRAState
)
from langchain_core.runnables import RunnableConfig
from langgraph.graph import START, END, StateGraph

def serialize_pydantic(obj):
    if isinstance(obj, list):
        return [serialize_pydantic(item) for item in obj]
    elif isinstance(obj, dict):
        return {key: serialize_pydantic(value) for key, value in obj.items()}
    elif hasattr(obj, "model_dump"):  # Pydantic v2
        return obj.model_dump()
    elif hasattr(obj, "dict"):  # Pydantic v1
        return obj.dict()
    else:
        return obj

class AIRAGenerateSummaryConfig(FunctionBaseConfig, name="generate_summaries"):
    """
    Configuration for the generate_summary function/endpoint
    """
    rag_url: str = ""
    max_tool_calls: int = 3
    tool_names: list[str] = []
def serialize_pydantic(obj):
    if isinstance(obj, list):
        return [serialize_pydantic(item) for item in obj]
    elif isinstance(obj, dict):
        return {key: serialize_pydantic(value) for key, value in obj.items()}
    elif hasattr(obj, "model_dump"):  # Pydantic v2
        return obj.model_dump()
    elif hasattr(obj, "dict"):  # Pydantic v1
        return obj.dict()
    else:
        return obj

@register_function(config_type=AIRAGenerateSummaryConfig)
async def generate_summary_fn(config: AIRAGenerateSummaryConfig, aiq_builder: Builder):
    """
    The main function for research, report writing, and reflection to generate a report, representing /generate_summary in config.yml
    """

    # Build the Stage 2 pipeline
    builder = StateGraph(
        AIRAState,
        config_schema=ConfigSchema
    )
    builder.add_node("web_research", web_research)
    builder.add_node("summarize_sources", summarize_sources)
    builder.add_node("finalize_summary", finalize_summary)
    builder.add_node("reflect_on_summary", reflect_on_summary)


    builder.add_edge(START, "web_research")
    builder.add_edge("web_research", "summarize_sources")
    builder.add_conditional_edges("summarize_sources", check_final_summary, {
        "finalize_summary": "finalize_summary",
        "reflect_on_summary": "reflect_on_summary"
    })
    builder.add_edge("reflect_on_summary", "web_research")
    builder.add_edge("finalize_summary", END)

    graph = builder.compile()

    

    # ------------------------------------------------------------------
    # SINGLE-OUTPUT
    # ------------------------------------------------------------------
    async def _generate_summary_single(message: GenerateSummaryStateInput) -> GenerateSummaryStateOutput:
        """
        Runs the entire pipeline to produce a final summarized report
        """
        writer_llm = await aiq_builder.get_llm(llm_name="instruct", wrapper_type=LLMFrameworkEnum.LANGCHAIN)
        search_agent = aiq_builder.get_tool(fn_name="search_agent", wrapper_type=LLMFrameworkEnum.LANGCHAIN)
        llm = await aiq_builder.get_llm(llm_name=message.llm_name, wrapper_type=LLMFrameworkEnum.LANGCHAIN)
        response: AIRAState = await graph.ainvoke(
            input={"queries": message.queries, "research_results": [], "current_report": ""},
            config={
                "llm": llm,
                "writer_llm": writer_llm,
                "search_agent": search_agent,
                "max_tool_calls": config.max_tool_calls,
                "report_organization": message.report_organization,
                "collection": message.rag_collection,
                "num_reflections": message.reflection_count, 
                "topic": message.topic,
            }
        )
        return GenerateSummaryStateOutput(final_report=response["final_report"], citations="")

    # ------------------------------------------------------------------
    # STREAMING VERSION
    # ------------------------------------------------------------------
    async def _generate_summary_stream(
            message: GenerateSummaryStateInput
    ) -> AsyncGenerator[GenerateSummaryStateOutput, None]:
        """
        Runs the entire pipeline to produce a final summarized report, streaming the response
        """
        # Acquire the LLM from the builder
        llm = await aiq_builder.get_llm(llm_name=message.llm_name, wrapper_type=LLMFrameworkEnum.LANGCHAIN)
        writer_llm = await aiq_builder.get_llm(llm_name="instruct", wrapper_type=LLMFrameworkEnum.LANGCHAIN)
        search_agent = aiq_builder.get_tool(fn_name="search_agent", wrapper_type=LLMFrameworkEnum.LANGCHAIN)
       
        async for _t, val in graph.astream(
                input={"queries": message.queries, "research_results": [], "current_report": ""},
                stream_mode=['custom', 'values'],
                config={
                    "llm": llm,
                    "report_organization": message.report_organization,
                    "max_tool_calls": config.max_tool_calls,
                    "writer_llm": writer_llm,
                    "search_agent": search_agent,
                    "collection": message.rag_collection,
                    "topic": message.topic,
                    "num_reflections": message.reflection_count, 
                    "recursion_limit": 250
                }
        ):

            if _t == "values":
                if "final_report" not in val:
                    yield GenerateSummaryStateOutput(intermediate_step=json.dumps(serialize_pydantic(val)))
                else:
                    yield GenerateSummaryStateOutput(final_report=val["final_report"], citations="")
            else:
                yield GenerateSummaryStateOutput(intermediate_step=json.dumps(serialize_pydantic(val)))


    # Instead of from_fn(...), provide both single & stream versions:
    yield FunctionInfo.create(
        single_fn=_generate_summary_single,
        stream_fn=_generate_summary_stream,
        description="Generates a full summary by doing research, summarizing, reflecting, and finalizing the report (supports streaming)."
    )

