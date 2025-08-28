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

import json
import logging
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

import httpx
from fastapi import FastAPI
from fastapi import File
from fastapi import Form
from fastapi import HTTPException
from fastapi import Query
from fastapi import UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class DocumentRequest(BaseModel):
    """Request model for document operations"""
    collection_name: str
    documents: List[Dict[str, Any]]


async def add_document_routes(app: FastAPI, rag_ingest_url: str):
    """Add document-related routes to the FastAPI app"""

    async def _handle_document_upload(documents: List[UploadFile],
                                      data: str,
                                      http_method: str = "POST") -> Dict[str, Any]:
        """
        Common logic for handling document uploads.
        
        Args:
            documents: List of uploaded files
            data: JSON string containing metadata
            http_method: HTTP method to use (POST or PATCH)
            
        Returns:
            Response from RAG ingest service
            
        Raises:
            HTTPException: On validation or processing errors
        """
        try:
            # Parse metadata from form data
            metadata = json.loads(data)

            # Set default blocking if not specified
            if "blocking" not in metadata:
                metadata["blocking"] = True

            logger.info(f"Document upload request ({http_method}) - Metadata: {metadata}")

            # Create multipart form data for upstream request
            files = []
            for doc in documents:
                content = await doc.read()
                files.append(('documents', (doc.filename, content, doc.content_type)))

            form_data = {'data': json.dumps(metadata)}

            # Forward to RAG ingest service
            async with httpx.AsyncClient(timeout=3600.0) as client:
                if http_method == "PATCH":
                    response = await client.patch(f"{rag_ingest_url}/documents", files=files, data=form_data)
                else:  # Default to POST
                    response = await client.post(f"{rag_ingest_url}/documents", files=files, data=form_data)

                if response.status_code not in [200, 201]:
                    raise HTTPException(status_code=response.status_code, detail=response.json())

                return response.json()

        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON in data field")
        except Exception as e:
            logger.error(f"Error uploading documents ({http_method}): {e}")
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(status_code=500, detail=str(e))

    # POST /documents - Upload documents
    @app.post("/documents", tags=["rag-endpoints"])
    async def upload_documents(
            documents: List[UploadFile] = File(...),
            data:
        str = Form(
            ...,
            description="JSON string containing metadata for document upload",
            example=
            '{"collection_name": "multimodal_data", "blocking": false, "split_options": {"chunk_size": 512, "chunk_overlap": 150}}'
        )):
        """
        Upload documents to RAG with metadata.
        
        Example data field:
        {
            "collection_name": "multimodal_data",
            "blocking": false,
            "split_options": {
                "chunk_size": 512,
                "chunk_overlap": 150
            }
        }
        """
        return await _handle_document_upload(documents, data, "POST")

    # PATCH /documents - Upload/replace documents
    @app.patch("/documents", tags=["rag-endpoints"])
    async def upload_replace_documents(
            documents: List[UploadFile] = File(...),
            data:
        str = Form(
            ...,
            description="JSON string containing metadata for document upload/replacement",
            example=
            '{"collection_name": "multimodal_data", "blocking": false, "split_options": {"chunk_size": 512, "chunk_overlap": 150}}'
        )):
        """
        Upload documents to RAG with metadata. If the document already exists, it will be replaced.
        
        Example data field:
        {
            "collection_name": "multimodal_data",
            "blocking": false,
            "split_options": {
                "chunk_size": 512,
                "chunk_overlap": 150
            }
        }
        """
        return await _handle_document_upload(documents, data, "PATCH")

    # GET /documents - List documents
    @app.get("/documents", tags=["rag-endpoints"])
    async def list_documents(collection_name: str = Query(...)):
        """List documents in a collection"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(f"{rag_ingest_url}/documents", params={"collection_name": collection_name})

                if response.status_code != 200:
                    raise HTTPException(status_code=response.status_code, detail=response.json())

                return response.json()

        except Exception as e:
            logger.error(f"Error fetching documents: {e}")
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(status_code=500, detail=str(e))

    # DELETE /documents - Delete documents
    @app.delete("/documents", tags=["rag-endpoints"])
    async def delete_documents(document_names: List[str], collection_name: str = Query(...)):
        """Delete documents from a collection"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.request("DELETE",
                                                f"{rag_ingest_url}/documents",
                                                params={"collection_name": collection_name},
                                                json=document_names)

                if response.status_code != 200:
                    raise HTTPException(status_code=response.status_code, detail=response.json())

                logger.info(f"Documents deleted: {response.json()}")
                return response.json()

        except Exception as e:
            logger.error(f"Error deleting documents: {e}")
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(status_code=500, detail=str(e))

    # GET /status - Get the status of an ingestion task.
    @app.get("/status", tags=["rag-endpoints"])
    async def check_status(task_id: str = Query(...)):
        """Get the status of an ingestion task."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(f"{rag_ingest_url}/status", params={"task_id": task_id})

                if response.status_code != 200:
                    raise HTTPException(status_code=response.status_code, detail=response.json())

                return response.json()

        except Exception as e:
            logger.error(f"Error checking status: {e}")
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(status_code=500, detail=str(e))
