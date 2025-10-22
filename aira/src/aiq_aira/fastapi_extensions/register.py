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
"""
FastAPI Extensions Module

This module provides custom FastAPI extensions that are layered on top of the base
AIQ/NAT server API. It includes middleware functionality such as session management
with Redis and automatic cleanup of temporary resources.

The extensions are implemented as a FastAPI plugin that can inject additional
routes and functionality into the base FastAPI server.
"""

import os
from typing import override

from nat.builder.workflow_builder import WorkflowBuilder
from nat.cli.register_workflow import register_front_end
from nat.data_models.config import AIQConfig
from nat.front_ends.fastapi.fastapi_front_end_config import FastApiFrontEndConfig
from nat.front_ends.fastapi.fastapi_front_end_plugin import FastApiFrontEndPlugin
from nat.front_ends.fastapi.fastapi_front_end_plugin_worker import FastApiFrontEndPluginWorker
from nat.front_ends.fastapi.fastapi_front_end_plugin_worker import FastApiFrontEndPluginWorkerBase
from fastapi import FastAPI

from .routes.collections import add_collection_routes
from .routes.documents import add_document_routes


class APIExtensionsConfig(FastApiFrontEndConfig, name="aira_frontend"):
    """Configuration for API extensions including middleware settings"""
    pass


class APIExtensionsWorker(FastApiFrontEndPluginWorker):
    """Worker that adds custom API routes and middleware to the base API server"""

    @override
    async def add_routes(self, app: FastAPI, builder: WorkflowBuilder):
        await super().add_routes(app, builder)

        rag_ingest_url = os.getenv("RAG_INGEST_URL", "http://ingestor-server:8082/v1")

        # Add collection routes with Redis session tracking
        await add_collection_routes(app, rag_ingest_url)

        # Add document routes
        await add_document_routes(app, rag_ingest_url)


class APIExtensionsPlugin(FastApiFrontEndPlugin):
    """Plugin that extends the base API with custom functionality"""

    def __init__(self, full_config: AIQConfig, config: APIExtensionsConfig):
        super().__init__(full_config=full_config)
        self.config = config

    @override
    def get_worker_class(self) -> type[FastApiFrontEndPluginWorkerBase]:
        return APIExtensionsWorker


@register_front_end(config_type=APIExtensionsConfig)
async def register_api_extensions(config: APIExtensionsConfig, full_config: AIQConfig):
    """Register API extensions with the AIQ framework"""
    yield APIExtensionsPlugin(full_config=full_config, config=config)
