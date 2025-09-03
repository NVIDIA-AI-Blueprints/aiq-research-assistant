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

import asyncio
import logging
from typing import List
from typing import Optional

import httpx
from fastapi import FastAPI
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class CollectionResponse(BaseModel):
    """Response model for collection operations"""
    message: Optional[str] = None
    successful: Optional[List[str]] = None
    failed: Optional[List[str]] = None
    total_success: Optional[int] = None
    total_failed: Optional[int] = None


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


async def create_post_collections_handler(rag_ingest_url: str):
    """Create a handler for POST /collections endpoint"""

    async def post_collections(request: List[str]):
        # Simple list format: ["collection1", "collection2"]
        collection_names = request
        collection_type = "text"
        embedding_dimension = 2048
        
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
            params = {
                "collection_type": collection_type,
                "embedding_dimension": embedding_dimension
            }
            
            url = f"{rag_ingest_url}/collections"
            response = await client.post(url, json=collection_names, params=params)
            
            # Forward the response directly
            return response.json()

    return post_collections

async def create_get_collections_handler(rag_ingest_url: str):
    """Get a handler for GET /collections endpoint"""
    async def get_collections():
        """Get collections"""
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
            response = await client.get(f"{rag_ingest_url}/collections")
            return response.json()
    return get_collections

async def add_collection_routes(app: FastAPI, rag_ingest_url: str):
    """Add collection-related routes to the FastAPI app"""

    # Create the POST collections handler
    post_collections_handler = await create_post_collections_handler(rag_ingest_url)
    get_collections_handler = await create_get_collections_handler(rag_ingest_url)

    # Add the route
    app.add_api_route("/collections",
                      post_collections_handler,
                      methods=["POST"],
                      tags=["rag-endpoints"],
                      summary="Create RAG collections")
    
    app.add_api_route("/collections",
                      get_collections_handler,
                      methods=["GET"],
                      tags=["rag-endpoints"],
                      summary="Get RAG collections")
