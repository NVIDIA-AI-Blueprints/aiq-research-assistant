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

import os
import json
import glob
import asyncio
import logging
import zipfile
from pathlib import Path
from pydantic import BaseModel
import aiohttp
import aiofiles
import os
from typing import List, Literal, Dict, Any
import urllib.parse
# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
)
logger = logging.getLogger(__name__)

RAG_URL = os.getenv("RAG_INGEST_URL", "http://ingestor-server:8082")
MAX_UPLOAD_WAIT_TIME = os.getenv("MAX_UPLOAD_WAIT_TIME", 60*60)
FILES_DIR = "."     

class Document(BaseModel):
    """ A document response from the RAG server. """
    document_name: str
    error_message: str | None = None

class UploadResult(BaseModel):
    """ Result of an upload. """
    message: str
    total_documents: int
    documents: List[Document]
    failed_documents: List[Document]

class UploadStatusResponse(BaseModel):
    """ Response from the RAG server after starting an upload. """
    state: Literal["PENDING", "FINISHED"]
    result: UploadResult | None = None

class UploadResponse(BaseModel):
    """ Response from the RAG server after starting an upload. """
    task_id: str
    message: str

# --- Helper Functions ---
def unzip_file(zip_path: str, extract_to: str):
    """Extracts a zip file to the specified directory."""
    logger.info(f"Unzipping {zip_path} to {extract_to}")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_to)

async def upload_files(paths: List[str], collection_name: str, rag_url: str) -> UploadResponse:
    """
    Start a batch upload of multiple files to the RAG service.
    
    Args:
        paths: List of file paths to upload
        collection_name: Name of the collection to upload to
        rag_url: Base URL of the RAG service
    """
    data = {
        "blocking": False,
        "collection_name": collection_name,
        "extraction_options": {
            "extract_text": True,
            "extract_tables": True,
            "extract_charts": True,
            "extract_images": False,
        },
        
    }

    async with aiohttp.ClientSession() as session:
        # Read all files asynchronously
        form_data = aiohttp.FormData()
        
        # Add all files to a single documents field
        for path in paths:
            dest_filename = os.path.basename(path)
            async with aiofiles.open(path, "rb") as file_obj:
                file_content = await file_obj.read()
                form_data.add_field(
                    "documents",  # Single field name for all files
                    file_content,
                    filename=dest_filename,
                    content_type="application/pdf"
                )
        
        # Add the metadata once
        form_data.add_field(
            "data",
            json.dumps(data),
            content_type="application/json"
        )
        
        endpoint = f"{rag_url}/documents"
        
        try:
            async with session.request("POST", endpoint, data=form_data) as response:
                result = await response.json()
                return UploadResponse(
                    task_id=result.get("task_id"),
                    message=result.get("message")
                )
        except Exception as e:
            error_msg = f"Failed to start file upload, error: {e}"
            try:
                if 'result' in locals():
                    error_msg += f" and upload response: {result}"
            except:
                pass
            logger.error(error_msg)
            raise e

async def create_collection(
    collection_name: list = None,
    rag_url: str = None,
):
    """
    Creates a collection through the RAG server API if it doesn't already exist.
    First checks for existing collections, then creates only if needed.
    Returns the response from the server.
    """    

    HEADERS = {"Content-Type": "application/json"}

    async with aiohttp.ClientSession() as session:
        try:
            # First, get existing collections
            async with session.get(f"{rag_url}/collections", headers=HEADERS) as response:
                if response.status != 200:
                    logger.error(f"Failed to get existing collections: {await response.text()}")
                    return None
                
                response_data = await response.json()
                logger.info(f"Existing collections: {response_data}")
                
                # Extract collection names from the response structure
                existing_collection_names = [collection["collection_name"] for collection in response_data.get("collections", [])]
                
                # Check if our collection already exists
                if collection_name[0] in existing_collection_names:
                    logger.info(f"Collection {collection_name[0]} already exists, skipping creation")
                    return "Collection already exists"

            # If collection doesn't exist, create it
            async with session.post(f"{rag_url}/collections", json=collection_name, headers=HEADERS) as response:
                result = await response.text()
                if '"total_failed":1' in result:  
                    logger.error(f"Failed to create collection: {result}")
                    return None
                logger.info(f"Created collection with result: {result}")
                return result
            
        except aiohttp.ClientError as e:
            logger.error(f"Failed to create collection: {str(e)}")
            return None
        
