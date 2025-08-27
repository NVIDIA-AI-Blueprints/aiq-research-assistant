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
"""Extraction utilities for AIRA evaluation workflow."""

import asyncio
import json
import logging
import os
import re
import time
from typing import Any
from typing import Dict
from typing import List
from typing import Tuple

import requests
from joblib import Parallel
from joblib import delayed
from pydantic import BaseModel
from pydantic import Field

logger = logging.getLogger(__name__)


def get_bear_token():
    """
    Helper function to get a Bear token for accessing APIs via the LLM Gateway
    """
    client_id = os.environ.get("NV_CLIENT_ID")
    secret = os.environ.get("NV_CLIENT_SECRET")

    if not client_id or not secret:
        raise ValueError("NV_CLIENT_ID and NV_CLIENT_SECRET environment variables must be set for LLM Gateway usage.")

    url = "https://prod.api.nvidia.com/oauth/api/v1/ssa/default/token"

    payload = json.dumps({
        "client_id": client_id,
        "client_secret": secret,
        "scope": "openai-readwrite azureopenai-readwrite",
        "grant_type": "client_credentials",
    })
    headers = {"Content-Type": "application/json"}

    response = requests.request("POST", url, headers=headers, data=payload)
    bear_token = response.json()["access_token"]

    return bear_token


# Prompts from report_extractor.py
FACT_CLAIM_EXTRACTION_PROMPT = """# Key Facts/Claims Extraction

You are tasked with extracting key facts, claims, and statements from a research report. These extractions will be used to evaluate the "groundness" of the report - that is, whether the details in the report are properly supported by the sources used in its creation.

## Your Task

Read the following research report carefully:

<report>
{final_report}
</report>

Extract a comprehensive list of key facts, claims, and statements made in this report. These should be specific, verifiable assertions that could be checked against source materials.

## Guidelines for Extraction
1. **Verbatim text**: Copy each fact/claim exactly as it appears in the report—no paraphrasing or re-wording.  
2. Focus on extracting **specific, concrete claims** rather than general observations or opinions.
3. Each extracted item should be a single, coherent statement that makes a clear assertion.
4. Prioritize extracting claims that:
   - Contain specific data, statistics, or measurements
   - Make causal assertions (X causes Y)
   - Describe specific events, discoveries, or developments
   - Attribute specific positions or actions to individuals or organizations
   - Make definitive statements about the state of a field or topic

5. Avoid extracting:
   - Vague generalizations
   - Obvious statements of common knowledge
   - The report's own conclusions or recommendations (unless they're presented as factual claims)
   - Purely methodological descriptions

## Important Note

You must extract these facts/claims ONLY from the provided report. Do not use any external context, knowledge, or sources. The goal is to identify what the report itself is claiming, not to evaluate the accuracy of these claims. Extract as many key facts/claims as you can.

## Output Format

Present your extracted facts/claims as a python list. Use the following format:
```
["fact1", "fact2", ... "factN"]
```

Begin your extraction now."""

FACT_CITATION_MAPPING_PROMPT = """You will be analyzing a research report to identify which citation numbers are associated with a specific fact or claim.

<report>
{final_report}
</report>

<fact>
{fact}
</fact>

Your task is to find the inline numeric citations that appear directly with this fact in the report and return them as a list of numbers.

## Citation Detection Rules

1. **Look for inline citations** formatted as integers in parentheses or square brackets:
   - `(3)` or `[3]` → citation number 3
   - `(2, 7, 11)` or `[2, 7, 11]` → citation numbers 2, 7, and 11
   - `(1, 5)` or `[1, 5]` → citation numbers 1 and 5

2. **Only include citations that directly appear with the fact**:
   - The citation must be in the same sentence as the fact OR immediately at the end of the sentence containing the fact
   - Do NOT include citations from other sentences, even if they seem topically related
   - Do NOT guess or infer citations based on topic similarity

3. **Handle edge cases**:
   - If no citation appears with the fact, return an empty list
   - If citation formatting is malformed or missing numbers, treat as no citation
   - Only count properly formatted numeric citations in parentheses or square brackets

## Output Format

Provide your final answer as a simple list of citation numbers in ascending order inside <answer> tags. Examples:
- If citations 1 and 5 appear with the fact: [1, 5]
- If only citation 3 appears with the fact: [3]
- If no citations appear with the fact: []"""


class FactsResponse(BaseModel):
    """Pydantic model for structured facts extraction"""
    facts: List[str] = Field(description="A list of extracted facts and claims")


class CitationsResponse(BaseModel):
    """Pydantic model for structured citation extraction"""
    citations: List[int] = Field(default_factory=list, description="Citation numbers; empty list means no citations.")


class BatchCitationsResponse(BaseModel):
    """Pydantic model for batch citation extraction"""
    fact_citations: Dict[str, List[int]] = Field(description="Mapping of facts to their citation numbers")


def _get_llm_client():
    """Initialize NVIDIA API client for LLM calls"""
    api_key = os.environ.get("NVIDIA_API_KEY")
    if not api_key:
        raise ValueError("NVIDIA_API_KEY environment variable not set. Please set it to use LLM extraction features.")

    from openai import OpenAI
    return OpenAI(base_url="https://integrate.api.nvidia.com/v1", api_key=api_key)


