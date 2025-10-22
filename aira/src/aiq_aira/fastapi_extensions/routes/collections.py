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
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class CreateCollectionRequest(BaseModel):
    """Request model for creating a collection"""
    vdb_endpoint: str
    collection_name: str
    embedding_dimension: int
    metadata_schema: List[Any] = []


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
            logger.error("Error verifying collection '%s': %s", collection_name, e)
            # On error, assume it doesn't exist to be safe
            return False


async def verify_collection_ready(collection_name: str,
                                  rag_ingest_url: str,
                                  max_attempts: int = 3,
                                  delay: int = 5) -> bool:
    """Verify a newly created collection is ready by polling the documents endpoint"""
    for attempt in range(max_attempts):
        logger.info("Verifying collection '%s' is ready (attempt %d/%d)...", collection_name, attempt + 1, max_attempts)

        if await verify_collection_exists(collection_name, rag_ingest_url):
            logger.info("Collection '%s' verified as ready", collection_name)
            return True

        if attempt < max_attempts - 1:
            logger.info("Collection '%s' not ready yet, waiting %d seconds...", collection_name, delay)
            await asyncio.sleep(delay)

    logger.error("Collection '%s' not ready after %d attempts", collection_name, max_attempts)
    return False


async def create_collection_handler(rag_ingest_url: str):
    """Create a handler for POST /collection endpoint"""

    async def post_collection(request: CreateCollectionRequest):
        try:
            # Create a list with the collection name for the RAG ingest service
            collection_names = [request.collection_name]
            collection_type = "text"  # Default collection type
            
            async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
                params = {
                    "collection_type": collection_type,
                    "embedding_dimension": request.embedding_dimension
                }
                
                url = f"{rag_ingest_url}/collections"
                response = await client.post(url, json=collection_names, params=params)
                
                if response.status_code == 200:
                    # Return the raw response from RAG ingest service
                    return response.json()
                else:
                    # Handle error responses from the RAG ingest service
                    error_detail = response.text
                    logger.error("Failed to create collection '%s': %s", request.collection_name, error_detail)
                    raise HTTPException(status_code=response.status_code, detail=f"Failed to create collection: {error_detail}")
                    
        except httpx.RequestError as e:
            logger.error("Request error when creating collection '%s': %s", request.collection_name, e)
            raise HTTPException(status_code=500, detail=f"Request error: {str(e)}") from e
        except Exception as e:
            logger.error("Unexpected error when creating collection '%s': %s", request.collection_name, e)
            raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}") from e

    return post_collection



async def create_delete_collections_handler(rag_ingest_url: str):
    """Create a handler for DELETE /collections endpoint"""

    async def delete_collections(request: List[str]):
        print(f"Deleting collections: {request}")
        try:
            # Forward the list of collection names to the RAG ingest service
            collection_names = request            
            async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
                url = f"{rag_ingest_url}/collections"
                response = await client.request("DELETE", url, json=collection_names)
                
                if response.status_code == 200:
                    # Return the raw response from RAG ingest service
                    return response.json()
                else:
                    # Handle error responses from the RAG ingest service
                    error_detail = response.text
                    logger.error("Failed to delete collections: %s", error_detail)
                    raise HTTPException(status_code=response.status_code, detail=f"Failed to delete collections: {error_detail}")
                    
        except httpx.RequestError as e:
            logger.error("Request error when deleting collections: %s", e)
            raise HTTPException(status_code=500, detail=f"Request error: {str(e)}") from e
        except Exception as e:
            logger.error("Unexpected error when deleting collections: %s", e)
            raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}") from e

    return delete_collections


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

    # Create the handlers
    post_collection_handler = await create_collection_handler(rag_ingest_url)
    delete_collections_handler = await create_delete_collections_handler(rag_ingest_url)
    get_collections_handler = await create_get_collections_handler(rag_ingest_url)

    # Add the collection creation route
    app.add_api_route("/collection",
                      post_collection_handler,
                      methods=["POST"],
                      tags=["rag-endpoints"],
                      summary="Create a RAG collection")
    
    # Add the collections deletion route
    app.add_api_route("/collections",
                      delete_collections_handler,
                      methods=["DELETE"],
                      tags=["rag-endpoints"],
                      summary="Delete RAG collections")
    
    # Add the collections listing route
    app.add_api_route("/collections",
                      get_collections_handler,
                      methods=["GET"],
                      tags=["rag-endpoints"],
                      summary="Get RAG collections")
