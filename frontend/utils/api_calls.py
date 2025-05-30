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

"""
Utility module for making API calls to backend services.

This module centralizes all functions responsible for interacting with external APIs
required by the AI Research Assistant frontend. It handles:
-   Configuration management for API base URLs and keys (retrieved from environment
    variables or Streamlit session state).
-   Construction of API requests (GET, POST, PUT, DELETE) with appropriate headers
    and payloads.
-   Error handling for API responses, including displaying user-friendly messages
    in the Streamlit interface.
-   Processing of API responses, including JSON decoding and data extraction.
-   Support for streaming API responses for real-time updates in the UI.

Key functions provide interfaces for:
-   Managing data collections (list, create, list files, upload files, delete documents).
-   Monitoring asynchronous tasks (e.g., file upload status).
-   Generating content via LLMs (queries, summaries/drafts, Q&A on artifacts).
-   Updating and finalizing reports.

The module aims to abstract the complexities of API communication, providing
clear and reusable functions for the main application logic.
It relies on the `requests` library for HTTP communication and uses `streamlit`
for displaying status messages and errors.
"""
import streamlit as st
import requests
import os
import json
from typing import List, Dict, Any, Optional, Generator

# Helper function to get base URL and API key from session state or env
def get_api_config():
    """
    Retrieves API configuration (base URLs and headers) from session state or environment variables.

    It fetches `RAG_INGEST_URL`, `AIRA_BASE_URL`, and `API_KEY`.
    If `RAG_INGEST_URL` is not found, it displays an error in Streamlit and stops execution.
    Constructs and returns common headers, including an Authorization header if an API key is present.

    Returns:
        tuple: A tuple containing:
            - RAG_INGEST_URL (str): The base URL for the RAG (Retrieval Augmented Generation) API.
            - headers (dict): HTTP headers for API requests, including Content-Type and Authorization.
            - aira_base_url (str): The base URL for the AIRA (AI Research Assistant) specific API.

    Raises:
        streamlit.errors.StreamlitAPIException: If `RAG_INGEST_URL` is not configured, `st.stop()` is called.
    """
    RAG_INGEST_URL = st.session_state.get('RAG_INGEST_URL') or os.getenv("RAG_INGEST_URL")
    aira_base_url = st.session_state.get('aira_base_url') or os.getenv("AIRA_BASE_URL")

    if not RAG_INGEST_URL:
        st.error("RAG_INGEST_URL is not configured. Please set it in your .env file.")
        st.stop()

    headers = {
        "Content-Type": "application/json",
    }

    return RAG_INGEST_URL, headers, aira_base_url

def handle_api_error(response: requests.Response):
    """
    Handles common API error responses by displaying them in the Streamlit UI.

    Attempts to parse a JSON error response to extract a detailed message.
    If parsing fails, it displays the raw response text.

    Args:
        response (requests.Response): The error response object from an API call.
    """
    try:
        error_data = response.json()
        detail = error_data.get("detail", "No specific error detail provided.")
        st.error(f"API Error ({response.status_code}): {detail}")
    except json.JSONDecodeError:
        st.error(f"API Error ({response.status_code}): {response.text}")

# --- API Functions ---
def list_collections() -> Optional[List[Dict[str, Any]]]:
    """
    Fetches a list of existing data collections from the RAG API.

    It uses the `LIST_COLLECTIONS_ENDPOINT` environment variable for the endpoint path.
    Handles potential request exceptions and JSON decoding errors, displaying
    errors in the Streamlit UI via `st.error` and `handle_api_error`.

    Returns:
        Optional[List[Dict[str, Any]]]: A list of dictionaries, where each dictionary
            represents a collection and contains its metadata (e.g., name, ID).
            Returns `None` if an error occurs or if the response format is unexpected.
    """
    RAG_INGEST_URL, headers, _ = get_api_config()
    endpoint = os.getenv("LIST_COLLECTIONS_ENDPOINT", "/collections")
    url = f"{RAG_INGEST_URL.rstrip('/')}{endpoint}"
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        response_data = response.json()
        
        # Extract the collections from the response format
        collections = response_data.get("collections", [])
        if collections is None:
            st.error("API Error: The response does not include 'collections'.")
            print(f"Unexpected response format for list_collections: {response_data}")
            return None
        if not isinstance(collections, list):
            st.error("API Error: 'collections' is expected to be a list.")
            print(f"Unexpected response format for list_collections: {response_data}")
            return None
        
        return collections
    except requests.exceptions.RequestException as e:
        st.error(f"Error listing collections: {e}")
        if hasattr(e, 'response') and e.response is not None:
            handle_api_error(e.response)
        return None
    except json.JSONDecodeError:
        st.error("API Error: Could not decode the collections response from the server.")
        return None

