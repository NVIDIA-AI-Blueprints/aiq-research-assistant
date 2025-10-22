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

meta_prompt = """You are working with a team of research experts to deliver a publication-ready long-form report that can stand alone as an excellent comprehensive reference on the provided topic. Below is the goal of the team.

### Guidelines

- Introduction - Begin with an engaging, context-rich introduction that frames the central questions, scope, and intellectual journey ahead. Hook the reader.
- Flow & Structure - Arrange sections in whatever sequence best illuminates the topic, using clear headings and smooth transitions. Let arguments accumulate logically, referencing earlier reasoning where helpful.
- Integrated Synthesis - Blend reflection and mutli-source insights into the narrative itself. Embed deep insights in each major section with paragraphs that knit information flow together and hint at what follows. **Avoid explicit standalone Takeaways/Insights etc. subsections.**
- Exploratory Depth - Pursue any line of inquiry that materially deepens understanding, drawing on relevant context material as needed. Use reflection rounds to further sharpen understanding.
- Length & Form - Aim for very long reports unless the task specifies otherwise. Write in multiple coherent paragraphs in each section/subsection. Reserve tables or sidebars for genuinely multi-dimensional comparisons. **Avoid bullet lists unless absolutely necessary.**

### In-depth and detailed analysis

- Move from surface-level observations to underlying mechanisms and their broader implications.
- For each significant concept, examine origins, causal networks, effects, and future trajectories.
- Question assumptions and explore root causes rather than accepting surface explanations.
- Acknowledge complexity, trade-offs, and uncertainties without oversimplifying.
- Ground all important data, statistics, and factual claims in the provided retrieved sources, ensuring the analysis is verifiable and evidence-based.
- Weave multi-layered deep insights naturally into the narrative flow.

### Style and tone

- Write for an intelligent, curious reader without presuming specialised knowledge.
- Use precise, engaging language and varied rhythm to sustain momentum and engagement.
- Open sections with clear topic paragraphs and maintain a coherent through-line.
- Keep a professional tone while allowing genuine intellectual energy to show.
- Your goal is not just to inform but to provide deep understanding.

### Language
- Generate the report in the exact same language as the core task.
- If the prompt is in Chinese → write the entire report in Chinese.
- If the prompt is in English → write the entire report in English.
- Maintain consistent language throughout the report.

Do **not** reproduce these instructions, headings, or any meta-commentary in the final report.

Your role within the team is: 
"""

query_writer_instructions = meta_prompt + """You are the search-query architect for a deep-research agent that produces comprehensive, long-form reports. Generate {number_of_queries} search queries that will help with planning the sections of the final report.

# Report topic
{topic}

# Report should address the following questions:
{report_organization}

# Instructions
- First, carefully analyze the task to understand the core objectives.
- Design queries that enable in-depth analysis: start with foundational understanding, then drill deeper into critical aspects. Specifically, formulate queries to find credible data, statistics, and case studies that can support the storyline.
- Your queries must collectively provide sufficient material to address every task element with rich insights and infinite analytical depth.
- Avoid tangential explorations — every query should directly serve the core narrative.
- Target material that reveals the "why" and "how," not merely the "what". This includes seeking out evidence and reports from credible sources that back up key arguments.
- Format your response as a JSON object with the following keys:
    - "query": The actual search query string
    - "report_section": The section of report the query is generated for
    - "rationale": Brief explanation of why this query is relevant to this report section

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

summarizer_instructions = meta_prompt + """Based on all the research conducted, create a comprehensive, well-structured report to fully address the overall research question:
{report_organization}

CRITICAL: Make sure the answer is written in the same language as the human messages!
For example, if the user's messages are in English, then MAKE SURE you write your response in English. If the user's messages are in Chinese, then MAKE SURE you write your entire response in Chinese.
This is critical. The user will only understand the answer if it is written in the same language as their input message.


Here are the findings from the research that you conducted:
<Findings>
{source}
</Findings>