async def _get_llm_response_structured(
    prompt: str,
    response_format: BaseModel,
    model: str = "nvdev/meta/llama-3.1-70b-instruct",
    temperature: float = 0.0,
    max_tokens: int = 4096,
    max_retries: int = 2,
    top_p: float = 1.0,
) -> Any:
    """Get structured response from LLM"""

    # Use LLM Gateway with GPT-4o for citation pairing if model is a GPT model
    if model.startswith("gpt-"):
        try:
            from openai import AzureOpenAI

            api_key = get_bear_token()
            api_base = "https://prod.api.nvidia.com/llm/v1/azure"

            client = AzureOpenAI(
                api_version="2025-03-01-preview",
                azure_endpoint=api_base,
                api_key=api_key,
            )

            for attempt in range(max_retries):
                try:
                    response = client.beta.chat.completions.parse(
                        model="gpt-4o",  # Use simple model name for LLM Gateway
                        messages=[{
                            "role": "user", "content": prompt
                        }],
                        temperature=temperature,
                        top_p=top_p,
                        max_tokens=max_tokens,
                        response_format=response_format,
                    )

                    result = response.choices[0].message.parsed.model_dump()

                    # Handle CitationsResponse format
                    if isinstance(result, dict) and "citations" in result:
                        return result
                    elif isinstance(result, list):
                        return {"citations": result}
                    else:
                        return result

                except Exception as e:
                    logger.error(f"LLM Gateway attempt {attempt + 1} failed: {str(e)}")
                    if attempt == max_retries - 1:
                        raise Exception(f"Failed after {max_retries} attempts: {str(e)}")

        except ImportError:
            raise ImportError("AzureOpenAI is required for LLM Gateway usage. Please install: pip install openai")
        except Exception as e:
            logger.error(f"LLM Gateway error: {str(e)}")
            raise

    # Original NVIDIA API logic for all other models
    client = _get_llm_client()
    for attempt in range(max_retries):
        try:
            # NVIDIA API may not support structured parse, so we try both approaches
            try:
                response = client.beta.chat.completions.parse(
                    model=model,
                    messages=[{
                        "role": "user", "content": prompt
                    }],
                    temperature=temperature,
                    max_tokens=max_tokens,
                    top_p=top_p,
                    response_format=response_format,
                )
                result = response.choices[0].message.parsed.model_dump()
                return result
            except Exception as e:
                # Fallback: try json_object format
                try:
                    response = client.chat.completions.create(
                        model=model,
                        messages=[{
                            "role": "user", "content": prompt
                        }],
                        temperature=temperature,
                        top_p=top_p,
                        max_tokens=max_tokens,
                        response_format={"type": "json_object"},
                    )
                    content = response.choices[0].message.content

                    result = json.loads(content)

                    # Handle different response formats
                    if isinstance(result, dict):
                        if "facts" in result:
                            return result["facts"]
                        elif "key_facts_claims" in result:
                            return result["key_facts_claims"]
                        else:
                            # If it's a dict but no expected key, try to find a list value
                            for value in result.values():
                                if isinstance(value, list):
                                    return value
                            return []
                    elif isinstance(result, list):
                        # If the response is directly a list
                        return result
                    else:
                        return []

                except Exception as fallback_error:
                    logger.error(f"Fallback also failed: {fallback_error}")
                    raise e  # Re-raise the original error

        except Exception as e:
            logger.error(f"Attempt {attempt + 1} failed: {str(e)}")
            if attempt == max_retries - 1:
                raise Exception(f"Failed after {max_retries} attempts: {str(e)}")


def extract_rag_contexts(intermediate_steps: List[Dict]) -> List[Dict]:
    """Extract RAG contexts from intermediate steps."""
    contexts = []
    seen = set()

    for step in intermediate_steps:
        if isinstance(step, dict) and "rag_answer" in step:
            # Extract questions and contexts from rag_answer
            rag_text = step["rag_answer"]

            # Split by section separator
            sections = rag_text.split("\n---\n")

            for section in sections:
                if "QUERY:" in section and "ANSWER:" in section:
                    # Extract query
                    query_match = re.search(r"QUERY:\s*\n([^\n]+(?:\n(?!ANSWER:)[^\n]+)*)", section, re.DOTALL)
                    # Extract answer
                    answer_match = re.search(r"ANSWER:\s*\n(.*?)(?:\nCITATION:|$)", section, re.DOTALL)

                    if query_match and answer_match:
                        question = query_match.group(1).strip()
                        context = answer_match.group(1).strip()

                        # Create unique key to avoid duplicates
                        key = f"{question}||{context[:100]}"  # Use first 100 chars of context for uniqueness

                        if key not in seen and question and context:
                            seen.add(key)
                            contexts.append({"question": question, "context": context})

    return contexts


def extract_relevancy_judgements(intermediate_steps: List[Dict]) -> List[Dict]:
    """Extract relevancy judgements from intermediate steps."""
    judgements = []

    for step in intermediate_steps:
        if isinstance(step, dict) and "relevancy_checker" in step:
            relevancy_text = step["relevancy_checker"]

            # Parse relevancy scores from the text
            # Looking for patterns like "Relevancy score: no" or "Relevancy score: yes"
            score_pattern = r"Relevancy score:\s*(yes|no)"
            query_pattern = r"Query:\s*([^\n]+)"
            answer_pattern = r"Answer:\s*([^\n]+)"

            scores = re.findall(score_pattern, relevancy_text, re.IGNORECASE)
            queries = re.findall(query_pattern, relevancy_text)
            answers = re.findall(answer_pattern, relevancy_text)

            # Combine them into judgements
            for i in range(len(scores)):
                judgement = {"score": scores[i].lower() == "yes", "relevant": scores[i].lower() == "yes"}
                if i < len(queries):
                    judgement["query"] = queries[i].strip()
                if i < len(answers):
                    judgement["answer"] = answers[i].strip()
                judgements.append(judgement)

    return judgements


