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

import logging

from aiq.builder.builder import Builder
from aiq.builder.function_info import FunctionInfo
from aiq.cli.register_workflow import register_function
from aiq.data_models.function import FunctionBaseConfig

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

    from aiq_aira.functions.eci.content_search_response import ContentSearchResponse
    from aiq_aira.functions.eci.eci_search import ECISearchRequest
    from aiq_aira.functions.eci.eci_search import eci_search_single

    async with httpx.AsyncClient() as client:

        async def _eci_search_inner(query: str,
                                    query_size: int | None = None,
                                    data_sources: list[str] | None = None) -> ContentSearchResponse:

            request = ECISearchRequest(
                query=query,
                query_size=query_size if query_size is not None else config.default_query_size,
                max_snippet_size=1000,
                data_sources=data_sources if data_sources is not None else config.default_data_sources,
            )

            return await eci_search_single(client=client, prod=config.use_prod, request=request)

        yield FunctionInfo.create(
            single_fn=_eci_search_inner,
            description="Search the Enterprise Content Intelligence (ECI) repositories for a given query.")
