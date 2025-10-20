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

import html
import re
import yaml
from dataclasses import field, dataclass
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field, field_validator
from typing_extensions import TypedDict
from langchain_openai import ChatOpenAI

# Default prompt injection patterns (used as fallback)
_DEFAULT_BLOCKED_PATTERNS = [
    r'ignore\s+(?:all\s+)?previous\s+instructions',
    r'you\s+are\s+now',
    r'system\s*:',
    r'<\s*system\s*>',
    r'\[system\]',
    r'(?:reveal|show|display|print|give\s+me)\s+(?:me\s+)?(?:the\s+)?(?:api|secret|password|key)',
    r'execute\s+(?:system\s+)?commands?',
    r'run\s+(?:system\s+)?commands?',
    r'delete\s+(?:all\s+)?(?:files?|data|collections?)',
    r'drop\s+table',
    r'union\s+select',
    r'<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>',
    r'javascript:',
    r'eval\s*\(',
    r'exec\s*\(',
]

def _load_blocked_patterns() -> list[str]:
    """Load blocked patterns from security config file with fallback to defaults."""
    config_path = Path(__file__).parent.parent.parent.parent / "configs" / "security_config.yml"
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            return config.get('blocked_patterns', _DEFAULT_BLOCKED_PATTERNS)
    except (FileNotFoundError, yaml.YAMLError):
        return _DEFAULT_BLOCKED_PATTERNS

BLOCKED_PATTERNS = _load_blocked_patterns()

def sanitize_prompt(prompt: str) -> str:
    """
    Validate and sanitize user prompts to mitigate prompt injection attacks.

    Args:
        prompt: User input string to validate and sanitize
        
    Returns:
        Sanitized prompt with HTML special characters escaped
        
    Raises:
        ValueError: If prompt contains blocked text patterns
    """
    if not prompt:
        return prompt

    # Check for known injection patterns before escaping
    prompt_lower = prompt.lower()
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, prompt_lower, re.IGNORECASE):
            raise ValueError("Prompt contains potentially harmful content")

    # Remove common delimiter patterns that could be used for prompt manipulation
    prompt = prompt.replace("---", "")
    prompt = prompt.replace("[SYSTEM]", "[USER_TEXT]")
    
    # HTML-escape special characters to mitigate XSS and markup injection
    # This escapes: < > & " ' and other HTML special characters
    prompt = html.escape(prompt, quote=True)

    return prompt.strip()

class GeneratedQuery(BaseModel):
    """A search query generated for research purposes."""
    query: str = Field(..., description="The actual text of the search query")
    report_section: str = Field(..., description="Section of the report this query addresses")
    rationale: str = Field(..., description="Why this query is relevant")

    @field_validator('query')
    @classmethod
    def validate_query(cls, v):
        """Validate and sanitize the query field."""
        return sanitize_prompt(v)


##
# For Stage 1: GenerateQueries
##
class GenerateQueryStateInput(BaseModel):
    """Input parameters for generating research queries."""
    topic: str = Field(..., description="Topic to investigate and generate queries for")
    report_organization: str = Field(..., description="Desired structure or constraints for the final report")
    num_queries: int = Field(3, description="Number of queries to generate")
    llm_name: str = Field(..., description="LLM model to use")

    @field_validator('topic')
    @classmethod
    def validate_topic(cls, v):
        """Validate and sanitize the topic field."""
        return sanitize_prompt(v)

    @field_validator('report_organization')
    @classmethod
    def validate_report_organization(cls, v):
        """Validate and sanitize the report_organization field."""
        return sanitize_prompt(v)

class GenerateQueryStateOutput(BaseModel):
    """Output containing generated research queries."""
    queries: list[GeneratedQuery] | None = None
    intermediate_step: str | None = None


##
# For Stage 2: GenerateSummary
#  This function will do the web_research + summarization (and optionally reflection/finalization).
##
class GenerateSummaryStateInput(BaseModel):
    """Input parameters for generating research summary reports."""
    topic: str = Field(..., description="Topic of the report")
    report_organization: str = Field(..., description="Desired structure or constraints for the final report")
    queries: list[GeneratedQuery] = Field(..., description="Queries previously generated in Stage 1")
    search_web: bool = Field(..., description="Whether to search the web or not")
    rag_collection: str = Field(..., description="Collection to search for information from")
    reflection_count: int = Field(2, description="Number of reflection loops to run")
    llm_name: str = Field(..., description="LLM model to use")
    # You can add other metadata flags here, e.g. search_web, max_web_research_loops, etc.

class GenerateSummaryStateOutput(BaseModel):
    """Output containing the final research report and citations."""
    citations: str | None = Field(None, description="The final list of citations formatted as a string")
    final_report: str | None = Field(
        None,
        description="The final summarized report after the entire pipeline "
                    "(web_research, summarize, reflection, finalize)"
    )
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
    artifact: str = Field(
        ...,
        description="Previously generated artifact (e.g. a report or queries) to reference for Q&A"
    )
    question: str = Field(..., description="User's question about the artifact")
    chat_history: list[str] = Field(default_factory=list, description="Prior conversation turns or context")
    use_internet: bool = Field(False, description="If true, the agent can do additional web or RAG lookups")
    rewrite_mode: ArtifactRewriteMode | None = Field(None, description="Rewrite mode for the LLM")
    additional_context: str | None = Field(None, description="Additional context to provide to the LLM")
    rag_collection: str = Field(..., description="Collection to search for information from")

    @field_validator('question')
    @classmethod
    def validate_question(cls, v):
        """Validate and sanitize the question field."""
        if not v or not v.strip():
            raise ValueError("Question cannot be empty")
        return sanitize_prompt(v)

    @field_validator('additional_context')
    @classmethod
    def validate_additional_context(cls, v):
        """Validate and sanitize the additional_context field."""
        if v is not None:
            return sanitize_prompt(v)
        return v

    @field_validator('chat_history')
    @classmethod
    def validate_chat_history(cls, v):
        """Validate and sanitize each item in the chat_history field."""
        if v:
            return [sanitize_prompt(item) for item in v]
        return v

class ArtifactQAOutput(BaseModel):
    """Output data for artifact-based Q&A."""
    assistant_reply: str = Field(..., description="The agent's answer or response to the question")
    updated_artifact: str | None = Field(None, description="The updated artifact after a rewrite operation")

###
# Main State for the AIRA lang graph
###
@dataclass(kw_only=True)
class AIRAState:
    """State object for AIRA LangGraph workflow."""
    queries: list[GeneratedQuery] | None = None    
    web_research_results: list[str] | None = None
    citations: str | None = None
    running_summary: str | None = field(default=None) 
    final_report: str | None = field(default=None)


##
# Graph config typed-dict that we attach to each step
##
class ConfigSchema(TypedDict):
    """Configuration schema for AIRA graph execution."""
    llm: ChatOpenAI
    report_organization: str
    collection: str 
    number_of_queries: int
    rag_url: str
    num_reflections: int
    search_web: bool
    topic: str