def extract_web_answers(intermediate_steps: List[Dict]) -> List[str]:
    """Extract web answers from intermediate steps."""
    web_answers = []

    for step in intermediate_steps:
        if isinstance(step, dict) and "web_research_results" in step:
            web_results = step["web_research_results"]

            # Extract individual answers from the web research results
            # The format appears to be XML-like with <source> tags
            answer_pattern = r"<answer>([^<]+)</answer>"
            matches = re.findall(answer_pattern, web_results)

            for match in matches:
                if match.strip() and not match.startswith("Error"):
                    web_answers.append(match.strip())

    return web_answers


def extract_reflections_and_queries(intermediate_steps: List[Dict]) -> Tuple[List[str], List[str]]:
    """Extract reflections and queries from reflections."""
    reflection_tokens = []

    # Collect all reflection tokens
    for step in intermediate_steps:
        if isinstance(step, dict) and "reflect_on_summary" in step:
            reflection_text = step["reflect_on_summary"]
            if reflection_text:
                reflection_tokens.append(reflection_text)

    # Join all tokens and process
    if not reflection_tokens:
        return [], []

    # Join all reflection content
    full_reflection_text = "".join(reflection_tokens)

    # Remove "Starting reflection" and split by <think>
    full_reflection_text = full_reflection_text.replace(" Starting reflection",
                                                        "").replace("\n Starting reflection \n", "")

    # Split by <think> to get individual reflections
    parts = full_reflection_text.split("<think>")

    reflections = []
    queries_from_reflection = []

    for part in parts:
        if part.strip():
            # Reconstruct the reflection with <think> tag
            reflection = f"<think>{part}"
            reflections.append(reflection)

            # Extract everything after </think> as the query
            if "</think>" in part:
                additional_q = part.split("</think>")[-1].strip()
                queries_from_reflection.append(additional_q)
            else:
                # If no closing tag, the whole thing might be after the think section
                queries_from_reflection.append("")

    return reflections, queries_from_reflection


def split_report_and_citations(final_report: str) -> Tuple[str, str]:
    """Split final report into summary and citation sections."""
    # Try multiple citation prefixes, including AIRA format with dashes
    citation_prefixes = [
        "## Sources---",  # AIRA format with dashes
        "## Sources",  # Standard format
        "### Sources---",  # Alternative with dashes
        "### Sources",  # Alternative format
        "## Citations",
        "### Citations"
    ]

    for prefix in citation_prefixes:
        if prefix in final_report:
            parts = final_report.split(prefix)
            if len(parts) > 1:
                citation_section = prefix + parts[-1].strip()
                summary_section = "\n\n".join(parts[:-1]).strip()
                return summary_section, citation_section

    # If no citation section found, check if the report ends with "Sources" section
    if final_report.strip().endswith("## Sources") or final_report.strip().endswith("### Sources"):
        # Empty sources section
        return final_report.replace("## Sources", "").replace("### Sources", "").strip(), ""

    return final_report, ""


async def extract_groundness_facts(final_report: str, llm: str, verbose: bool = False) -> List[str]:
    """Extract facts/claims from report using LLM.
    
    Args:
        final_report: The generated research report
        llm: The LLM instance to use (if None, will create default client)
        verbose: Whether to enable verbose logging
    """
    if verbose:
        logger.info("Starting fact/claim extraction from report")

    try:
        prompt = FACT_CLAIM_EXTRACTION_PROMPT.format(final_report=final_report)

        raw_result = await _get_llm_response_structured(
            prompt,
            response_format=FactsResponse,
            model=llm,
            temperature=0.0,
            max_tokens=4096,
        )

        # Handle both dict and list returns
        if isinstance(raw_result, list):
            facts = raw_result
        elif isinstance(raw_result, dict) and "facts" in raw_result:
            facts = raw_result["facts"]
        else:
            logger.warning(f"Unexpected result format for facts extraction: {type(raw_result)}")
            facts = []

        if verbose:
            logger.info(f"Successfully extracted {len(facts)} groundness facts/claims")
            if facts and len(facts) <= 3:
                logger.debug("Sample facts:")
                for i, fact in enumerate(facts[:3], 1):
                    logger.debug("  %d. %s", i, fact[:150] + "..." if len(fact) > 150 else fact)
        else:
            logger.info(f"Extracted {len(facts)} groundness facts/claims")

        return facts

    except Exception as e:
        logger.error(f"Failed to extract groundness facts: {str(e)}")
        if verbose:
            logger.exception("Full exception details:")
        return []


def parse_aira_sources(citation_section: str) -> Dict[int, str]:
    """
    Parse AIRA citation section to extract source number and content.
    
    Args:
        citation_section: The citation section from AIRA report
        
    Returns:
        Dict mapping source numbers to their content
    """
    sources = {}

    # Match patterns like "**Source** 1" or "**Source** 2"
    pattern = re.compile(
        r"\*\*Source\*\*\s*(\d+).*?"  # capture source number
        r"\*\*Answer:\*\*\s*"  # locate the Answer header
        r"(.*?)"  # non-greedy capture of answer content
        r"(?=\n---|\*\*Source\*\*|\Z)",  # stop at next source or end
        flags=re.S | re.M)

    for match in pattern.finditer(citation_section):
        source_num = int(match.group(1))
        answer_content = match.group(2).strip()

        # Clean up the answer content by removing CITATION: section
        if "CITATION:" in answer_content:
            answer_content = answer_content.split("CITATION:")[0].strip()

        sources[source_num] = answer_content

    return sources


