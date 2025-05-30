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

RELEVANCY_CHECK = """
You are an AI assistant part of a research team. You have a draft research report and access to the data sources for the report. The user will be asking questions about the report and making requests for edits. 

Your job is to determine the user prompt is within scope. If the prompt is not, reply no. If the prompt is in scope, reply yes. Reply using JSON with the format

```json
{{"relevant": "no"}}
```

## Prompt
{prompt}

## Draft Report
{artifact}


Examples:

prompt: what is the report about
response: {{"relevant": "yes"}}

prompt: change the title to be shorter
response: {{"relevant": "yes"}}

prompt: who is the current president
draft report: a report about effective study habits
response: {{"relevant": "no"}}

prompt: tell me more about taiwan 
draft report: a report about effective study habits
response: {{"relevant": "no"}}

prompt: tell me more about taiwan 
draft report: a report about taiwan manufacturing
response: {{"relevant": "yes"}}
"""


UPDATE_ENTIRE_ARTIFACT_PROMPT = f"""You are an AI assistant, and the user has requested you make an update to an artifact you generated in the past.

Here is the current content of the artifact:
<artifact>
{{artifactContent}}
</artifact>

You also have the following reflections on style guidelines and general memories/facts about the user to use when generating your response.
<reflections>
{{reflections}}
</reflections>

Please update the artifact based on the user's request.

Follow these rules and guidelines:
<rules-guidelines>
- You should respond with the ENTIRE updated artifact, with no additional text before and after.
- Do not wrap it in any XML tags you see in this prompt.
- You should use proper markdown syntax when appropriate, as the text you generate will be rendered in markdown. UNLESS YOU ARE WRITING CODE.
- When you generate code, a markdown renderer is NOT used so if you respond with code in markdown syntax, or wrap the code in tipple backticks it will break the UI for the user.
- If generating code, it is imperative you never wrap it in triple backticks, or prefix/suffix it with plain text. Ensure you ONLY respond with the code.
</rules-guidelines>

{{updateMetaPrompt}}

Ensure you ONLY reply with the rewritten artifact and NO other content.
"""