def create_collection(collection_name: str) -> Optional[str]:
    """
    Creates a new data collection via the RAG API.

    Uses the `CREATE_COLLECTION_ENDPOINT` environment variable for the endpoint path.
    Sends a POST request with the collection name.
    Displays success or error messages in the Streamlit UI.

    Args:
        collection_name (str): The name for the new collection to be created.

    Returns:
        Optional[str]: The ID or name of the newly created collection if successful,
            otherwise `None`. The exact return value (ID vs. name) depends on the
            API's response structure (currently expects an "id" field).
    """
    RAG_INGEST_URL, headers, _ = get_api_config()
    endpoint = os.getenv("CREATE_COLLECTION_ENDPOINT", "/collections")
    url = f"{RAG_INGEST_URL.rstrip('/')}{endpoint}"
    payload = [collection_name]
    params = {"vdb_endpoint": "http://milvus:19530", "collection_type": "text", "embedding_dimension": 2048}

    try:
        with st.spinner(f"Creating collection '{collection_name}'..."):
            response = requests.post(url, headers=headers, json=payload, params=params)
            response.raise_for_status() # Raises HTTPError for bad responses (4xx or 5xx)

        response_data = response.json()
        collection_name = response_data.get("successful")[0] # Adjust based on actual API response
        if collection_name:
            st.success(f"Collection '{collection_name}' created successfully (ID: {collection_name}).")
            return str(collection_name)
        else:
            st.error(f"Failed to create collection: No ID returned in response {response_data}")
            return None
    except requests.exceptions.RequestException as e:
        st.error(f"Error creating collection: {e}")
        if hasattr(e, 'response') and e.response is not None:
            handle_api_error(e.response)
        return None
    except json.JSONDecodeError:
         st.error(f"API Error: Could not decode server response after creating collection. Status: {response.status_code}, Body: {response.text}")
         return None

# Update list_files_in_collection function
def list_files_in_collection(collection_name: str) -> Optional[List[Dict[str, Any]]]:
    """
    Lists all files (documents) within a specified collection using the RAG API.

    Uses the `LIST_FILES_ENDPOINT` environment variable for the endpoint path.
    Sends a GET request with `collection_name` as a query parameter.
    The API is expected to return a list of documents under a "documents" key.
    Handles errors and displays messages in the Streamlit UI.

    Args:
        collection_name (str): The name of the collection for which to list files.

    Returns:
        Optional[List[Dict[str, Any]]]: A list of dictionaries, where each dictionary
            represents a file and contains its metadata (e.g., `document_name`).
            Returns `None` if an error occurs or the response format is not as expected.
    """
    RAG_INGEST_URL, headers, _ = get_api_config()
    endpoint = os.getenv("LIST_FILES_ENDPOINT", "/documents")
    url = f"{RAG_INGEST_URL.rstrip('/')}{endpoint}"
    params = {"collection_name": collection_name}

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        response_data = response.json()
        # Extract files from the 'documents' key in the response
        files = response_data.get("documents")

        if files is None:
             st.error(f"API Error: Response for listing files in '{collection_name}' does not contain a 'documents' key.")
             print(f"Unexpected file list response: {response_data}")
             return None
        if not isinstance(files, list):
            st.error(f"API Error: Expected 'documents' to be a list for collection '{collection_name}', but received {type(files)}.")
            print(f"Unexpected file list response: {response_data}")
            return None

        # Assuming each item in the list is like {"document_name": "..."}
        # The function expects List[Dict[str, Any]], so this structure is fine.
        return files

    except requests.exceptions.RequestException as e:
        st.error(f"Error listing files for collection '{collection_name}': {e}")
        if hasattr(e, 'response') and e.response is not None:
            handle_api_error(e.response)
        return None
    except json.JSONDecodeError:
        st.error(f"API Error: Could not decode the list of files for collection '{collection_name}' from the server response.")
        return None