async def pair_facts_with_aira_sources(facts: List[str],
                                       citation_section: str,
                                       llm: str,
                                       verbose: bool = False) -> List[Tuple[str, List[int]]]:
    """
    Pair facts with AIRA sources when no inline citations exist.
    
    Args:
        facts: List of facts to pair with sources
        citation_section: The citation section from AIRA report
        llm: LLM to use for fact-source matching
        verbose: Whether to enable verbose logging
        
    Returns:
        List of tuples containing (fact, source_numbers)
    """
    if not facts:
        if verbose:
            logger.info("No facts provided for AIRA source matching")
        return []

    if verbose:
        logger.info(f"Starting AIRA source matching for {len(facts)} facts")
        logger.info(f"Citation section length: {len(citation_section)} characters")

    # Parse sources from citation section
    sources = parse_aira_sources(citation_section)

    if not sources:
        if verbose:
            logger.warning("No sources found in citation section")
            logger.warning(f"Citation section preview: {citation_section[:500]}...")
        return [(fact, []) for fact in facts]

    if verbose:
        logger.info(f"Found {len(sources)} sources in citation section: {list(sources.keys())}")
        for source_num, content in sources.items():
            logger.debug(f"Source {source_num}: {content[:100]}...")

    # Use LLM to match facts with sources
    fact_source_pairs = []
    successful_matches = 0
    failed_matches = 0

    for i, fact in enumerate(facts):
        if verbose and i > 0 and i % 10 == 0:
            logger.info(f"Progress: {i}/{len(facts)} facts processed")

        # Create prompt to match fact with relevant sources
        sources_text = "\n\n".join([f"**Source {num}:**\n{content}" for num, content in sources.items()])

        prompt = f"""You are analyzing a research fact and determining which sources support it.

**Fact to analyze:**
{fact}

**Available sources:**
{sources_text}

**Task:** Identify which source numbers (if any) contain information that supports this fact.

**Rules:**
1. Only include sources that directly support or contain information about the fact
2. Do not include sources that are only tangentially related
3. If no sources support the fact, return an empty list
4. Return only the source numbers as a JSON list

**Output format:** Return only a JSON list of source numbers, e.g., [1, 3] or [] if no sources support the fact.
"""

        try:
            raw_result = await _get_llm_response_structured(
                prompt,
                response_format=CitationsResponse,
                model=llm,
                temperature=0.0,
                max_tokens=100,
            )

            # Handle response format
            if isinstance(raw_result, dict) and "citations" in raw_result:
                matched_sources = raw_result["citations"]
            elif isinstance(raw_result, list):
                matched_sources = raw_result
            else:
                matched_sources = []
                if verbose:
                    logger.warning(f"Unexpected LLM response format for fact {i+1}: {type(raw_result)}")

            # Validate source numbers exist
            valid_sources = [s for s in matched_sources if s in sources]

            if matched_sources != valid_sources:
                invalid_sources = [s for s in matched_sources if s not in sources]
                if verbose:
                    logger.warning(f"Fact {i+1}: Invalid source numbers {invalid_sources} ignored")

            if valid_sources:
                successful_matches += 1
                if verbose:
                    logger.debug(f"Fact {i+1} matched to sources {valid_sources}: {fact[:50]}...")
            else:
                if verbose:
                    logger.debug(f"Fact {i+1} matched to no sources: {fact[:50]}...")

            fact_source_pairs.append((fact, valid_sources))

        except Exception as e:
            failed_matches += 1
            if verbose:
                logger.error(f"Error matching fact {i+1} to sources: {e}")
                logger.debug(f"Failed fact: {fact[:100]}...")
            fact_source_pairs.append((fact, []))

    if verbose:
        logger.info(f"AIRA source matching completed:")
        logger.info(f"  - Total facts processed: {len(fact_source_pairs)}")
        logger.info(f"  - Successful matches: {successful_matches}")
        logger.info(f"  - Failed matches: {failed_matches}")
        logger.info(
            f"  - Facts with sources: {successful_matches}/{len(fact_source_pairs)} ({100.0 * successful_matches / len(fact_source_pairs):.1f}%)"
        )

    return fact_source_pairs


