# SPDX-FileCopyrightText: Copyright (c) 2025, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
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

from typing import Optional

from pydantic import BaseModel


class AIResearcherEvalInput(BaseModel):
    id: str
    topic: str
    report_organization: str
    search_web: bool
    rag_collection: str
    num_queries: int
    llm_name: str
    reflection_count: int
    ground_truth: str
    context_relevance_questions: Optional[list[dict]] = []
    coverage_facts_claims: Optional[list[str]] = []


class AIResearcherEvalOutput(AIResearcherEvalInput):
    queries: Optional[list[dict]] = []
    rag_contexts: Optional[list[dict]] = []
    relevancy_judgements: Optional[list] = []
    web_answers: Optional[list] = []
    queries_from_reflections: Optional[list] = []
    reflections: Optional[list] = []
    finalized_summary: Optional[str] = ""
    citation_section: Optional[str] = ""
    groundness_facts_claims: Optional[list[str]] = []
    fact_citation_pairs: Optional[list[tuple[str, list[int]]]] = []