def upload_files(
    collection_name: str, 
    files: List[st.runtime.uploaded_file_manager.UploadedFile],
    blocking: bool = False,
    split_options: Optional[Dict[str, Any]] = {"chunk_size":512,"chunk_overlap":150}
) -> Optional[str]:
    """
    Uploads files to a specified collection via the RAG API.

    This function constructs a multipart/form-data request containing the files
    and a JSON payload with metadata like `collection_name`, `blocking` mode,
    and `split_options`. It uses the `UPLOAD_DOCUMENTS_ENDPOINT` environment variable.

    Args:
        collection_name (str): The name of the collection to upload files to.
        files (List[st.runtime.uploaded_file_manager.UploadedFile]): A list of files
            uploaded via Streamlit's file uploader.
        blocking (bool): If `True`, the API call waits for the upload and processing
            to complete. If `False` (default), the API returns a `task_id` for
            asynchronous status checking.
        split_options (Optional[Dict[str, Any]]): Dictionary specifying options for
            splitting documents during ingestion (e.g., `chunk_size`, `chunk_overlap`).
            Defaults to `{"chunk_size":512,"chunk_overlap":150}`.

    Returns:
        Optional[Union[str, bool]]: 
            - If `blocking` is `False`: Returns a `task_id` (str) if the upload is initiated
              successfully, otherwise `None`.
            - If `blocking` is `True`: Returns `True` (bool) if files are uploaded and
              processed successfully, otherwise `None` (though implicitly it might suggest
              failure if `None` is returned instead of `True` on success, based on current logic).
            Returns `None` on any major error.
    """
    RAG_INGEST_URL, base_headers, _ = get_api_config()
    # Get endpoint from environment variable, defaulting to /v1/documents
    endpoint = os.getenv("UPLOAD_DOCUMENTS_ENDPOINT", "/v1/documents")
    url = f"{RAG_INGEST_URL.rstrip('/')}{endpoint}"

    # Prepare headers for the request, ensuring Authorization is included if available.
    # requests library will set the Content-Type for multipart/form-data.
    request_headers = {}
    if "Authorization" in base_headers:
        request_headers["Authorization"] = base_headers["Authorization"]

    if not files:
        st.warning("No files selected for upload.")
        return None

    # Prepare file parts for multipart upload
    file_parts = [('documents', (file.name, file.getvalue(), file.type)) for file in files]
    
    data_payload = {
        "collection_name": collection_name,
        "blocking": blocking,
        "split_options": split_options
    }
    # The 'data' field is sent as a string in the form
    form_parts = file_parts + [('data', (None, json.dumps(data_payload)))]

    try:
        with st.spinner(f"Initiating upload of {len(files)} file(s) to '{collection_name}'..."):
            response = requests.post(url, headers=request_headers, files=form_parts)
            response.raise_for_status()
        
        response_data = response.json()
        
        if not blocking:
            task_id = response_data.get("task_id")
            if task_id:
                st.toast(f"Upload initiated. Task ID: {task_id}")
                return task_id
            else:
                st.error("API Error: Upload initiated (non-blocking) but no task_id was returned.")
                print(f"Unexpected response for non-blocking upload: {response_data}")
                return None
        else:
            st.success(f"{len(files)} file(s) uploaded successfully (blocking mode) to collection: {collection_name}.")
            return True

    except requests.exceptions.RequestException as e:
        st.error(f"Error uploading files to '{collection_name}': {e} {response.json()}")
        return None
    except json.JSONDecodeError:
        st.error(f"API Error: Could not decode server response after uploading files. Status: {response.status_code}, Body: {response.text}")
        return None
    except Exception as e:
        st.error(f"An unexpected error occurred during file upload: {e}")
        return None