async def pair_facts_with_citations(final_report: str,
                                    facts: List[str],
                                    llm: str,
                                    verbose: bool = False) -> List[Tuple[str, List[int]]]:
    """
    Pair facts with their citations using LLM.
    
    Args:
        final_report: The generated research report text
        facts: List of facts to find citations for
        llm: The LLM instance to use (if None, will create default client)
        verbose: Whether to enable verbose logging
        
    Returns:
        List of tuples containing (fact, citations)
    """
    if not facts:
        return []

    if verbose:
        logger.info("Starting fact-citation pairing")
        logger.info("  - Number of facts to process: %d", len(facts))

    # Check if the final_report actually contains inline citations
    # Use a more specific pattern that excludes 4-digit years
    citation_pattern = re.compile(r'\(([1-9][0-9]?)\)|\[([1-9][0-9]?)\]')  # Matches (1) to (99) but not (2023)
    citation_matches = citation_pattern.findall(final_report)

    if not citation_matches:
        if verbose:
            logger.warning("No inline citations found in final_report!")
            logger.warning("Attempting to use AIRA source format instead...")

        # Try to extract citation section and use AIRA format
        summary_section, citation_section = split_report_and_citations(final_report)

        if citation_section:
            if verbose:
                logger.info("Found citation section, using AIRA source matching")
            return await pair_facts_with_aira_sources(facts, citation_section, llm, verbose)
        else:
            if verbose:
                logger.warning("No citation section found either. All facts will be marked as having no citations.")
            return [(fact, []) for fact in facts]

    if verbose:
        logger.info(f"Found {len(citation_matches)} inline citations in report: {set(citation_matches)}")

    # If we have inline citations, proceed with the original logic
    async def _pair_single_fact(fact: str, fact_idx: int) -> List[int]:
        """Helper function for parallel processing"""
        try:
            prompt = FACT_CITATION_MAPPING_PROMPT.format(final_report=final_report, fact=fact)

            # Use GPT-4o specifically for citation pairing instead of the passed llm parameter
            raw_result = await _get_llm_response_structured(
                prompt,
                response_format=CitationsResponse,
                model=llm,
                temperature=0.0,
                max_tokens=5000,
            )

            # Handle both dict and list returns
            if isinstance(raw_result, list):
                citations = raw_result
            elif isinstance(raw_result, dict) and "citations" in raw_result:
                citations = raw_result["citations"]
            else:
                citations = []

            # Ensure citations are integers
            citations = [int(c) for c in citations if isinstance(c, (int, str)) and str(c).isdigit()]

            # Validate that citations actually exist in the report
            valid_citations = []
            for citation in citations:
                if f"({citation})" in final_report or f"[{citation}]" in final_report:
                    valid_citations.append(citation)
                elif verbose:
                    logger.warning(f"Citation {citation} not found in report for fact: {fact[:50]}...")

            citations = valid_citations

            return citations

        except Exception as e:
            logger.error(f"Failed to pair fact with citations: {str(e)}")
            if verbose:
                logger.debug("Failed fact: %s", fact[:100] + "..." if len(fact) > 100 else fact)
            return []

    # Process facts one by one (async doesn't benefit from joblib parallel)
    paired_results = []
    for idx, fact in enumerate(facts):
        if verbose and idx > 0 and idx % 10 == 0:
            logger.info("  - Progress: %d/%d facts processed", idx, len(facts))

        citations = await _pair_single_fact(fact, idx)
        paired_results.append((fact, citations))

    if verbose:
        facts_with_citations = sum(1 for _, citations in paired_results if citations)
        logger.info("Fact-citation pairing complete:")
        logger.info("  - Total facts processed: %d", len(paired_results))
        logger.info("  - Facts with citations: %d (%.1f%%)",
                    facts_with_citations,
                    100.0 * facts_with_citations / len(paired_results) if paired_results else 0)
        logger.info("  - Facts without citations: %d", len(paired_results) - facts_with_citations)
    else:
        logger.info(f"Paired {len(paired_results)} facts with citations")

    return paired_results


# Add the batch citation pairing prompt and function before the existing pair_facts_with_citations function

BATCH_FACT_CITATION_MAPPING_PROMPT = """You will be analyzing a research report to identify which citation numbers are associated with each fact or claim.

<report>
{final_report}
</report>

<facts>
{facts_json}
</facts>

Your task is to process ALL facts at once and return which inline numeric citations appear directly with each fact in the report.

## Citation Detection Rules

1. **Look for inline citations** formatted as integers in parentheses or square brackets:
   - `(3)` or `[3]` → citation number 3
   - `(2, 7, 11)` or `[2, 7, 11]` → citation numbers 2, 7, and 11
   - `(1, 5)` or `[1, 5]` → citation numbers 1 and 5

2. **Only include citations that directly appear with the fact**:
   - The citation must be in the same sentence as the fact OR immediately at the end of the sentence containing the fact
   - Do NOT include citations from other sentences, even if they seem topically related
   - Do NOT guess or infer citations based on topic similarity

3. **Handle edge cases**:
   - If no citation appears with the fact, return an empty list for that fact
   - If citation formatting is malformed or missing numbers, treat as no citation
   - Only count properly formatted numeric citations in parentheses or square brackets

## Output Format

Return a JSON object where each key is the fact text and the value is a list of citation numbers in ascending order. Example:

```json
{{
  "Fact 1 text here": [1, 3],
  "Fact 2 text here": [2],
  "Fact 3 text here": []
}}
```

Process all facts and return the complete mapping."""


