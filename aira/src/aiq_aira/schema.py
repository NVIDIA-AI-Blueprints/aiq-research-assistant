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

import operator
from dataclasses import field
from enum import Enum

from pydantic import BaseModel, Field
from typing_extensions import Annotated, TypedDict
from langchain_openai import ChatOpenAI
from typing import Dict
from dataclasses import dataclass

class GeneratedQuery(BaseModel):
    query: str = Field(..., description="The actual text of the search query")
    report_section: str = Field(..., description="Section of the report this query addresses")
    rationale: str = Field(..., description="Why this query is relevant")


##
# For Stage 1: GenerateQueries
##
class GenerateQueryStateInput(BaseModel):
    topic: str = Field(..., description="Topic to investigate and generate queries for")
    report_organization: str = Field(..., description="Desired structure or constraints for the final report")
    num_queries: int = Field(3, description="Number of queries to generate")
    llm_name: str = Field(..., description="LLM model to use")

class GenerateQueryStateOutput(BaseModel):
    queries: list[Dict] | None = None
    intermediate_step: str | None = None


##
# For Stage 2: GenerateSummary
#  This function will do the web_research + summarization (and optionally reflection/finalization).
##
class GenerateSummaryStateInput(BaseModel):
    topic: str = Field(..., description="Topic of the report")
    report_organization: str = Field(..., description="Desired structure or constraints for the final report")
    queries: list[GeneratedQuery] = Field(..., description="Queries previously generated in Stage 1")
    search_web: bool = Field(..., description="Whether to search the web or not")
    rag_collection: str = Field(..., description="Collection to search for information from")
    reflection_count: int = Field(2, description="Number of reflection loops to run")
    llm_name: str = Field(..., description="LLM model to use")
    # You can add other metadata flags here, e.g. search_web, max_web_research_loops, etc.

class GenerateSummaryStateOutput(BaseModel):
    citations: str | None = Field(None, description="The final list of citations formatted as a string")
    final_report: str | None = Field(None, description="The final summarized report after the entire pipeline (web_research, summarize, reflection, finalize)")
    intermediate_step: str | None = None

##
# For ArtifactQA
##

# Define a new Enum for RewriteMode
class ArtifactRewriteMode(str, Enum):
    """Rewrite modes for the LLM."""
    ENTIRE = "entire"

class ArtifactQAInput(BaseModel):
    """Input data for artifact-based Q&A."""
    artifact: str = Field(..., description="Previously generated artifact (e.g. a report or queries) to reference for Q&A")
    question: str = Field(..., description="User's question about the artifact")
    chat_history: list[str] = Field(default_factory=list, description="Prior conversation turns or context")
    use_internet: bool = Field(False, description="If true, the agent can do additional web or RAG lookups")
    rewrite_mode: ArtifactRewriteMode | None = Field(None, description="Rewrite mode for the LLM")
    additional_context: str | None = Field(None, description="Additional context to provide to the LLM")
    rag_collection: str = Field(..., description="Collection to search for information from")

class ArtifactQAOutput(BaseModel):
    """Output data for artifact-based Q&A."""
    assistant_reply: str = Field(..., description="The agent's answer or response to the question")
    updated_artifact: str | None = Field(None, description="The updated artifact after a rewrite operation")

###
# Main State for the AIRA lang graph
###
@dataclass(kw_only=True)
class AIRAState:
    queries: list[Dict] | None = None    
    web_research_results: list[str] | None = None
    citations: str | None = None
    running_summary: str | None = field(default=None) 
    final_report: str | None = field(default=None)


##
# Graph config typed-dict that we attach to each step
##
class ConfigSchema(TypedDict):
    llm: ChatOpenAI
    report_organization: str
    collection: str 
    number_of_queries: int
    rag_url: str
    num_reflections: int
    search_web: bool
    topic: str
