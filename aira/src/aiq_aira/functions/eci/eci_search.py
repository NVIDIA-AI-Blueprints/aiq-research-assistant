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

import json
import logging

import httpx
from pydantic import BaseModel

from aiq_aira.functions.eci.content_search_response import ContentSearchResponse
from aiq_aira.functions.eci.eci_search_utils import get_ssa_token
from aiq_aira.functions.eci.eci_search_utils import get_starfleet_token
from aiq_aira.utils import custom_raise_for_status

logger = logging.getLogger(__name__)


class ECISearchRequest(BaseModel):
    allow_login: bool = False

    query: str
    query_size: int = 10
    data_sources: list[str] | None = None
    max_snippet_size: int = 1000
    cursor: str | None = None


async def eci_search_single(*, client: httpx.AsyncClient, prod: bool,
                            request: ECISearchRequest) -> ContentSearchResponse:

    # First, get the saved credentials
    starfleet_token = await get_starfleet_token(client=client, prod=prod, allow_login=request.allow_login)

    ssa_token = await get_ssa_token(client=client, prod=prod)

    # Now, make the request
    headers = {
        "Authorization": f"Bearer {ssa_token}",
        "Nv-Actor-Token": starfleet_token,
        "Content-Type": "application/json",
    }

    payload = {"query": request.query, "pageSize": request.query_size, "maxSnippetSize": request.max_snippet_size}

    if (request.data_sources is not None):
        payload["requestOptions"] = {"datasourcesFilter": [ds.upper() for ds in request.data_sources]}

    if (request.cursor is not None):
        payload["cursor"] = request.cursor

    response = await client.post(
        f"https://enterprise-content-intelligence{'-stg' if not prod else ''}.nvidia.com/v1/content/search",
        headers=headers,
        json=payload)

    custom_raise_for_status(response)

    response_json = response.json()

    logger.debug("Successfully made ECI request. Response: %s", json.dumps(response_json, indent=2))

    return ContentSearchResponse.model_validate(response_json)