def get_upload_status(task_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieves the status of an asynchronous file upload task from the RAG API.

    Uses the `GET_TASK_STATUS_ENDPOINT` environment variable. This is typically used
    when `upload_files` is called with `blocking=False`.

    Args:
        task_id (str): The ID of the upload task, previously returned by `upload_files`.

    Returns:
        Optional[Dict[str, Any]]: A dictionary containing the status information of the task
            if successful (e.g., progress, state). Returns `None` if an error occurs.
    """
    RAG_INGEST_URL, headers, _ = get_api_config()
    # Get endpoint from environment variable, defaulting to /v1/status
    endpoint = os.getenv("GET_TASK_STATUS_ENDPOINT", "/v1/status")
    url = f"{RAG_INGEST_URL.rstrip('/')}{endpoint}"
    
    params = {"task_id": task_id}

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching status for task ID '{task_id}': {e}")
        if hasattr(e, 'response') and e.response is not None:
            handle_api_error(e.response)
        return None
    except json.JSONDecodeError:
        st.error(f"API Error: Could not decode status response for task ID '{task_id}'. Status: {response.status_code}, Body: {response.text}")
        return None
    except Exception as e:
        st.error(f"An unexpected error occurred while fetching upload status: {e}")
        return None

def delete_document_from_collection(collection_name: str, document_name: str) -> bool:
    """
    Deletes a specific document from a specified collection via the RAG API.

    Uses the `DELETE_DOCUMENT_ENDPOINT` environment variable. Sends a DELETE request
    with `collection_name` as a query parameter and a list containing the
    `document_name` in the JSON payload.

    Args:
        collection_name (str): The name of the collection from which to delete the document.
        document_name (str): The name of the document to delete.

    Returns:
        bool: The function currently doesn't explicitly return `True` or `False` based on
            the success of the operation. It displays toast messages for success/error.
            A more robust implementation would return a boolean indicating success.
            (Current implementation implicitly suggests success if no exception occurs,
             but does not return a value from the main try block).
    """
    RAG_INGEST_URL, headers, _ = get_api_config()
    # Endpoint should not include document_name in the path; it's in the body.
    # collection_name is used as collection_name in query parameters.
    endpoint = os.getenv("DELETE_DOCUMENT_ENDPOINT", "/documents") # Default to /documents
    url = f"{RAG_INGEST_URL.rstrip('/')}{endpoint}"

    params = {"collection_name": collection_name}
    # The document_name to delete is sent in the body as a JSON list
    payload = [document_name]

    try:
        response = requests.delete(url, headers=headers, params=params, json=payload)
        response.raise_for_status()  # Raises HTTPError for bad responses (4xx or 5xx)
        st.toast(f"{response.text}")
    except requests.exceptions.RequestException as e:
        st.toast(f"Error deleting document '{document_name}' from collection '{collection_name}': {e}")
        if hasattr(e, 'response') and e.response is not None:
            handle_api_error(e.response)
    # The following catch block might be redundant if handle_api_error covers JSON issues from response.text
    # or if successful DELETE requests don't typically return a JSON body to decode.
    # However, keeping it for robustness in case of unexpected server responses.
    except json.JSONDecodeError:
        # This case might occur if the error response itself is not valid JSON,
        # or if a non-error response that we try to parse (e.g. if API spec changes) is not JSON.
        # For a typical DELETE, we might not expect a body on success.
        # response.text might be more informative here if available from a failed request.
        error_message = f"API Error: Could not decode server response after attempting to delete document."
        if 'response' in locals() and response is not None:
             error_message += f" Status: {response.status_code}, Body: {response.text}"
        else:
            error_message += " No response object available."
        st.error(error_message)

def generate_summary(
    topic: str,
    report_organization: str,
    queries: List[Dict[str, str]],
    search_web: bool,
    rag_collection: str,
    reflection_count: int,
    llm_name: str
) -> Optional[Generator[Dict[str, Any], None, None]]:
    """
    Generates a summary or draft report by streaming data from the AIRA API.

    This function sends a POST request to the `GENERATE_SUMMARY_STREAM_ENDPOINT`.
    The payload includes the report topic, organization structure, queries, and other
    generation parameters like web search permission, RAG collection, reflection count,
    and LLM name.

    It expects a server-sent events (SSE) stream. Each event's data part is parsed as JSON.
    -   "intermediate_step" events are accumulated in `st.session_state.thinking_summary_tokens`
        and yielded for real-time display of the model's thought process.
    -   "final_report" events populate `st.session_state.final_report_content` and
        `st.session_state.citations`.

    Args:
        topic (str): The main topic of the report.
        report_organization (str): The desired structure or outline for the report.
        queries (List[Dict[str, str]]): A list of queries to be used for information gathering.
        search_web (bool): Whether to allow the LLM to search the web.
        rag_collection (str): The name of the RAG collection to use for context.
        reflection_count (int): The number of reflection steps for the LLM.
        llm_name (str): The name of the language model to use.

    Returns:
        Optional[Generator[str, None, None]]: A generator that yields intermediate
            thinking steps (strings) from the API stream. Returns `None` if the API
            request fails or `AIRA_BASE_URL` is not configured.
    """
    _, headers, aira_base_url = get_api_config()
    if not aira_base_url:
        st.error("AIRA_BASE_URL is not configured. Cannot generate summary.")
        return None
        
    endpoint = os.getenv("GENERATE_SUMMARY_STREAM_ENDPOINT", "/generate_summary/stream")
    url = f"{aira_base_url.rstrip('/')}{endpoint}"
    
    payload = {
        "topic": topic,
        "report_organization": report_organization,
        "queries": queries,
        "search_web": search_web,
        "rag_collection": rag_collection,
        "reflection_count": reflection_count,
        "llm_name": llm_name
    }

    try:
        with st.spinner("Initiating summary generation stream..."):
            response = requests.post(url, headers=headers, json=payload, stream=True)
            response.raise_for_status() # Check for HTTP errors before starting to stream
        
        def stream_generator():
            st.session_state.thinking_summary_tokens = dict()
            try:
                for line in response.iter_lines():
                    if line:
                        decoded_line = line.decode('utf-8')
                        if decoded_line.startswith('data:'):
                            data_content = decoded_line[len('data:'):].strip()
                            if data_content: # Ensure content is not empty before parsing
                                try:
                                    data = json.loads(data_content)
                                    if data.get("intermediate_step") is not None:
                                        temp_dict = json.loads(data.get("intermediate_step"))
                                        yield temp_dict
                                    elif data.get("final_report") is not None:
                                        st.session_state.final_report_content = data.get("final_report")
                                        st.session_state.citations = data.get("citations", [])
                                except json.JSONDecodeError:
                                    st.warning(f"Could not decode stream chunk (JSON parse error): '{data_content}'")

            except requests.exceptions.ChunkedEncodingError as chunk_error:
                st.error(f"Error reading summary stream (chunked encoding error): {chunk_error}")
            except Exception as e: 
                st.error(f"An unexpected error occurred while processing the summary stream: {e}")
            finally:
                response.close()
        
        return stream_generator()

    except requests.exceptions.RequestException as e:
        st.error(f"Error initiating summary generation: {e}")
        if hasattr(e, 'response') and e.response is not None:
            handle_api_error(e.response)
        return None

def generate_query(
    topic: str,
    report_organization: str,
    num_queries: int,
    llm_name: str
) -> Optional[Generator[Dict[str, Any], None, None]]:
    """
    Generates research queries by streaming data from the AIRA API.

    Sends a POST request to the `GENERATE_QUERY_STREAM_ENDPOINT`. The payload includes
    the topic, report organization, number of queries desired, and LLM name.

    It expects a server-sent events (SSE) stream. Each event's data part is parsed as JSON.
    -   "intermediate_step" events (specifically the "generating_questions" part)
        are accumulated in `st.session_state.thinking_queries_tokens` and yielded for
        real-time display.
    -   The final set of queries from an event is stored in `st.session_state.final_queries`.

    Args:
        topic (str): The main topic for which to generate queries.
        report_organization (str): The desired structure or outline of the report,
            used as context for query generation.
        num_queries (int): The desired number of queries to generate.
        llm_name (str): The name of the language model to use.

    Returns:
        Optional[Generator[str, None, None]]: A generator that yields intermediate
            thinking steps (strings, specifically the "generating_questions" content)
            from the API stream. Returns `None` if the API request fails or `AIRA_BASE_URL`
            is not configured.
    """
    _, headers, aira_base_url = get_api_config()
    if not aira_base_url:
        st.error("AIRA_BASE_URL is not configured. Cannot generate queries.")
        return None

    endpoint = os.getenv("GENERATE_QUERY_STREAM_ENDPOINT", "/generate_query/stream")
    url = f"{aira_base_url.rstrip('/')}{endpoint}"

    payload = {
        "topic": topic,
        "report_organization": report_organization,
        "num_queries": num_queries,
        "llm_name": llm_name
    }

    try:
        with st.spinner("Initiating query generation stream..."):
            response = requests.post(url, headers=headers, json=payload, stream=True)
            response.raise_for_status() # Check for HTTP errors before starting to stream
        def stream_generator():
            try:
                for line in response.iter_lines():
                    if line:
                        decoded_line = line.decode('utf-8')
                        if decoded_line.startswith('data:'):
                            data_content = decoded_line[len('data:'):].strip()
                            if data_content:
                                try:
                                    data = json.loads(data_content)
                                    if data.get("intermediate_step") is not None:
                                        intermediate_step = json.loads(data.get("intermediate_step")).get("generating_questions")
                                        st.session_state.thinking_queries_tokens += intermediate_step
                                        yield intermediate_step
                                    else:
                                        st.session_state.final_queries = data.get("queries", [])
                                except json.JSONDecodeError:
                                    st.warning(f"Could not decode stream chunk (JSON parse error): '{data_content}'")
            except requests.exceptions.ChunkedEncodingError as chunk_error:
                st.error(f"Error reading query stream (chunked encoding error): {chunk_error}")
            except Exception as e:
                st.error(f"An unexpected error occurred while processing the query stream: {e}")
            finally:
                response.close()
        
        return stream_generator()

    except requests.exceptions.RequestException as e:
        st.error(f"Error initiating query generation: {e}")
        if hasattr(e, 'response') and e.response is not None:
            handle_api_error(e.response)
        return None

def update_draft_report(draft_content: str) -> bool:
    """
    Updates the content of a draft report via an API call.

    Sends a PUT (or POST/PATCH, depending on API design) request to the
    `UPDATE_DRAFT_ENDPOINT` with the new `draft_content`.

    Args:
        draft_content (str): The new content for the draft report.

    Returns:
        bool: `True` if the update is successful (API returns 2xx status),
            `False` otherwise. Displays success or error messages in Streamlit UI.
    """
    RAG_INGEST_URL, headers, _ = get_api_config()
    endpoint_template = os.getenv("UPDATE_DRAFT_ENDPOINT", "/reports/draft")
    endpoint = endpoint_template
    url = f"{RAG_INGEST_URL.rstrip('/')}{endpoint}"
    payload = {"content": draft_content} # Adjust payload based on API spec

    try:
        with st.spinner("Saving draft report..."):
            response = requests.put(url, headers=headers, json=payload) # Or POST/PATCH
            response.raise_for_status()
        st.success("Draft report saved successfully.")
        return True
    except requests.exceptions.RequestException as e:
        st.error(f"Error updating draft report: {e}")
        if hasattr(e, 'response') and e.response is not None:
            handle_api_error(e.response)
        return False

def artifact_qa(
    artifact: str,
    question: str,
    chat_history: List[str],  # Expects List[str] as per new payload
    use_internet: bool = False,
    rewrite_mode: Optional[str] = None,
    additional_context: Optional[str] = None,
    rag_collection: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Performs a Question/Answering or artifact modification task via the AIRA API.

    Sends a POST request to the `ARTIFACT_QA_ENDPOINT`. The payload includes an
    'artifact' (text content), a 'question' or instruction, chat history, and flags
    for internet use, rewrite mode, and additional context.

    Args:
        artifact (str): The primary text content (e.g., a document, a section of a report,
            a list of queries as a string) to be queried or modified.
        question (str): The user's question about the artifact or instruction for
            modifying it.
        chat_history (List[str]): A list of previous messages (user and assistant)
            in the current conversation, used to provide context to the LLM.
        use_internet (bool): Flag to allow the LLM to use internet search to answer
            the question or fulfill the instruction. Defaults to `False`.
        rewrite_mode (Optional[str]): Specifies how the artifact should be rewritten.
            Common values might be "entire" (rewrite the whole artifact based on the
            question/instruction) or `None` (just answer, don't rewrite). The exact
            behavior depends on the backend API. Defaults to `None`.
        additional_context (Optional[str]): Any supplementary context to be provided
            to the LLM along with the artifact and question. Defaults to `None`.
        rag_collection (Optional[str]): The name of a RAG collection to be used for
            retrieving relevant information to help answer the question or modify the
            artifact. Defaults to `None`.

    Returns:
        Optional[Dict[str, Any]]: A dictionary containing the API's response if successful.
            Expected keys are "assistant_reply" (str, the LLM's textual response) and
            "updated_artifact" (Any, the modified artifact if `rewrite_mode` was active;
            could be str, list, dict, etc.). Returns `None` if the API call fails,
            `AIRA_BASE_URL` is not configured, or the response is malformed.
    """
    _, headers, aira_base_url = get_api_config()  # Using AIRA base URL
    if not aira_base_url:
        st.error("AIRA_BASE_URL is not configured. Cannot perform Artifact Q&A.")
        return None

    endpoint = os.getenv("ARTIFACT_QA_ENDPOINT", "/artifact_qa")  # New configurable endpoint
    url = f"{aira_base_url.rstrip('/')}{endpoint}"
    
    print(url)

    payload = {
        "artifact": artifact,
        "question": question,
        "chat_history": chat_history,
        "use_internet": use_internet,
    }
    
    if rewrite_mode is not None:
        payload["rewrite_mode"] = rewrite_mode
    
    # Add optional fields to the payload only if they are provided (not None)
    if additional_context is not None:
        payload["additional_context"] = additional_context
    if rag_collection is not None:
        payload["rag_collection"] = rag_collection

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        response_data = response.json()
        
        print(f"Response data: {response_data}")
        # Expecting a dictionary with 'assistant_reply' and potentially 'updated_artifact'
        assistant_reply = response_data.get("assistant_reply")
        updated_artifact = response_data.get("updated_artifact") # This might be a string or structured data

        if assistant_reply is not None:
            # Return a dictionary containing both parts, let the caller decide how to use them
            return {
                "assistant_reply": str(assistant_reply),
                "updated_artifact": updated_artifact # Keep original type (str, list, dict)
            }
        else:
            st.error("Artifact Q&A API Error: 'assistant_reply' key missing in response.")
            print(f"Artifact Q&A unexpected response (missing assistant_reply): {response_data}")
            return None
            
    except requests.exceptions.RequestException as e:
        st.error(f"Error during Artifact Q&A request: {e}")
        if hasattr(e, 'response') and e.response is not None:
            handle_api_error(e.response)
        return None
    except json.JSONDecodeError:
        st.error(f"API Error: Could not decode server response for Artifact Q&A. Status: {response.status_code}, Body: {response.text}")
        return None
