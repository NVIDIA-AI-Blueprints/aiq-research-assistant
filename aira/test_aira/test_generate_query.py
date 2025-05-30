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
from aiq_aira.functions.generate_queries import AIRAGenerateQueriesConfig
from aiq_aira.schema import GenerateQueryStateInput, GenerateQueryStateOutput, GeneratedQuery
from aiq.data_models.config import AIQConfig
import yaml
import logging

# for some reason I have to manually import these functions for the workflow builder to run 
from aiq_aira.functions import artifact_qa, generate_summary, generate_queries
from aiq_aira import register
from aiq.llm.openai_llm import openai_llm
from aiq.front_ends.fastapi.register import register_fastapi_front_end
from aiq.llm import register  # Import LLM registration module

logger = logging.getLogger(__name__)

# Global test configuration
TEST_RAG_COLLECTION = "Default_Financial"

@pytest.fixture
async def workflow_builder():
    """Fixture to provide a WorkflowBuilder instance with generate_queries configured."""
    config_path = Path(__file__).parent.parent / "configs" / "config.yml"
    with open(config_path, 'r') as file:
        config_dict = yaml.safe_load(file)
        config = AIQConfig.parse_obj(config_dict)
    logger.info(f"Using config from: {config_path}")

    async with WorkflowBuilder.from_config(config=config) as builder:
        yield builder

@pytest.mark.asyncio
async def test_generate_query_basic(workflow_builder):
    """Test basic query generation with default settings."""
    async for builder in workflow_builder:
        workflow = builder.build(entry_function="generate_query")
        
        input_data = GenerateQueryStateInput(
            topic="Impact of AI on Healthcare",
            report_organization="Executive Summary, Key Findings, Future Outlook",
            num_queries=3,
            llm_name="nemotron"
        )
        # Validate the input
        input_data.model_validate(input_data.model_dump())
        
        async with workflow.run(input_data) as runner:
            result = await runner.result()
            assert isinstance(result, GenerateQueryStateOutput)
            assert result.queries is not None
            assert len(result.queries) == 3
            for query in result.queries:
                assert isinstance(query, dict)
                assert "query" in query
                assert "report_section" in query
                assert "rationale" in query

@pytest.mark.asyncio
async def test_generate_query_custom_count(workflow_builder):
    """Test query generation with a custom number of queries."""
    async for builder in workflow_builder:
        workflow = builder.build(entry_function="generate_query")
        
        input_data = GenerateQueryStateInput(
            topic="Impact of AI on Healthcare",
            report_organization="Executive Summary, Key Findings, Future Outlook",
            num_queries=1,
            llm_name="nemotron"
        )
        # Validate the input
        input_data.model_validate(input_data.model_dump())
        
        async with workflow.run(input_data) as runner:
            result = await runner.result()
            assert isinstance(result, GenerateQueryStateOutput)
            assert result.queries is not None
            assert len(result.queries) == 1