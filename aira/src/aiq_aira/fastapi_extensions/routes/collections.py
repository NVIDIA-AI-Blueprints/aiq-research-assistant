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
from typing import List

import httpx
from fastapi import FastAPI

from ..redis_utils import CollectionRequest
from ..redis_utils import CollectionResponse
from ..redis_utils import check_existing_collections
from ..redis_utils import initialize_redis
from ..redis_utils import track_collection

logger = logging.getLogger(__name__)


async def create_post_collections_handler(rag_ingest_url: str):
    """Create a handler for POST /collections endpoint"""

    # Initialize Redis on startup
    await initialize_redis(rag_ingest_url)

    async def post_collections(request: CollectionRequest) -> CollectionResponse:
        """Create collections and track them in Redis"""
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
            try:
                # Check which collections already exist in Redis (non-expired)
                existing, new_collections = await check_existing_collections(request.collection_names)

                # Log existing collections (no TTL refresh)
                for name in existing:
                    logger.info(f"Collection '{name}' already exists - using existing session")

                # If all collections already exist, return success
                if not new_collections:
                    return CollectionResponse(message=f"All collections already exist: {', '.join(existing)}",
                                              successful=existing,
                                              failed=[],
                                              total_success=len(existing),
                                              total_failed=0)

                # Create only the new collections
                params = {
                    "collection_type": request.collection_type, "embedding_dimension": request.embedding_dimension
                }

                url = f"{rag_ingest_url}/collections"
                logger.info(f"Creating new collections at {url} with params: {params}")
                logger.info(f"New collection names: {new_collections}")
                if existing:
                    logger.info(f"Existing collection names (skipped): {existing}")

                response = await client.post(url, json=new_collections, params=params)

                # If successful, track the collections
                if response.status_code in [200, 201]:
                    result = response.json()

                    # Track each successful collection in Redis
                    for name in result.get("successful", []):
                        await track_collection(name)

                    # Combine results
                    all_successful = existing + result.get("successful", [])

                    return CollectionResponse(
                        message=
                        f"Collection creation completed. Created: {len(result.get('successful', []))}, Already existed: {len(existing)}",
                        successful=all_successful,
                        failed=result.get("failed", []),
                        total_success=len(all_successful),
                        total_failed=result.get("total_failed", 0))
                elif len(existing) > 0:
                    error_text = response.text
                    # Still return existing as successful, following existing RAG API behavior
                    return CollectionResponse(
                        message=f"Failed to create new collections: {response.status_code} - {error_text}",
                        successful=existing,
                        failed=new_collections,
                        total_success=len(existing),
                        total_failed=len(new_collections))
                else:
                    raise Exception(f"Failed to create collections: {response.status_code} - {response.text}")

            except Exception as e:
                logger.error(f"Error creating collections: {e}")
                return CollectionResponse(message=f"Error creating collections: {str(e)}",
                                          successful=[],
                                          failed=request.collection_names,
                                          total_success=0,
                                          total_failed=len(request.collection_names))

    return post_collections


async def add_collection_routes(app: FastAPI, rag_ingest_url: str):
    """Add collection-related routes to the FastAPI app"""

    # Create the POST collections handler
    post_collections_handler = await create_post_collections_handler(rag_ingest_url)

    # Add the route
    app.add_api_route("/collections",
                      post_collections_handler,
                      methods=["POST"],
                      response_model=CollectionResponse,
                      tags=["rag-endpoints"],
                      summary="Create RAG collections with session TTL tracking")