async def batch_pair_facts_with_citations(final_report: str,
                                          facts: List[str],
                                          llm: str,
                                          verbose: bool = False) -> List[Tuple[str, List[int]]]:
    """
    Batch pair all facts with their citations using a single LLM call.
    
    Args:
        final_report: The generated research report text
        facts: List of facts to find citations for
        llm: The LLM instance to use
        verbose: Whether to enable verbose logging
        
    Returns:
        List of tuples containing (fact, citations)
    """
    if not facts:
        if verbose:
            logger.info("No facts provided for citation pairing")
        return []

    if verbose:
        logger.info("Starting batch fact-citation pairing")
        logger.info("  - Number of facts to process: %d", len(facts))
        logger.info("  - Final report length: %d characters", len(final_report))

    # Check if the final_report actually contains inline citations
    citation_pattern = re.compile(r'\(([1-9][0-9]?)\)|\[([1-9][0-9]?)\]')
    citation_matches = citation_pattern.findall(final_report)

    if not citation_matches:
        if verbose:
            logger.warning("No inline citations found in final_report!")
            logger.warning("Attempting to use AIRA source format instead...")

        # Try to extract citation section and use AIRA format
        summary_section, citation_section = split_report_and_citations(final_report)

        if verbose:
            logger.info(f"Split report: summary_length={len(summary_section)}, citation_length={len(citation_section)}")

        if citation_section:
            if verbose:
                logger.info("Found citation section, using AIRA source matching")
                logger.info(f"Citation section preview: {citation_section[:200]}...")

            # Use AIRA source matching
            try:
                result = await pair_facts_with_aira_sources(facts, citation_section, llm, verbose)
                if verbose:
                    facts_with_citations = sum(1 for _, citations in result if citations)
                    logger.info(
                        f"AIRA source matching completed: {facts_with_citations}/{len(result)} facts have citations")
                return result
            except Exception as e:
                if verbose:
                    logger.error(f"AIRA source matching failed: {str(e)}")
                    logger.exception("Full exception details:")
                # Fall back to empty citations
                return [(fact, []) for fact in facts]
        else:
            if verbose:
                logger.warning("No citation section found either. All facts will be marked as having no citations.")
            return [(fact, []) for fact in facts]

    if verbose:
        logger.info(f"Found {len(citation_matches)} inline citations in report")
        unique_citations = set()
        for match in citation_matches:
            for group in match:
                if group:
                    unique_citations.add(int(group))
        logger.info(f"Unique citation numbers: {sorted(unique_citations)}")

    try:
        # Create JSON representation of facts for the prompt
        facts_json = json.dumps(facts, indent=2)

        prompt = BATCH_FACT_CITATION_MAPPING_PROMPT.format(final_report=final_report, facts_json=facts_json)

        if verbose:
            logger.info("Sending batch citation pairing request to LLM...")

        raw_result = await _get_llm_response_structured(
            prompt,
            response_format=BatchCitationsResponse,
            model=llm,
            temperature=0.0,
            max_tokens=8192,  # Increased for batch processing
        )

        # Handle response format
        if isinstance(raw_result, dict) and "fact_citations" in raw_result:
            fact_citations_dict = raw_result["fact_citations"]
        else:
            if verbose:
                logger.warning(f"Unexpected response format: {type(raw_result)}")
                logger.warning(f"Raw result: {raw_result}")
                logger.warning("Falling back to AIRA source matching...")

            # Fallback to AIRA source matching when inline citation processing fails
            summary_section, citation_section = split_report_and_citations(final_report)

            if citation_section:
                if verbose:
                    logger.info("Found citation section, using AIRA source matching as fallback")
                    logger.info(f"Citation section preview: {citation_section[:200]}...")

                try:
                    result = await pair_facts_with_aira_sources(facts, citation_section, llm, verbose)
                    if verbose:
                        facts_with_citations = sum(1 for _, citations in result if citations)
                        logger.info(
                            f"AIRA source matching fallback completed: {facts_with_citations}/{len(result)} facts have citations"
                        )
                    return result
                except Exception as e:
                    if verbose:
                        logger.error(f"AIRA source matching fallback failed: {str(e)}")
                        logger.exception("Full exception details:")
                    # Fall back to empty citations
                    return [(fact, []) for fact in facts]
            else:
                if verbose:
                    logger.warning(
                        "No citation section found for fallback. All facts will be marked as having no citations.")
                return [(fact, []) for fact in facts]

        # Convert back to list of tuples, preserving order
        paired_results = []
        for fact in facts:
            citations = fact_citations_dict.get(fact, [])

            # Ensure citations are integers
            citations = [int(c) for c in citations if isinstance(c, (int, str)) and str(c).isdigit()]

            # Validate that citations actually exist in the report
            valid_citations = []
            for citation in citations:
                if f"({citation})" in final_report or f"[{citation}]" in final_report:
                    valid_citations.append(citation)
                elif verbose:
                    logger.warning(f"Citation {citation} not found in report for fact: {fact[:50]}...")

            paired_results.append((fact, valid_citations))

        # Check if citation pairing was successful
        facts_with_citations = sum(1 for _, citations in paired_results if citations)

        if verbose:
            logger.info("Batch fact-citation pairing complete:")
            logger.info("  - Total facts processed: %d", len(paired_results))
            logger.info("  - Facts with citations: %d (%.1f%%)",
                        facts_with_citations,
                        100.0 * facts_with_citations / len(paired_results) if paired_results else 0)
            logger.info("  - Facts without citations: %d", len(paired_results) - facts_with_citations)

        # If no facts have citations despite finding inline citations, try AIRA fallback
        if facts_with_citations == 0 and citation_matches:
            if verbose:
                logger.warning(
                    "No facts were successfully paired with inline citations. Trying AIRA source matching as fallback..."
                )

            summary_section, citation_section = split_report_and_citations(final_report)

            if citation_section:
                if verbose:
                    logger.info("Found citation section, using AIRA source matching as secondary fallback")
                    logger.info(f"Citation section preview: {citation_section[:200]}...")

                try:
                    result = await pair_facts_with_aira_sources(facts, citation_section, llm, verbose)
                    if verbose:
                        facts_with_citations_fallback = sum(1 for _, citations in result if citations)
                        logger.info(
                            f"AIRA source matching secondary fallback completed: {facts_with_citations_fallback}/{len(result)} facts have citations"
                        )
                    return result
                except Exception as e:
                    if verbose:
                        logger.error(f"AIRA source matching secondary fallback failed: {str(e)}")
                        logger.exception("Full exception details:")

        if not verbose:
            logger.info(f"Batch paired {len(paired_results)} facts with citations")

        return paired_results

    except Exception as e:
        logger.error(f"Batch fact-citation pairing failed: {str(e)}")
        if verbose:
            logger.exception("Full exception details:")

        # Try AIRA source matching as fallback before individual processing
        if verbose:
            logger.info("Trying AIRA source matching as exception fallback...")

        summary_section, citation_section = split_report_and_citations(final_report)

        if citation_section:
            if verbose:
                logger.info("Found citation section, using AIRA source matching as exception fallback")
                logger.info(f"Citation section preview: {citation_section[:200]}...")

            try:
                result = await pair_facts_with_aira_sources(facts, citation_section, llm, verbose)
                if verbose:
                    facts_with_citations = sum(1 for _, citations in result if citations)
                    logger.info(
                        f"AIRA source matching exception fallback completed: {facts_with_citations}/{len(result)} facts have citations"
                    )
                return result
            except Exception as e2:
                if verbose:
                    logger.error(f"AIRA source matching exception fallback failed: {str(e2)}")
                    logger.exception("Full exception details:")

        # Final fallback to individual processing
        if verbose:
            logger.info("Falling back to individual fact processing...")
        return await pair_facts_with_citations(final_report, facts, llm, verbose)


