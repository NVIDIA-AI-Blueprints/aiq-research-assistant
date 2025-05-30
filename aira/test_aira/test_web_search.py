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

import pytest_asyncio
import asyncio
import json
from unittest.mock import patch
from aiohttp import web, ClientSession
from aiohttp import ClientSession
from urllib.parse import urljoin
from langchain_openai import ChatOpenAI
import os
import pytest
import io
import json
from pathlib import Path
from aiq_aira.nodes import web_research
from aiq_aira.schema import ConfigSchema, GeneratedQuery
from aiq_aira.schema import AIRAState
from aiq_aira.functions.generate_summary import GenerateSummaryStateInput, AIRAGenerateSummaryConfig

@pytest.fixture(scope="session")
def reasoning_llm():
    key = os.getenv("OPENAI_API_KEY")
    print(f"USING KEY: {key}")
    llm = ChatOpenAI(
        #model="stg/nvidia/llama-3.3-nemotron-super-49b-v1",
        model="stg/deepseek-ai/deepseek-r1",
        temperature=0.6,
        base_url="https://integrate.api.nvidia.com/v1",
        openai_api_key=key,
        streaming=True
    )
    return llm



# piece together all the input config classes the same way AIQ does
generate_summary_user_post_input = GenerateSummaryStateInput(
    topic="NVIDIA Earnings",
    report_organization="Can you create a detailed report on NVIDIA's 2025 earnings that covers its key financial numbers, market and competition factors, tech investments, global economic and political trends, and future outlook using the provided docs and data visuals?",
    queries=[
        GeneratedQuery(
            query="nvidia earnings",
            report_section="main body",
            rationale="its important"
        ), 
        GeneratedQuery(
            query="nvidia competitors",
            report_section="conclusion",
            rationale="other information"
        )
    ],
    reflection_count=1,
    search_web=False,
    rag_collection="user_passed_collection",
    llm_name="not-used-here" # llm name used by aiq builder, but llm is directly initalized here as test fixture
)


aira_state = AIRAState(
    queries=generate_summary_user_post_input.queries
)


@pytest_asyncio.fixture
async def mock_rag_relevant(aiohttp_client):
    async def handler(request):
        
        data = await request.json()

        # Validation
        assert data["collection_name"] is not None
        assert data["collection_name"]=="user_passed_collection", f"Got collection: {data["collection_name"]} but expected user_passed_collection"
        assert isinstance(data["messages"][0]["content"], str)
        p = Path(__file__).parent.joinpath("rag_response_relevant.json")
        with open(p, "r") as f:
            responses = json.load(f)
        
        response = web.StreamResponse()
        response.content_type = 'text/event-stream'  # Set content type for SSE
        await response.prepare(request)

        for resp in responses:
            await response.write(f"data: {json.dumps(resp)}\n\n".encode('utf-8'))
            await asyncio.sleep(0.01) #simulate network delay

        return response

    app = web.Application()
    app.add_routes([web.post("/generate", handler)])
    return await aiohttp_client(app)

@pytest_asyncio.fixture
async def mock_rag_not_relevant(aiohttp_client):
    async def handler(request):
        
        data = await request.json()

        # Validation
        assert data["collection_name"] is not None
        assert data["collection_name"]=="user_passed_collection", f"Got collection: {data["collection_name"]} but expected user_passed_collection"
        assert isinstance(data["messages"][0]["content"], str)

        p = Path(__file__).parent.joinpath("rag_response_not_relevant.json")
        with open(p, "r") as f:
            responses = json.load(f)
        
        return web.json_response(responses)
    

    app = web.Application()
    app.add_routes([web.post("/generate", handler)])
    return await aiohttp_client(app)


@pytest_asyncio.fixture
async def mock_rag_not_running(aiohttp_client):
    async def handler(request):
        
        data = await request.json()

        # Validation
        assert data["collection_name"] is not None
        assert data["collection_name"]=="user_passed_collection", f"Got collection: {data["collection_name"]} but expected user_passed_collection"
        assert isinstance(data["messages"][0]["content"], str)
   
        return web.Response(status=500, text="Internal Server Error")

    app = web.Application()
    app.add_routes([web.post("/generate", handler)])
    return await aiohttp_client(app)

@pytest.mark.asyncio
async def test_web_research_relevant(mock_rag_relevant, reasoning_llm, capsys):
    mock_server = mock_rag_relevant
    url = str(mock_server.make_url("/")) 

    aira_config = AIRAGenerateSummaryConfig(
        rag_url=url
    )

    user_input_passed_as_langchain_config = ConfigSchema(
        llm=reasoning_llm,
        report_organization=generate_summary_user_post_input.report_organization,
        topic=generate_summary_user_post_input.topic,
        collection=generate_summary_user_post_input.rag_collection,
        rag_url=aira_config.rag_url,
        search_web=generate_summary_user_post_input.search_web
    )

    async with ClientSession() as session:
        
        result = await web_research(aira_state,
                 {"configurable": user_input_passed_as_langchain_config}, 
                 print
        )

        aira_stream_results = capsys.readouterr()
        print(aira_stream_results.out)
        assert "citations" in result
        citations = result["citations"] 
        citation_list = citations.split("\n")
        assert len(citation_list) == 15 # based on the rag_response_relevant.json file
        assert "web_research_results" in result
        assert "{'score': 'yes'}" in aira_stream_results.out  
    

@pytest.mark.asyncio
async def test_web_research_not_relevant(mock_rag_not_relevant, reasoning_llm, capsys):
    mock_server = mock_rag_not_relevant
    url = str(mock_server.make_url("/")) 

    aira_config = AIRAGenerateSummaryConfig(
        rag_url=url
    )

    user_input_passed_as_langchain_config = ConfigSchema(
        llm=reasoning_llm,
        report_organization=generate_summary_user_post_input.report_organization,
        topic=generate_summary_user_post_input.topic,
        collection=generate_summary_user_post_input.rag_collection,
        rag_url=aira_config.rag_url,
        search_web=generate_summary_user_post_input.search_web
    )

    async with ClientSession() as session:
        
        result = await web_research(aira_state,
                 {"configurable": user_input_passed_as_langchain_config}, 
                 print
        )

        aira_stream_results = capsys.readouterr()
        print(aira_stream_results.out)
        assert "citations" in result
        assert "web_research_results" in result
        assert "{'score': 'no'}" in aira_stream_results.out  