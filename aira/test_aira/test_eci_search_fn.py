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

from aiq_aira.functions.eci.eci_search_fn import ECISearchConfig
import pytest
import logging
from aiq.builder.workflow_builder import WorkflowBuilder

from aiq_aira.functions.eci.content_search_response import ContentSearchResponse

logger = logging.getLogger(__name__)


async def test_eci_search_fn():

    async with WorkflowBuilder() as builder:

        fn = await builder.add_function(
            name="eci_search", config=ECISearchConfig(allow_login=True))

        result: ContentSearchResponse = await fn.acall_invoke(query="NVIDIA?")

        print(result)
