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

from enum import Enum
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field


class ClusterTypeEnum(str, Enum):
    SIMILAR = "SIMILAR"
    FRESHNESS = "FRESHNESS"
    TITLE = "TITLE"
    CONTENT = "CONTENT"
    NONE = "NONE"
    THREAD_REPLY = "THREAD_REPLY"
    THREAD_ROOT = "THREAD_ROOT"
    PREFIX = "PREFIX"
    SUFFIX = "SUFFIX"


class ConnectorType(str, Enum):
    API_CRAWL = "API_CRAWL"
    BROWSER_CRAWL = "BROWSER_CRAWL"
    BROWSER_HISTORY = "BROWSER_HISTORY"
    BUILTIN = "BUILTIN"
    FEDERATED_SEARCH = "FEDERATED_SEARCH"
    PUSH_API = "PUSH_API"
    WEB_CRAWL = "WEB_CRAWL"
    NATIVE_HISTORY = "NATIVE_HISTORY"


class SearchResultProminenceEnum(str, Enum):
    HERO = "HERO"
    PROMOTED = "PROMOTED"
    STANDARD = "STANDARD"


class UserMetadata(BaseModel):
    last_extension_use: Optional[str] = Field(None, alias="lastExtensionUse")
    logging_id: Optional[str] = Field(None, alias="loggingId")


class User(BaseModel):
    name: Optional[str] = None
    obfuscated_id: Optional[str] = Field(None, alias="obfuscatedId")
    metadata: Optional[UserMetadata] = None


class DocumentContent(BaseModel):
    """Empty document content - can be extended as needed"""
    pass


class DocumentSection(BaseModel):
    """Empty document section - can be extended as needed"""
    pass


class CustomDataValue(BaseModel):
    string_value: Optional[str] = Field(None, alias="stringValue")


class CustomData(BaseModel):
    site: Optional[CustomDataValue] = None


class DocumentMetadata(BaseModel):
    datasource: Optional[str] = None
    datasource_instance: Optional[str] = Field(None, alias="datasourceInstance")
    object_type: Optional[str] = Field(None, alias="objectType")
    container: Optional[str] = None
    container_id: Optional[str] = Field(None, alias="containerId")
    super_container_id: Optional[str] = Field(None, alias="superContainerId")
    mime_type: Optional[str] = Field(None, alias="mimeType")
    document_id: Optional[str] = Field(None, alias="documentId")
    logging_id: Optional[str] = Field(None, alias="loggingId")
    create_time: Optional[str] = Field(None, alias="createTime")
    update_time: Optional[str] = Field(None, alias="updateTime")
    author: Optional[User] = None
    owner: Optional[User] = None
    visibility: Optional[str] = None
    assigned_to: Optional[User] = Field(None, alias="assignedTo")
    updated_by: Optional[User] = Field(None, alias="updatedBy")
    datasource_id: Optional[str] = Field(None, alias="datasourceId")
    interactions: Optional[Dict[str, Any]] = Field(default_factory=dict)
    path: Optional[str] = None
    custom_data: Optional[CustomData] = Field(None, alias="customData")
    document_category: Optional[str] = Field(None, alias="documentCategory")


class Document(BaseModel):
    connector_type: Optional[ConnectorType] = Field(None, alias="connectorType")
    container_document: Optional['Document'] = Field(None, alias="containerDocument")
    content: Optional[DocumentContent] = None
    datasource: Optional[str] = None
    doc_type: Optional[str] = Field(None, alias="docType")
    id: Optional[str] = None
    metadata: Optional[DocumentMetadata] = None
    parent_document: Optional['Document'] = Field(None, alias="parentDocument")
    sections: Optional[List[DocumentSection]] = None
    title: Optional[str] = None
    url: Optional[str] = None


class Person(BaseModel):
    email: Optional[str] = None


class Team(BaseModel):
    name: Optional[str] = None


class SearchResultSnippetRange(BaseModel):
    start_index: int = Field(..., alias="startIndex")
    end_index: int = Field(..., alias="endIndex")
    type: str = Field(..., alias="type")


class SearchResultSnippet(BaseModel):
    model_config = ConfigDict(extra="allow")

    snippet: str
    mime_type: Optional[str] = Field(None, alias="mimeType")
    text: Optional[str] = None
    snippet_text_ordering: Optional[int] = Field(None, alias="snippetTextOrdering")
    ranges: Optional[List[SearchResultSnippetRange]] = None
    url: Optional[str] = None


class RelatedDocuments(BaseModel):
    """Empty related documents - can be extended as needed"""
    pass


class ClusterGroup(BaseModel):
    visible_count_hint: int = Field(..., alias="visibleCountHint")


class QuerySuggestion(BaseModel):
    query: Optional[str] = None


class QuerySuggestionList(BaseModel):
    suggestions: Optional[List[QuerySuggestion]] = None


class PinDocument(BaseModel):
    id: Optional[str] = None
    document_id: Optional[str] = Field(None, alias="documentId")


class StructuredResult(BaseModel):
    """Empty structured result - can be extended as needed"""
    pass


