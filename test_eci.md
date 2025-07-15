<!--
SPDX-FileCopyrightText: Copyright (c) 2025, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
SPDX-License-Identifier: Apache-2.0

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
-->

# Testing with ECI 

1. Checkout git repo 

```
git clone ssh://git@gitlab-master.nvidia.com:12051/chat-labs/OpenSource/agentiq-blueprint/aiq-bp-internal.git
git fetch origin eci-search && git checkout eci-search
```

2. Create a virtualenv 

```
uv venv --python 3.12
source .venv/bin/activate
```

3. Create a file, test.env with value

```
AIQ_STARFLEET_CLIENT_ID="get-this-from-lopp-or-demoret"
```

4. Create starfleet token

```
uv pip install -r scripts/eci_auth/requirements.txt
uv run --env-file test.env scripts/eci_auth/cli.py --prod starfleet
```

Copy the ID token, set this as the `Authorization` header in requests to a backend that has been deployed with the appropriate SSA client and SSA secret already in place. The authorization header only needs to be on artifact_qa and generate_summary calls, or on ai_researcher calls.

```bash
curl -X POST \
  http://10.57.202.36:3838/generate_summary \
  -H "Content-Type: application/json" \
  -H "Authorization: your-super-long-starfleet-id-token" \
  -d '{
    "topic": "NVIDIA Dynamo",
    "report_organization": "overview and key concepts",
    "queries": [
      {
        "query": "key concepts in NVIDIA dynamo for improving performance in LLM inference",
        "report_section": "overview",
        "rationale": "important"
      }
    ],
    "rag_collection": "fake",
    "reflection_count": 1,
    "llm_name": "nemotron",
    "search_web": true
  }'
```

You can test just ECI results by setting `search_web` to `False` and specifying `rag_collection: ""`. You will see RAG errors that are safe to ignore.