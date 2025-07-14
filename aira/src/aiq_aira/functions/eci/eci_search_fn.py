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

from aiq.builder.builder import Builder
from aiq.builder.function_info import FunctionInfo
from aiq.cli.register_workflow import register_function
from aiq.data_models.function import FunctionBaseConfig

from aiq_aira.functions.eci.content_search_response import ContentSearchResponse

logger = logging.getLogger(__name__)


class ECISearchConfig(FunctionBaseConfig, name="eci_search"):
    """
    Configuration for the eci_search function/endpoint
    """
    use_prod: bool = False
    allow_login: bool = False
    default_query_size: int = 10
    default_data_sources: list[str] | None = None


@register_function(config_type=ECISearchConfig)
async def eci_search_fn(config: ECISearchConfig, aiq_builder: Builder):
    import httpx

    from aiq_aira.functions.eci.eci_search_utils import get_ssa_token
    from aiq_aira.functions.eci.eci_search_utils import get_starfleet_token
    from aiq_aira.utils import custom_raise_for_status

    async with httpx.AsyncClient() as client:

        async def _eci_search_single(query: str,
                                     query_size: int | None = None,
                                     data_sources: list[str] | None = None) -> ContentSearchResponse:

            # First, get the saved credentials
            starfleet_token = await get_starfleet_token(prod=config.use_prod, allow_login=config.allow_login)

            ssa_token = await get_ssa_token(client=client, prod=config.use_prod)

            # Now, make the request
            headers = {
                "Authorization": f"Bearer {ssa_token}",
                "Nv-Actor-Token": starfleet_token,
                "Content-Type": "application/json",
            }

            payload = {
                "query": query,
                "pageSize": query_size if query_size is not None else config.default_query_size,
            }

            data_sources = data_sources if data_sources is not None else config.default_data_sources

            if (data_sources is not None):
                payload["requestOptions"] = {"datasourcesFilter": [ds.upper() for ds in data_sources]}

            response = await client.post(
                f"https://enterprise-content-intelligence{'-stg' if not config.use_prod else ''}.nvidia.com/v1/content/search",
                headers=headers,
                json=payload)

            custom_raise_for_status(response)

            response_json = response.json()

            logger.debug("Successfully made ECI request. Response: %s", json.dumps(response_json, indent=2))

            return ContentSearchResponse.model_validate(response_json)

        yield FunctionInfo.create(
            single_fn=_eci_search_single,
            description="Search the Enterprise Content Intelligence (ECI) repositories for a given query.")
