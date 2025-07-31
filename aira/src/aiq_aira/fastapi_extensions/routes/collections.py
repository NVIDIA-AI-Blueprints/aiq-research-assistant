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

import asyncio
import logging
from typing import List

import httpx
from fastapi import FastAPI

from ..redis_utils import CollectionRequest
from ..redis_utils import CollectionResponse
from ..redis_utils import check_existing_collections
from ..redis_utils import collection_exists_in_redis
from ..redis_utils import get_redis
from ..redis_utils import initialize_redis
from ..redis_utils import track_collection

logger = logging.getLogger(__name__)


async def verify_collection_exists(collection_name: str, rag_ingest_url: str) -> bool:
    """Verify if a collection actually exists by querying the documents endpoint"""
    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
        try:
            url = f"{rag_ingest_url}/documents"
            params = {"collection_name": collection_name}
            response = await client.get(url, params=params)

            # If we get a 200 response, the collection exists
            # If we get 404 or error, it doesn't exist
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Error verifying collection '{collection_name}': {e}")
            # On error, assume it doesn't exist to be safe
            return False


async def verify_collection_ready(collection_name: str,
                                  rag_ingest_url: str,
                                  max_attempts: int = 3,
                                  delay: int = 5) -> bool:
    """Verify a newly created collection is ready by polling the documents endpoint"""
    for attempt in range(max_attempts):
        logger.info(f"Verifying collection '{collection_name}' is ready (attempt {attempt + 1}/{max_attempts})...")

        if await verify_collection_exists(collection_name, rag_ingest_url):
            logger.info(f"Collection '{collection_name}' verified as ready")
            return True

        if attempt < max_attempts - 1:
            logger.info(f"Collection '{collection_name}' not ready yet, waiting {delay} seconds...")
            await asyncio.sleep(delay)

    logger.error(f"Collection '{collection_name}' not ready after {max_attempts} attempts")
    return False


async def remove_collection_from_redis(collection_name: str):
    """Remove a collection from Redis cache"""
    r = await get_redis()
    session_key = f"session:{collection_name}"
    await r.delete(session_key)
    logger.info(f"Removed collection '{collection_name}' from Redis cache")


async def create_post_collections_handler(rag_ingest_url: str):
    """Create a handler for POST /collections endpoint"""

    # Initialize Redis on startup
    await initialize_redis(rag_ingest_url)

    async def post_collections(request: CollectionRequest) -> CollectionResponse:
        """Create collections and track them in Redis"""
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
            try:
                # Check which collections already exist in Redis (non-expired)
                existing_in_redis, new_collections = await check_existing_collections(request.collection_names)

                # Verify collections that Redis claims exist
                verified_existing = []
                collections_to_recreate = []

                for name in existing_in_redis:
                    logger.info(f"Verifying collection '{name}' exists in RAG service...")
                    if await verify_collection_exists(name, rag_ingest_url):
                        verified_existing.append(name)
                        logger.info(f"Collection '{name}' verified - using existing session")
                    else:
                        logger.warning(
                            f"Collection '{name}' not found in RAG service - removing from cache and recreating")
                        await remove_collection_from_redis(name)
                        collections_to_recreate.append(name)

                # Add collections that need to be recreated to the new_collections list
                new_collections.extend(collections_to_recreate)

                # If all collections already exist and are verified, return success
                if not new_collections:
                    return CollectionResponse(message=f"All collections already exist: {', '.join(verified_existing)}",
                                              successful=verified_existing,
                                              failed=[],
                                              total_success=len(verified_existing),
                                              total_failed=0)

                # Create only the new collections
                params = {
                    "collection_type": request.collection_type, "embedding_dimension": request.embedding_dimension
                }

                url = f"{rag_ingest_url}/collections"
                logger.info(f"Creating new collections at {url} with params: {params}")
                logger.info(f"New collection names: {new_collections}")
                if verified_existing:
                    logger.info(f"Existing collection names (verified): {verified_existing}")

                response = await client.post(url, json=new_collections, params=params)

                # If successful, verify each collection is ready before tracking
                if response.status_code in [200, 201]:
                    result = response.json()
                    created_collections = result.get("successful", [])

                    # Verify each newly created collection is ready
                    actually_successful = []
                    failed_verification = []

                    for name in created_collections:
                        if await verify_collection_ready(name, rag_ingest_url):
                            # Only track in Redis if collection is verified as ready
                            await track_collection(name)
                            actually_successful.append(name)
                        else:
                            logger.error(f"Collection '{name}' created but not accessible - not tracking in Redis")
                            failed_verification.append(name)

                    # Combine results
                    all_successful = verified_existing + actually_successful
                    all_failed = result.get("failed", []) + failed_verification

                    return CollectionResponse(
                        message=
                        f"Collection creation completed. Created and verified: {len(actually_successful)}, Already existed: {len(verified_existing)}, Failed verification: {len(failed_verification)}",
                        successful=all_successful,
                        failed=all_failed,
                        total_success=len(all_successful),
                        total_failed=len(all_failed))
                elif len(verified_existing) > 0:
                    error_text = response.text
                    # Still return existing as successful, following existing RAG API behavior
                    return CollectionResponse(
                        message=f"Failed to create new collections: {response.status_code} - {error_text}",
                        successful=verified_existing,
                        failed=new_collections,
                        total_success=len(verified_existing),
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

    # GET /collections/{collection_name}/exists - Check if collection exists in Redis cache
    @app.get("/collections/{collection_name}/exists", tags=["rag-endpoints"])
    async def check_collection_exists(collection_name: str) -> dict:
        """
        Check if a collection exists in Redis cache (has an active session).
        
        Args:
            collection_name: Name of the collection to check
            
        Returns:
            dict: {"exists": bool, "collection_name": str}
        """
        exists = await collection_exists_in_redis(collection_name)
        return {"exists": exists, "collection_name": collection_name}