# Prompt templates for preprocessing
QG_TEMPLATE = """# Evaluation Question Generator

You are tasked with generating evaluation questions that will help assess the relevance of retrieved contexts to a research topic. These questions will be used to evaluate how well an AI research system retrieves relevant information for creating comprehensive reports.

## Research Topic
<research_topic>
{topic}
</research_topic>

## Ground Truth Report
This is a high-quality research report on the topic that can be used as reference for generating targeted evaluation questions:

<ground_truth_report>
{ground_truth}
</ground_truth_report>

## Your Task: Generate Evaluation Questions

Generate 16 specific, targeted questions that can be used to evaluate whether retrieved contexts are relevant to the research topic. Follow these guidelines:

1. Questions should be specific enough that they can only be answered correctly if the retrieved contexts contain relevant information
2. Include questions that test for the presence of critical information that would be expected in high-quality research on this topic
3. Questions should cover different aspects and subtopics of the research area
4. Avoid questions that are too general or that could be answered without specific knowledge of the topic

## Step-by-Step Approach

1. First, carefully read and analyze the research topic to understand the main subject area.
2. Then, thoroughly read the ground truth report, identifying:
   - Key facts, statistics, and data points
   - Main arguments and conclusions
   - Important subtopics and their relationships
   - Other important details

3. Based on your analysis, identify 10-15 distinct aspects of the research topic that are crucial for comprehensive understanding.

4. For each aspect, formulate a specific question that:
   - Targets information that would only be present in relevant contexts
   - Cannot be answered with general knowledge alone
   - Relates directly to content in the ground truth report

5. For each question, write a brief rationale explaining:
   - Why this question is important for evaluating context relevance
   - What specific aspect of the research topic it addresses

## Output Format

Your output should be a Python list of dictionaries with the following structure:

```
[
  {{
    "question": "<question>",
    "rationale": "<rationale>",
    "aspect": "<aspect>"
  }},
  ...
]
```

Remember that these questions will be used to evaluate retrieved contexts that you don't know beforehand. The questions should help determine whether those contexts contain the most relevant information for the research topic.

Please provide your list of evaluation questions now."""

FACT_EXTRACTION_TEMPLATE = """# Key Facts/Claims Extraction

You are tasked with extracting key facts, claims, and statements from a research report. These extractions will be used to evaluate the "groundness" of the report - that is, whether the details in the report are properly supported by the sources used in its creation.

## Your Task

Read the following research report carefully:

<ground_truth_report>
{ground_truth}
</ground_truth_report>

Extract a comprehensive list of key facts, claims, and statements made in this report. These should be specific, verifiable assertions that could be checked against source materials.

## Guidelines for Extraction
1. **Verbatim text**: Copy each fact/claim exactly as it appears in the report—no paraphrasing or re-wording.  
2. Focus on extracting **specific, concrete claims** rather than general observations or opinions.
3. Each extracted item should be a single, coherent statement that makes a clear assertion.
4. Prioritize extracting claims that:
   - Contain specific data, statistics, or measurements
   - Make causal assertions (X causes Y)
   - Describe specific events, discoveries, or developments
   - Attribute specific positions or actions to individuals or organizations
   - Make definitive statements about the state of a field or topic

5. Avoid extracting:
   - Vague generalizations
   - Obvious statements of common knowledge
   - The report's own conclusions or recommendations (unless they're presented as factual claims)
   - Purely methodological descriptions


## Important Note

You must extract these facts/claims ONLY from the provided report. Do not use any external context, knowledge, or sources. The goal is to identify what the report itself is claiming, not to evaluate the accuracy of these claims. Extract up to 32 key facts/claims, prioritizing the most important and specific assertions.

## Output Format

Present your extracted facts/claims as a python list. Use the following format:
```
["fact1", "fact2", ... "factN"]
```

Begin your extraction now."""


class QuestionsResponse(BaseModel):
    """Pydantic model for structured questions extraction"""
    questions: List[Dict[str, str]] = Field(description="A list of evaluation questions with rationale and aspect")


class FactsResponse(BaseModel):
    """Pydantic model for structured facts extraction"""
    facts: List[str] = Field(description="A list of key facts/claims extracted from the ground truth")