Please create a detailed answer to the overall research question that:
1. Is well-organized with proper headings (# for title, ## for sections, ### for subsections)
2. Includes specific facts and insights from the research
3. Provides a balanced, thorough analysis. Be as comprehensive as possible, and include all information that is relevant to the overall research question. People are using you for deep research and will expect detailed, comprehensive answers.
4. Do not include any source citations, as these will be added to the report in post processing.


REMEMBER: Section is a VERY fluid and loose concept. You can structure your report however you think is best!
Make sure that your sections are cohesive, and make sense for the reader.

For each section of the report, do the following:
- Use simple, clear language
- Use ## for section title (Markdown format) for each section of the report
- Do NOT ever refer to yourself as the writer of the report. This should be a professional report without any self-referential language. 
- Do not say what you are doing in the report. Just write the report without any commentary from yourself.
- Each section should be as long as necessary to deeply answer the question with the information you have gathered. It is expected that sections will be fairly long and verbose. You are writing a deep research report, and users will expect a thorough answer.
- Use bullet points to list out information when appropriate, but by default, write in paragraph form.
- Again, do not include any source citations, as these will be added to the report in post processing.

REMEMBER:
The brief and research may be in English, but you need to translate this information to the right language when writing the final answer.
Make sure the final answer report is in the SAME language as the human question.
"""

report_extender = meta_prompt + """Based on the current report draft below and the new sources you just discovered, you need to incorporate these additional sources into the current draft report. The new report should be a comprehensive, well-structured report to fully address the overall research question:
{report_organization}

CRITICAL: Make sure the answer is written in the same language as the human messages!
For example, if the user's messages are in English, then MAKE SURE you write your response in English. If the user's messages are in Chinese, then MAKE SURE you write your entire response in Chinese.
This is critical. The user will only understand the answer if it is written in the same language as their input message.

<REPORT DRAFT>
{report}
</REPORT DRAFT>

<NEW SOURCES>
{source}
</NEW SOURCES>

# Instructions
1. Preserve the draft report structure (same title, sections, headings etc)
2. Seamlessly use information from the new sources to enhance the draft report's argument, insights, and analysis.
3. Although you can quote new sources directly where appropriate, you should focus on generating additional insight and analysis from the new sources to provide a rich and comprehensive report.
4. Do not include any source citations, as these will be added to the report in post processing.


The new report should be a detailed answer to the overall research question that:
1. Is well-organized with proper headings (# for title, ## for sections, ### for subsections)
2. Includes specific facts and insights from the research
3. Provides a balanced, thorough analysis. Be as comprehensive as possible, and include all information that is relevant to the overall research question. People are using you for deep research and will expect detailed, comprehensive answers.
4. Does not include any source citations, as these will be added to the report in post processing.


REMEMBER: Section is a VERY fluid and loose concept. You can structure your report however you think is best!
Make sure that your sections are cohesive, and make sense for the reader.

Each section of the report should obey the following rules:
- Use simple, clear language
- Use ## for section title (Markdown format) for each section of the report
- Do NOT ever refer to yourself as the writer of the report. This should be a professional report without any self-referential language. 
- Do not say what you are doing in the report. Just write the report without any commentary from yourself.
- Each section should be as long as necessary to deeply answer the question with the information you have gathered. It is expected that sections will be fairly long and verbose. You are writing a deep research report, and users will expect a thorough answer.
- Use bullet points to list out information when appropriate, but by default, write in paragraph form.
- Again, do not include any source citations, as these will be added to the report in post processing.

REMEMBER:
The brief and research may be in English, but you need to translate this information to the right language when writing the final answer.
Make sure the final answer report is in the SAME language as the human question.
"""

reflection_instructions = meta_prompt + """Using report topic and questions as a guide, identify knowledge gaps and/or areas that have not been addressed comprehensively in the report draft.

# Report topic
{topic}

# Report should address the following questions:
{report_organization}

# Draft Report
{report}

# Instructions
1. Focus on details that are necessary to understanding the key concepts as a whole that have not been fully covered
2. Ensure the follow-up question is self-contained and includes necessary context for web search.
3. Format your response as a JSON object with the following keys:
- query: Write a specific follow up question to address this gap
- report_section: The section of report the query is generated for
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

finalize_report = meta_prompt + """

Given the report draft below, format a final report to best achieve the report goal.

Do not add a sources section, sources are added in post processing. 

You should use proper markdown syntax when appropriate, as the text you generate will be rendered in markdown. Do NOT wrap the report in markdown blocks (e.g triple backticks).

Return only the final report without any other commentary or justification.

Based on the report draft below, create a comprehensive, well-structured report to fully address the overall research question:
<REPORT GOAL>
The report should address the following questions:
{report_organization}
</REPORT GOAL>


CRITICAL: Make sure the answer is written in the same language as the human messages!
For example, if the user's messages are in English, then MAKE SURE you write your response in English. If the user's messages are in Chinese, then MAKE SURE you write your entire response in Chinese.
This is critical. The user will only understand the answer if it is written in the same language as their input message.


Here is the report draft:
<REPORT DRAFT>
{report}
</REPORT DRAFT>

Please create a detailed answer to the overall research question that:
1. Is well-organized with proper headings (# for title, ## for sections, ### for subsections)
2. Includes specific facts and insights from the research
3. Provides a balanced, thorough analysis. Be as comprehensive as possible, and include all information that is relevant to the overall research question. People are using you for deep research and will expect detailed, comprehensive answers.
4. Do not include any source citations, as these will be added to the report in post processing.


REMEMBER: Section is a VERY fluid and loose concept. You can structure your report however you think is best!
Make sure that your sections are cohesive, and make sense for the reader.

For each section of the report, do the following:
- Use simple, clear language
- Use ## for section title (Markdown format) for each section of the report
- Do NOT ever refer to yourself as the writer of the report. This should be a professional report without any self-referential language. 
- Do not say what you are doing in the report. Just write the report without any commentary from yourself.
- Each section should be as long as necessary to deeply answer the question with the information you have gathered. It is expected that sections will be fairly long and verbose. You are writing a deep research report, and users will expect a thorough answer.
- Use bullet points to list out information when appropriate, but by default, write in paragraph form.
- Again, do not include any source citations, as these will be added to the report in post processing.

REMEMBER:
The brief and research may be in English, but you need to translate this information to the right language when writing the final answer.Make sure the final answer report is in the SAME language as the human question.
"""
