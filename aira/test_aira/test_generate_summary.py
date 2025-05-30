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

import pytest
from pathlib import Path
from aiq.builder.workflow_builder import WorkflowBuilder
from aiq_aira.schema import GenerateSummaryStateInput, GenerateSummaryStateOutput, GeneratedQuery
from aiq.data_models.config import AIQConfig
import yaml
import logging
import json

# for some reason I have to manually import these functions for the workflow builder to run 
from aiq_aira.functions import artifact_qa, generate_summary, generate_queries
from aiq_aira import register
from aiq.llm.openai_llm import openai_llm
from aiq.front_ends.fastapi.register import register_fastapi_front_end
from aiq.llm import register  # Import LLM registration module

logger = logging.getLogger(__name__)

# Global test configuration
TEST_RAG_COLLECTION = "Default_Financial"

# Sample queries for testing
SAMPLE_QUERIES = [
    GeneratedQuery(
        query="Amazon 2023 Annual Report Summary official release",
        report_section="Introduction",
        rationale="Provides an overview of Amazon's 2023 financial highlights and business segments for contextualizing the report."
    ),
    GeneratedQuery(
        query="Amazon Q1-Q4 2023 revenue growth trend analysis",
        report_section="Revenue Growth",
        rationale="Helps identify quarterly revenue patterns and year-over-year changes to assess growth consistency."
    ),
    # one query that wont be in rag results
    GeneratedQuery(
        query="List of big mac ingredients",
        report_section="test web search",
        rationale="test rag irrelevant"
    )
]

@pytest.fixture
async def workflow_builder():
    """Fixture to provide a WorkflowBuilder instance with generate_summary configured."""
    config_path = Path(__file__).parent.parent / "configs" / "config.yml"
    with open(config_path, 'r') as file:
        config_dict = yaml.safe_load(file)
        config = AIQConfig.parse_obj(config_dict)
    logger.info(f"Using config from: {config_path}")

    async with WorkflowBuilder.from_config(config=config) as builder:
        yield builder

@pytest.mark.asyncio
async def test_generate_summary_basic(workflow_builder):
    """Test basic summary generation with web research enabled."""
    async for builder in workflow_builder:
        workflow = builder.build(entry_function="generate_summary")
        
        input_data = GenerateSummaryStateInput(
            topic="Comprehensive Financial Report",
            report_organization="You are a financial analyst who specializes in financial statement analysis. Write a financial report analyzing the 2023 financial performance of Amazon. Identify trends in revenue growth, net income, and total assets. Discuss how these trends affected Amazon's yearly financial performance for 2023. Your output should be organized into a brief introduction, as many sections as necessary to create a comprehensive report, and a conclusion. Format your answer in paragraphs. Use factual sources such as Amazon's quarterly meeting releases for 2023. Cross analyze the sources to draw original and sound conclusions and explain your reasoning for arriving at conclusions. Do not make any false or unverifiable claims. I want a factual report with cited sources.",
            queries=SAMPLE_QUERIES,
            search_web=True,
            rag_collection=TEST_RAG_COLLECTION,
            reflection_count=2,
            llm_name="nemotron"
        )
        # Validate the input
        input_data.model_validate(input_data.model_dump())
        
        # Capture intermediate results
        intermediate_results = []
        final_result = None
        
        async with workflow.run(input_data) as runner:
            # Collect intermediate results from the stream
            async for intermediate in runner.result_stream():
                intermediate_results.append(intermediate)
                # If this is the final result, capture it
                if intermediate.final_report is not None:
                    final_result = intermediate
        
        # Verify we got intermediate results
        assert len(intermediate_results) > 0
        # Verify the progression of intermediate steps
        assert any("web_answer" in r.intermediate_step.lower() for r in intermediate_results if r.intermediate_step)
        assert any("rag_answer" in r.intermediate_step.lower() for r in intermediate_results if r.intermediate_step)
        assert any("summarize_sources" in r.intermediate_step.lower() for r in intermediate_results if r.intermediate_step)
        assert any("reflect_on_summary" in r.intermediate_step.lower() for r in intermediate_results if r.intermediate_step)
        assert any("final_report" in r.intermediate_step.lower() for r in intermediate_results if r.intermediate_step)
        assert any("relevancy_checker" in r.intermediate_step.lower() for r in intermediate_results if r.intermediate_step)
        
        # Verify final result
        assert final_result is not None
        assert isinstance(final_result, GenerateSummaryStateOutput)
        assert final_result.final_report is not None
        assert final_result.citations is not None
        
        # verify sections of the final report 
        report = final_result.final_report.lower()
        assert "introduction" in report
        assert "conclusion" in report
        assert "sources" in report

@pytest.mark.asyncio
async def test_generate_summary_no_web(workflow_builder):
    """Test summary generation without web research."""
    async for builder in workflow_builder:
        workflow = builder.build(entry_function="generate_summary")
        
        input_data = GenerateSummaryStateInput(
            topic="Renewable Energy Technologies",
            report_organization="Current State, Challenges, Solutions",
            queries=SAMPLE_QUERIES,
            search_web=False,
            rag_collection=TEST_RAG_COLLECTION,
            reflection_count=1,
            llm_name="nemotron"
        )
        # Validate the input
        input_data.model_validate(input_data.model_dump())
        
        # Capture intermediate results
        intermediate_results = []
        final_result = None
        
        async with workflow.run(input_data) as runner:
            # Collect intermediate results from the stream
            async for intermediate in runner.result_stream():
                intermediate_results.append(intermediate)
        
        # Verify we got intermediate results
        assert len(intermediate_results) > 0
        
        # Verify no web research steps occurred
        assert not any("web_answer" in r.intermediate_step.lower() for r in intermediate_results if r.intermediate_step)

        