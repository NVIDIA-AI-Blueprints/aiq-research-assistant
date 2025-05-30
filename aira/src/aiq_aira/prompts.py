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

query_writer_instructions="""Generate {number_of_queries} search queries that will help with planning the sections of the final report.

# Report topic
{topic}

# Report organization
{report_organization}

# Instructions
1. Create queries to help answer questions for all sections in report organization.
2. Format your response as a JSON object with the following keys:
- "query": The actual search query string
- "report_section": The section of report organization the query is generated for
- "rationale": Brief explanation of why this query is relevant to report organization

**Output example**
```json
[
    {{
        "query": "What is a transformer?",
        "report_section": "Introduction",
        "rationale": "Introduces the user to transformer"
    }},
    {{
        "query": "machine learning transformer architecture explained",
        "report_section": "technical architecture",
        "rationale": "Understanding the fundamental structure of transformer models"
    }}
]
```"""

summarizer_instructions="""Generate a high-quality report from the given sources. 

# Report organization
{report_organization}

# Knowledge Sources
{source}

# Instructions
1. Stick to the sections outlined in report organization
2. Highlight the most relevant pieces of information across all sources
3. Provide a concise and comprehensive overview of the key points related to the report topic
4. Focus the bulk of the analysis on the most significant findings or insights
5. Ensure a coherent flow of information
6. You should use proper markdown syntax when appropriate, as the text you generate will be rendered in markdown. Do NOT wrap the report in markdown blocks (e.g triple backticks).
7. Start report with a title
8. Do not include any source citations, as these will be added to the report in post processing.
"""


report_extender = """Add to the existing report additional sources preserving the current report structure (sections, headings etc).

# Draft Report
{report}

# New Knowledge Sources
{source}

# Instructions
1. Copy the original report title
2. Preserve the report structure (sections, headings etc)
3. Seamlessly add information from the new sources.
4. Do not include any source citations, as these will be added to the report in post processing.
"""


reflection_instructions = """Using report organization as a guide identify knowledge gaps and/or areas that have not been addressed comprehensively in the report.

# Report topic
{topic}

# Report organization
{report_organization}

# Draft Report
{report}

# Instructions
1. Focus on details that are necessary to understanding the key concepts as a whole that have not been fully covered
2. Ensure the follow-up question is self-contained and includes necessary context for web search.
3. Format your response as a JSON object with the following keys:
- query: Write a specific follow up question to address this gap
- report_section: The section of report the query is for
- rationale: Describe what information is missing or needs clarification

**Output example**
```json
{{
    "query": "What are typical performance benchmarks and metrics used to evaluate [specific technology]?"
    "report_section": "Deep dive",
    "rationale": "The report lacks information about performance metrics and benchmarks"
}}
```"""


relevancy_checker = """Determine if the Context contains proper information to answer the Question.

# Question
{query}

# Context
{document}

# Instructions
1. Give a binary score 'yes' or 'no' to indicate whether the context is able to answer the question.

**Output example**
```json
{{
    "score": "yes"
}}
```"""

finalize_report = """

Given the report draft below, format a final report according to the report structure.

Do not add a sources section, sources are added in post processing. 

You should use proper markdown syntax when appropriate, as the text you generate will be rendered in markdown. Do NOT wrap the report in markdown blocks (e.g triple backticks).

Return only the final report without any other commentary or justification.

<REPORT DRAFT>
{report}
</REPORT DRAFT>

<REPORT STRUCTURE>
{report_organization}
</REPORT STRUCTURE>
"""
