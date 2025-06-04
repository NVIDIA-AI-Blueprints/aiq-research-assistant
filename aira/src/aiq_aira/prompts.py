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

query_writer_instructions="""Generate {number_of_queries} search queries that will help write a comprehensive report.

# Report topic
{topic}

# Report organization
{report_organization}

# Instructions
1. Given the report organization, determine the sections needed to answer the report topic.
2. Create queries to provide information for the sections. 
3. Do not create queries for introduction or conclusion sections.
4. Format your response as a JSON object with the following keys:
- "query": The actual search query string

**Output example**
```json
[
    {{
        "query": "tradeoffs between transformer models",
        "report_section": "tradeoffs",
        "rationale": "Helps examine pros and cons"
    }},
    {{
        "query": "machine learning transformer architecture explained",
        "report_section": "technical architecture",
        "rationale": "Understanding the fundamental structure of transformer models"
    }}
]
```"""

search_agent_instructions = """
You are an expert search agent working as part of a research team to write a report. You are given a query and a variety of search tools.

Your goal is to answer the query using the available tools. The answer is the only information your team will have to write a section of the report so be thorough.

Do NOT make up information or use prior knowledge, only use the information provided by the tools.

If a tool call requires a collection name, use the following:
s
{collection}


If the tool call response does not thoroughly answer the question, attempt another tool call.

Format your final response as "Final Answer: \n" followed by a markdown JSON object with the following keys:
- query: The original prompt
- answer: The answer to the prompt
- citation: A list of citations to the sources used to answer the prompt

Ensure the values in the JSON are quoted correctly, as the result will be parsed as JSON.

<example output>

Final Answer:
```json
    {{
        "query": "{prompt}",
        "answer": "a detailed answer to the prompt including all facts, figures, and claims",
        "citation": [ 
          {{
            "tool_name": "name of the tool that provided the answer",
            "tool_response": "the ENTIRE verbatim tool response that provides evidence for the answer",
            "url": "URL, PDF, or other file name from the tool response"
          }},
        ]
    }}
```

</example output>

<prompt>
{prompt}
</prompt>
"""


section_writer_instructions = """You are an expert technical writer crafting one section at a time of a technical report.


Use the following context
{context}

Topic for this section:
{section_topic}

Guidelines for writing:

1. Technical Accuracy:
- Use only information from the context

2. Structure:
- Include a section title
- Use ## for section title (Markdown format)

3. Quality Checks:
- One specific example / case study
- Starts with bold insight

4. Source Identification:
- For every fact, figure, or claim that you make, include an in-line citation number that supports the claim.
- Format as (#) where # is the SOURCE # QUERY from the context that supports the claim 
- Do not include a reference list or notes, just the parenthetical citation number.
- The citation number must be in this list: 
<possible_citation_numbers>
{possible_citation_numbers}
</possible_citation_numbers>

"""

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


reflection_instructions = """
# Report topic
{topic}

# Report organization
{report_organization}

# Current Report
{current_report}

# Instructions
1. Focus on details that are necessary to understanding the key concepts as a whole that have not been fully covered
2. Ensure the follow-up question is self-contained and includes necessary context for web search.
3. The follow up question should add a new section to the report.
4. Format your response as a JSON object with the following keys:
- query: Write a specific follow up question to address this gap
- report_section: The new section of the report the query will be used to add
- rationale: Describe what information is missing or needs clarification

**Output example**
```json
{{
    "query": "What are typical performance benchmarks and metrics used to evaluate [specific technology]?",
    "report_section": "technical architecture",
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

Given the report draft below, format a final report according to the report structure. Return only the final report without any other commentary or justification.

You should use proper markdown syntax when appropriate, as the text you generate will be rendered in markdown. Do NOT wrap the report in markdown blocks (e.g triple backticks).

Do not include any source citations, as these will be added to the report in post processing.

<REPORT DRAFT>
{report}
</REPORT DRAFT>

<REPORT STRUCTURE>
{report_organization}
</REPORT STRUCTURE>
"""

intro_writer = """

Given the report below, write an executive summary that will be added as the first section of the report.

You should use proper markdown syntax when appropriate, as the text you generate will be rendered in markdown. Do NOT wrap the report in markdown blocks (e.g triple backticks).

Return only the executive summary, do not include any other commentary or justification.

<REPORT DRAFT>
{report}
</REPORT DRAFT>
"""