async def generate_context_relevance_questions(topic: str,
                                               ground_truth: str,
                                               llm: str = "nvdev/meta/llama-3.1-70b-instruct",
                                               verbose: bool = False) -> List[Dict[str, str]]:
    """Generate evaluation questions using the ground truth report.
    
    Args:
        topic: The research topic
        ground_truth: The ground truth report text
        llm: The LLM model to use
        verbose: Whether to enable verbose logging
        
    Returns:
        List of dictionaries with question, rationale, and aspect
    """
    if verbose:
        logger.info("Starting context relevance questions generation")
        logger.info("  - Topic: %s", topic[:100] + "..." if len(topic) > 100 else topic)
        logger.info("  - Ground truth length: %d characters", len(ground_truth))

    try:
        prompt = QG_TEMPLATE.format(topic=topic, ground_truth=ground_truth)

        raw_result = await _get_llm_response_structured(
            prompt,
            response_format=QuestionsResponse,
            model=llm,
            temperature=0.0,
            max_tokens=4096,
        )

        # Handle both dict and list returns
        if isinstance(raw_result, list):
            questions = raw_result
        elif isinstance(raw_result, dict) and "questions" in raw_result:
            questions = raw_result["questions"]
        else:
            logger.warning(f"Unexpected result format for questions generation: {type(raw_result)}")
            questions = []

        # Validate question format
        validated_questions = []
        for q in questions:
            if isinstance(q, dict) and all(k in q for k in ['question', 'rationale', 'aspect']):
                validated_questions.append(q)

        if verbose:
            logger.info(f"Successfully generated {len(validated_questions)} context relevance questions")
            if validated_questions and len(validated_questions) <= 3:
                logger.debug("Sample questions:")
                for i, q in enumerate(validated_questions[:3], 1):
                    logger.debug("  %d. %s",
                                 i,
                                 q['question'][:100] + "..." if len(q['question']) > 100 else q['question'])
        else:
            logger.info(f"Generated {len(validated_questions)} context relevance questions")

        return validated_questions

    except Exception as e:
        logger.error(f"Failed to generate context relevance questions: {str(e)}")
        if verbose:
            logger.exception("Full exception details:")
        return []


async def generate_coverage_facts_claims(ground_truth: str,
                                         llm: str = "nvdev/meta/llama-3.1-70b-instruct",
                                         verbose: bool = False) -> List[str]:
    """Extract key facts from the ground truth report for coverage evaluation.
    
    Args:
        ground_truth: The ground truth report text
        llm: The LLM model to use
        verbose: Whether to enable verbose logging
        
    Returns:
        List of key facts/claims extracted from the ground truth
    """
    if verbose:
        logger.info("Starting coverage facts/claims generation")
        logger.info("  - Ground truth length: %d characters", len(ground_truth))

    try:
        prompt = FACT_EXTRACTION_TEMPLATE.format(ground_truth=ground_truth)

        raw_result = await _get_llm_response_structured(
            prompt,
            response_format=FactsResponse,
            model=llm,
            temperature=0.0,
            max_tokens=4096,
        )

        # Handle both dict and list returns
        if isinstance(raw_result, list):
            facts = raw_result
        elif isinstance(raw_result, dict) and "facts" in raw_result:
            facts = raw_result["facts"]
        else:
            logger.warning(f"Unexpected result format for facts extraction: {type(raw_result)}")
            facts = []

        # Ensure we have a list of strings
        if isinstance(facts, list):
            facts = [str(fact) for fact in facts]
        else:
            logger.warning(f"Unexpected facts format: {type(facts)}")
            facts = []

        if verbose:
            logger.info(f"Successfully generated {len(facts)} coverage facts/claims")
            if facts and len(facts) <= 3:
                logger.debug("Sample facts:")
                for i, fact in enumerate(facts[:3], 1):
                    logger.debug("  %d. %s", i, fact[:100] + "..." if len(fact) > 100 else fact)
        else:
            logger.info(f"Generated {len(facts)} coverage facts/claims")

        return facts

    except Exception as e:
        logger.error(f"Failed to generate coverage facts/claims: {str(e)}")
        if verbose:
            logger.exception("Full exception details:")
        return []


def resolve_llm_to_model_name(builder, llm_ref: str) -> str:
    """
    Resolve LLM reference to actual model name for extraction utilities.
    
    Args:
        builder: The AIQ builder instance
        llm_ref: LLM reference (e.g., 'eval_llm') or actual model name (e.g., 'meta/llama-3.1-70b-instruct')
        
    Returns:
        str: The actual model name that can be used with extraction utilities
    """
    import logging
    logger = logging.getLogger(__name__)

    try:
        # Check if this is already a model name (contains "/" or starts with known prefixes)
        if "/" in llm_ref or llm_ref.startswith(("gpt-", "nvdev/", "meta/", "mistralai/")):
            return llm_ref

        # Try to get the LLM configuration from the builder
        if hasattr(builder, 'config') and hasattr(builder.config, 'llms'):
            llm_config = builder.config.llms.get(llm_ref)
            if llm_config and hasattr(llm_config, 'model_name'):
                logger.info(f"Resolved LLM reference '{llm_ref}' to model name '{llm_config.model_name}'")
                return llm_config.model_name

        # If we can't resolve it, log a warning and return as-is
        logger.warning(f"Could not resolve LLM reference '{llm_ref}' to model name, using as-is")
        return llm_ref

    except Exception as e:
        logger.error(f"Error resolving LLM reference '{llm_ref}': {str(e)}")
        return llm_ref