async def get_upload_status(task_id: str, rag_url: str) -> UploadStatusResponse:
    """
    Get the status of an upload.
    
    Args:
        task_id: The ID of the upload task to check
        rag_url: Base URL of the RAG service
    """
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{rag_url}/status", params={"task_id": task_id}) as response:
            result = await response.json()
            return UploadStatusResponse.model_validate(result)
        

async def get_existing_documents(collection_name: str, rag_url: str) -> List[Document]:
    """
    Get all existing documents from the RAG server.
    """
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{rag_url}/documents", params={"collection_name": collection_name}) as response:
            result = await response.json()
            return [Document(document_name=doc["document_name"]) for doc in result.get("documents", [])]

async def process_zip_file(zip_path: str):
    """
    Processes a single zip file: unzips it, uploads all files in a batch to the RAG server
    """

    collection_name = Path(zip_path).stem
    extraction_path = os.path.join("output", collection_name)
    os.makedirs(extraction_path, exist_ok=True)

    # Create collection
    max_attempts = 3
    for attempt in range(max_attempts):
        result = await create_collection(
            collection_name=[collection_name],  # API expects a list
            rag_url=RAG_URL,
        )

        if result is not None:
            break
        
        if attempt < max_attempts - 1:
            logger.warning(f"Failed to create collection on attempt {attempt + 1}/{max_attempts}. Waiting 10 seconds before retry...")
            await asyncio.sleep(10)
    
    if result is None:
        logger.error(f"Failed to create collection {collection_name} after {max_attempts} attempts. Skipping {zip_path}")
        return

    unzip_file(zip_path, extraction_path)
    
    # Recursively find all files in the extraction directory
    files = []
    existing_documents = await get_existing_documents(collection_name, RAG_URL)
    existing_documents_set = set([doc.document_name for doc in existing_documents])

    for root, _, filenames in os.walk(extraction_path):
        for filename in filenames:
            filename_url_encoded = urllib.parse.quote(filename)
            if filename_url_encoded in existing_documents_set:
                logger.info(f"Skipping {filename} because it already exists in the collection {collection_name}")
                continue
            files.append(os.path.abspath(os.path.join(root, filename)))
    
    if len(files) == 0:
        logger.info(f"No files to upload to collection {collection_name}")
        return

    logger.info(f"Starting upload of {len(files)} files to {collection_name}")
    upload_response = await upload_files(files, collection_name, RAG_URL)

    logger.info(f"Upload started with message: {upload_response.message}")
    upload_status = await get_upload_status(upload_response.task_id, RAG_URL)
    logger.info(f"Polling task {upload_response.task_id}, status: {upload_status.state}")
    time = 0

    while upload_status.state == "PENDING":
        await asyncio.sleep(10)
        time += 10
        upload_status = await get_upload_status(upload_response.task_id, RAG_URL)
        logger.info(f"Uploading files to {collection_name}. Elapsed time: {time} seconds")
        if time > MAX_UPLOAD_WAIT_TIME:
            logger.error(f"Upload did not finish in {MAX_UPLOAD_WAIT_TIME} seconds")
            break

    if upload_status.state == "FINISHED":
        logger.info(f"Upload to collection {collection_name} finished with result: {upload_status.result.total_documents} documents attempted.")
        logger.info(f"\n \n--- \n Document Results: {"\n".join([f"{doc.document_name}: Success"  for doc in upload_status.result.documents])}")
        logger.info(f"\n \n Failed Documents: {"\n".join([f"{doc.document_name}: {doc.error_message}" for doc in upload_status.result.failed_documents])}")


async def main():
    """Main function to process each zip file in the directory and upload to RAG server."""
    logger.info(f"Starting upload of files to RAG server")
    zip_files = [f for f in os.listdir(FILES_DIR) if f.endswith(".zip")]

    if not zip_files:
        logger.info(f"No zip files found in directory {FILES_DIR}")
        return
    
    logger.info(f"Found {len(zip_files)} zip files in directory {FILES_DIR}")

    for zip_file in zip_files:
        zip_path = os.path.join(FILES_DIR, zip_file)
        logger.info(f"Processing zip file: {zip_path}")
        await process_zip_file(zip_path)

if __name__ == "__main__":
    asyncio.run(main())