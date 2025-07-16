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
import json
import logging
import os
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

import httpx
import redis.asyncio as redis
from aiq.builder.builder import Builder
from aiq.builder.function_info import FunctionInfo
from aiq.cli.register_workflow import register_function
from aiq.data_models.function import FunctionBaseConfig
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Configuration
SESSION_TIMEOUT = int(os.getenv("SESSION_TIMEOUT_HOURS", "24")) * 60 * 60  # Convert hours to seconds
REDIS_HOST = os.getenv("REDIS_HOST", "rag-redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

# Redis connection pool
redis_pool = None
# Background task reference
cleanup_task = None


class CollectionRequest(BaseModel):
    """Request model for creating collections"""
    collection_names: List[str]
    collection_type: Optional[str] = "text"
    embedding_dimension: Optional[int] = 2048


class CollectionResponse(BaseModel):
    """Response model for collection operations"""
    message: Optional[str] = None
    successful: Optional[List[str]] = None
    failed: Optional[List[str]] = None
    total_success: Optional[int] = None
    total_failed: Optional[int] = None


async def get_redis() -> redis.Redis:
    """Get Redis connection"""
    global redis_pool
    if not redis_pool:
        redis_pool = redis.ConnectionPool(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True, max_connections=50)
    return redis.Redis(connection_pool=redis_pool)


async def track_collection(collection_name: str):
    """Track a collection in Redis with TTL"""
    r = await get_redis()
    session_key = f"session:{collection_name}"
    await r.setex(session_key, SESSION_TIMEOUT, "1")
    logger.info(f"Tracking collection: {collection_name} (TTL: {SESSION_TIMEOUT}s)")


async def check_existing_collections(collection_names: List[str]) -> tuple[List[str], List[str]]:
    """Check which collections exist in Redis (and thus in RAG)"""
    r = await get_redis()
    existing = []
    new_collections = []

    try:
        # Check each collection in Redis
        for collection_name in collection_names:
            session_key = f"session:{collection_name}"
            # Check if key exists (not expired)
            if await r.exists(session_key):
                existing.append(collection_name)
                logger.debug(f"Collection '{collection_name}' found in Redis (active session)")
            else:
                new_collections.append(collection_name)
                logger.debug(f"Collection '{collection_name}' not found in Redis (new or expired)")

        return existing, new_collections

    except Exception as e:
        logger.error(f"Error checking collections in Redis: {e}")
        # If error occurs, assume all are new
        return [], collection_names


async def cleanup_expired_collections(rag_url: str):
    """Monitor Redis key expiration and delete corresponding RAG collections"""
    r = await get_redis()

    # Subscribe to key expiration events
    pubsub = r.pubsub()
    await pubsub.subscribe("__keyevent@0__:expired")

    logger.info("Started monitoring collection expirations")

    async for message in pubsub.listen():
        if message["type"] == "message":
            expired_key = message["data"]
            if expired_key.startswith("session:"):
                collection_name = expired_key.replace("session:", "")
                logger.info(f"Session expired: {collection_name}")

                # Delete collection from RAG
                try:
                    async with httpx.AsyncClient() as client:
                        response = await client.request(method="DELETE",
                                                        url=f"{rag_url}/collections",
                                                        json=[collection_name])
                        if response.status_code in [200, 201]:
                            result = response.json()
                            if collection_name in result.get("successful", []):
                                logger.info(f"Successfully deleted collection: {collection_name}")
                            else:
                                logger.error(f"Failed to delete collection {collection_name}: {result}")
                        else:
                            logger.error(f"Failed to delete collection {collection_name}: {response.status_code}")
                except Exception as e:
                    logger.error(f"Error deleting collection {collection_name}: {e}")


async def initialize_redis(rag_url: str):
    """Initialize Redis connection and start cleanup task"""
    global cleanup_task

    # Test Redis connection
    try:
        r = await get_redis()
        await r.ping()

        # Enable keyspace notifications for expirations
        await r.config_set("notify-keyspace-events", "Ex")
        logger.info(f"Connected to Redis and enabled expiration notifications")
        logger.info(f"Session timeout configured to {SESSION_TIMEOUT // 3600} hours")

        # Start cleanup task if not already running
        if cleanup_task is None:
            cleanup_task = asyncio.create_task(cleanup_expired_collections(rag_url))

    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")
        raise


class PostCollectionsConfig(FunctionBaseConfig, name="post_collections"):
    """Configuration for POST /collections endpoint"""
    rag_url: str = ""


@register_function(config_type=PostCollectionsConfig)
async def post_collections_fn(config: PostCollectionsConfig, aiq_builder: Builder):
    """Handle collection creation - forward to RAG and track in Redis"""

    # Initialize Redis on first use
    await initialize_redis(config.rag_url)

    async def _post_collections(request: CollectionRequest) -> CollectionResponse:
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

                url = f"{config.rag_url}/collections"
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

    yield FunctionInfo.create(single_fn=_post_collections,
                              description="Create RAG collections and track them for automatic cleanup")
