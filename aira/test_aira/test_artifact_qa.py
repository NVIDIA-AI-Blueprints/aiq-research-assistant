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
from aiq_aira.functions.artifact_qa import ArtifactQAConfig
from aiq_aira.schema import ArtifactQAInput, ArtifactQAOutput, ArtifactRewriteMode
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

# Test artifacts
SAMPLE_TEXT_ARTIFACT = """
# Healthcare Innovation Report

## Executive Summary
The healthcare sector is experiencing rapid technological advancements.
"""

@pytest.fixture
async def workflow_builder():
    """Fixture to provide a WorkflowBuilder instance with artifact_qa configured."""
    config_path = Path(__file__).parent.parent / "configs" / "config.yml"
    with open(config_path, 'r') as file:
        config_dict = yaml.safe_load(file)
        config = AIQConfig.parse_obj(config_dict)
    logger.info(f"Using config from: {config_path}")

    async with WorkflowBuilder.from_config(config=config) as builder:
        yield builder

@pytest.mark.asyncio
async def test_artifact_qa_basic_qa(workflow_builder):
    """Test basic Q&A functionality without any rewrite mode."""
    async for builder in workflow_builder:
        workflow = builder.build(entry_function="artifact_qa")
        
        input_data = ArtifactQAInput(
            artifact=SAMPLE_TEXT_ARTIFACT,
            question="What is the main topic of this report?",
            chat_history=[],
            use_internet=False,
            rag_collection=TEST_RAG_COLLECTION
        )
        # Validate the input
        input_data.model_validate(input_data.model_dump())
        
        async with workflow.run(input_data) as runner:
            result = await runner.result()
            assert isinstance(result, ArtifactQAOutput)
            assert result.updated_artifact == SAMPLE_TEXT_ARTIFACT
            assert "healthcare" in result.assistant_reply.lower()

@pytest.mark.asyncio
async def test_artifact_qa_entire_rewrite(workflow_builder):
    """Test rewriting the entire artifact."""
    async for builder in workflow_builder:
        workflow = builder.build(entry_function="artifact_qa")
        
        input_data = ArtifactQAInput(
            artifact=SAMPLE_TEXT_ARTIFACT,
            question="Make this report more technical and detailed",
            chat_history=[],
            use_internet=False,
            rewrite_mode=ArtifactRewriteMode.ENTIRE,
            rag_collection=TEST_RAG_COLLECTION
        )
        # Validate the input
        input_data.model_validate(input_data.model_dump())
        
        async with workflow.run(input_data) as runner:
            result = await runner.result()
            assert isinstance(result, ArtifactQAOutput)
            assert result.updated_artifact != SAMPLE_TEXT_ARTIFACT
            assert "Here is the updated artifact (entire rewrite)" in result.assistant_reply

@pytest.mark.asyncio
async def test_artifact_qa_highlighted_rewrite(workflow_builder):
    """Test rewriting only highlighted portions of the artifact."""
    async for builder in workflow_builder:
        workflow = builder.build(entry_function="artifact_qa")
        
        input_data = ArtifactQAInput(
            artifact=SAMPLE_TEXT_ARTIFACT,
            question="Make the executive summary more concise",
            chat_history=[],
            use_internet=False,
            rewrite_mode=ArtifactRewriteMode.HIGHLIGHTED,
            additional_context="## Executive Summary",
            rag_collection=TEST_RAG_COLLECTION
        )
        # Validate the input
        input_data.model_validate(input_data.model_dump())
        
        async with workflow.run(input_data) as runner:
            result = await runner.result()
            assert isinstance(result, ArtifactQAOutput)
            assert "Updated only the highlighted part" in result.assistant_reply

@pytest.mark.asyncio
async def test_artifact_qa_highlighted_rewrite_empty_context(workflow_builder):
    """Test rewriting with HIGHLIGHTED mode but empty additional context."""
    async for builder in workflow_builder:
        workflow = builder.build(entry_function="artifact_qa")
        
        input_data = ArtifactQAInput(
            artifact=SAMPLE_TEXT_ARTIFACT,
            question="Make this more concise",
            chat_history=[],
            use_internet=False,
            rewrite_mode=ArtifactRewriteMode.HIGHLIGHTED,
            additional_context="",  # Empty context
            rag_collection=TEST_RAG_COLLECTION
        )
        # Validate the input
        input_data.model_validate(input_data.model_dump())
        
        async with workflow.run(input_data) as runner:
            result = await runner.result()
            assert isinstance(result, ArtifactQAOutput)
            assert result.updated_artifact == SAMPLE_TEXT_ARTIFACT