class SearchResult(BaseModel):
    structured_results: Optional[List[StructuredResult]] = Field(None, alias="structuredResults")
    tracking_token: Optional[str] = Field(None, alias="trackingToken")
    document: Optional[Document] = None
    person: Optional[Person] = None
    team: Optional[Team] = None
    title: Optional[str] = None
    url: Optional[str] = None
    native_app_url: Optional[str] = Field(None, alias="nativeAppUrl")
    snippets: Optional[List[SearchResultSnippet]] = None
    full_text: Optional[str] = Field(None, alias="fullText")
    full_text_list: Optional[List[str]] = Field(None, alias="fullTextList")
    related_results: Optional[List[RelatedDocuments]] = Field(None, alias="relatedResults")
    clustered_results: Optional[List['SearchResult']] = Field(None, alias="clusteredResults")
    all_clustered_results: Optional[List[ClusterGroup]] = Field(None, alias="allClusteredResults")
    attachment_count: Optional[int] = Field(None, alias="attachmentCount")
    attachments: Optional[List['SearchResult']] = None
    backlink_results: Optional[List['SearchResult']] = Field(None, alias="backlinkResults")
    cluster_type: Optional[ClusterTypeEnum] = Field(None, alias="clusterType")
    must_include_suggestions: Optional[QuerySuggestionList] = Field(None, alias="mustIncludeSuggestions")
    query_suggestion: Optional[QuerySuggestion] = Field(None, alias="querySuggestion")
    prominence: Optional[SearchResultProminenceEnum] = None
    attachment_context: Optional[str] = Field(None, alias="attachmentContext")
    pins: Optional[List[PinDocument]] = None


class SearchResponseMetadata(BaseModel):
    rewritten_query: Optional[str] = Field(None, alias="rewrittenQuery")
    searched_query: Optional[str] = Field(None, alias="searchedQuery")
    searched_query_ranges: Optional[List[str]] = Field(None, alias="searchedQueryRanges")
    original_query: Optional[str] = Field(None, alias="originalQuery")
    query_suggestion: Optional[str] = Field(None, alias="querySuggestion")
    additional_query_suggestions: Optional[List[str]] = Field(None, alias="additionalQuerySuggestions")
    negated_terms: Optional[List[str]] = Field(None, alias="negatedTerms")
    modified_query_was_used: Optional[bool] = Field(None, alias="modifiedQueryWasUsed")
    original_query_had_no_results: Optional[bool] = Field(None, alias="originalQueryHadNoResults")


class ResultsDescription(BaseModel):
    text: Optional[str] = None
    icon_config: Optional[Dict[str, Any]] = Field(None, alias="iconConfig")


class ResultTab(BaseModel):
    id: Optional[str] = None
    count: Optional[int] = None
    datasource: Optional[str] = None
    datasource_instance: Optional[str] = Field(None, alias="datasourceInstance")


class FacetFilterValue(BaseModel):
    value: str
    relation_type: str = Field(..., alias="relationType")


class FacetFilter(BaseModel):
    field_name: str = Field(..., alias="fieldName")
    group_name: Optional[str] = Field(None, alias="groupName")
    values: List[FacetFilterValue]


class FacetResult(BaseModel):
    source_name: Optional[str] = Field(None, alias="sourceName")
    operator_name: Optional[str] = Field(None, alias="operatorName")
    buckets: Optional[List[Dict[str, Any]]] = None
    has_more_buckets: Optional[bool] = Field(None, alias="hasMoreBuckets")
    group_name: Optional[str] = Field(None, alias="groupName")


class ContentSearchResponse(BaseModel):
    """
    Response model for content search.

    This represents the response from the /v1/content/search endpoint.
    """
    backend_time_millis: Optional[int] = Field(None, alias="backendTimeMillis")
    cursor: Optional[str] = None
    error_info: Optional[Dict[str, Any]] = Field(None, alias="errorInfo")
    experiment_ids: Optional[List[int]] = Field(None, alias="experimentIds")
    facet_results: Optional[List[FacetResult]] = Field(None, alias="facetResults")
    generated_qna_result: Optional[Dict[str, Any]] = Field(None, alias="generatedQnaResult")
    has_more_results: Optional[bool] = Field(None, alias="hasMoreResults")
    metadata: Optional[SearchResponseMetadata] = None
    request_id: Optional[str] = Field(None, alias="requestID")
    results: Optional[List[SearchResult]] = None
    results_description: Optional[ResultsDescription] = Field(None, alias="resultsDescription")
    result_tab_ids: Optional[List[str]] = Field(None, alias="resultTabIds")
    result_tabs: Optional[List[ResultTab]] = Field(None, alias="resultTabs")
    rewritten_facet_filters: Optional[List[FacetFilter]] = Field(None, alias="rewrittenFacetFilters")
    session_info: Optional[Dict[str, Any]] = Field(None, alias="sessionInfo")
    structured_results: Optional[List[StructuredResult]] = Field(None, alias="structuredResults")
    tracking_token: Optional[str] = Field(None, alias="trackingToken")
    excluded_results_count: int = Field(..., alias="excludedResultsCount")

    class Config:
        allow_population_by_field_name = True
        use_enum_values = True


# Update forward references
Document.model_rebuild()
SearchResult.model_rebuild()
