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
import json
import logging
import os
import re
import time
import typing as t
from time import sleep
from typing import Dict
from typing import List
from typing import Tuple

from nat.data_models.component_ref import LLMRef
from nat.data_models.evaluator import EvaluatorBaseConfig
from nat.eval.evaluator.evaluator_model import EvalInput
from nat.eval.evaluator.evaluator_model import EvalInputItem
from nat.eval.evaluator.evaluator_model import EvalOutput
from nat.eval.evaluator.evaluator_model import EvalOutputItem
from langchain_core.language_models.base import BaseLanguageModel
from langchain_openai import ChatOpenAI
from pydantic import Field
from ragas.dataset_schema import SingleTurnSample
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import ResponseGroundedness

from aiq_aira.eval.schema import AIResearcherEvalOutput

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Monkey-patch ChatOpenAI so it has the async helpers RAGAS expects.
# ------------------------------------------------------------------
if not hasattr(ChatOpenAI, "agenerate_text"):

    async def _agenerate_text(self, *args, **kwargs):  # type: ignore
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self.generate_text(*args, **kwargs))

    ChatOpenAI.agenerate_text = _agenerate_text  # type: ignore

# Also add the synchronous generate_text method if missing
if not hasattr(ChatOpenAI, "generate_text"):

    def _generate_text(self, prompt, n: int = 1, temperature: float | None = None, stop=None, callbacks=None):
        """RAGAS helper – just delegate to the native `generate` which returns LLMResult."""
        return self.generate(prompt, n=n, temperature=temperature, stop=stop, callbacks=callbacks)

    ChatOpenAI.generate_text = _generate_text  # type: ignore

# Now add the async version that calls the native agenerate
if not hasattr(ChatOpenAI, "agenerate_text"):

    async def _agenerate_text(self,
                              prompt,
                              n: int = 1,
                              temperature: float | None = None,
                              stop=None,
                              callbacks=None):  # type: ignore
        return await self.agenerate(prompt, n=n, temperature=temperature, stop=stop, callbacks=callbacks)

    ChatOpenAI.agenerate_text = _agenerate_text  # type: ignore

# ------------------------------------------------------------------


def create_nvidia_llm(model: str, api_key: str, temperature: float = 0.0) -> BaseLanguageModel:
    """
    Create a properly configured NVIDIA LLM for RAGAS.
    This uses ChatNVIDIA which is the proper LangChain integration for NVIDIA's API.
    """
    try:
        from langchain_nvidia_ai_endpoints import ChatNVIDIA

        return ChatNVIDIA(
            model=model,
            api_key=api_key,
            temperature=temperature,
        )
    except ImportError:
        logger.warning("langchain_nvidia_ai_endpoints not available, falling back to ChatOpenAI")

        # Fallback to ChatOpenAI with NVIDIA endpoint
        return ChatOpenAI(
            model_name=model,
            temperature=temperature,
            openai_api_key=api_key,
            openai_api_base="https://integrate.api.nvidia.com/v1",
        )


class CitationQualityEvaluatorConfig(EvaluatorBaseConfig, name="citation_quality"):
    """Configuration for the citation quality evaluator."""
    llm: LLMRef = Field(description="The LLM to use for evaluation.")


class CitationPrecisionEvaluatorConfig(EvaluatorBaseConfig, name="citation_precision"):
    """Configuration for the citation precision evaluator."""
    llm: LLMRef = Field(description="The LLM to use for evaluation.")


class CitationRecallEvaluatorConfig(EvaluatorBaseConfig, name="citation_recall"):
    """Configuration for the citation recall evaluator."""
    llm: LLMRef = Field(description="The LLM to use for evaluation.")


class CitationF1EvaluatorConfig(EvaluatorBaseConfig, name="citation_f1"):
    """Configuration for the citation f1 evaluator."""
    llm: LLMRef = Field(description="The LLM to use for evaluation.")


def parse_sources(citation_section: str) -> Dict[int, str]:
    """
    Parse the citation section to get the source number and content mapping.
    Adapted from the notebook implementation with improved error handling.
    """
    if not isinstance(citation_section, str):
        logger.warning(f"citation_section is not a string, but {type(citation_section)}. Returning empty dict.")
        return {}

    if not citation_section.strip():
        logger.warning("citation_section is empty. Returning empty dict.")
        return {}

    # Updated pattern to handle the actual format with both Query and Answer sections
    pattern = re.compile(
        r"\*\*Source\*\*\s*(\d+)\s*\n\n"  # Match **Source** N
        r"\*\*Query:\*\*.*?\n\n"  # Skip the Query section
        r"\*\*Answer:\*\*\s*\n"  # Match **Answer:**
        r"(.*?)"  # Capture the answer content
        r"(?=\n\n---|\nCITATION:|\*\*Source\*\*|\Z)",  # Stop at next source delimiter, citation, or end
        flags=re.S,
    )

    sources = {}
    matches = list(pattern.finditer(citation_section))

    logger.debug(f"Found {len(matches)} source matches in citation section")

    for match in matches:
        try:
            num = int(match.group(1))
            answer = match.group(2).strip()

            # Clean up the answer content by removing CITATION: section
            if "CITATION:" in answer:
                answer = answer.split("CITATION:")[0].strip()

            sources[num] = answer
        except (ValueError, IndexError) as e:
            logger.warning(f"Failed to parse source from match: {e}")
            continue

    logger.info(f"Successfully parsed {len(sources)} sources from citation section")
    return sources


async def verify_citations(fact_citation_pairs: List[Tuple[str, List[int]]],
                           citation_sources: Dict[int, str],
                           evaluator_llm: BaseLanguageModel,
                           max_concurrency: int = 4) -> Tuple[float, float, float]:
    """
    Verify citation quality and return precision, recall, F1.
    """
    tp = fp = fn = 0
    eps = 1e-8

    logger.debug(f"Verifying citations for {len(fact_citation_pairs)} fact-citation pairs")
    logger.debug(f"Available citation sources: {list(citation_sources.keys())}")

    ragas_llm = LangchainLLMWrapper(evaluator_llm)
    scorer = ResponseGroundedness(llm=ragas_llm)
    semaphore = asyncio.Semaphore(max_concurrency)

    async def score_with_retry(sample: SingleTurnSample) -> float:
        async with semaphore:
            for attempt in range(3):
                try:
                    return await scorer.single_turn_ascore(sample)
                except Exception as e:
                    logger.warning(f"Citation check failed on attempt {attempt + 1}/3: {str(e)}")
                    if attempt < 2:
                        sleep_time = 2**attempt
                        logger.info(f"Retrying in {sleep_time} seconds...")
                        await asyncio.sleep(sleep_time)
            logger.error("Citation check failed after multiple retries.")
            return 0.0

    tasks = []
    for i, (fact, citations) in enumerate(fact_citation_pairs):
        if not citations:
            fn += 1
            logger.debug(f"Fact {i+1}: No citations -> fn (fn={fn})")
            continue

        try:
            contexts = [citation_sources[c] for c in citations]
            sample = SingleTurnSample(response=fact, retrieved_contexts=contexts)
            tasks.append(score_with_retry(sample))
            logger.debug(f"Fact {i+1}: Created task for citations {citations}")
        except KeyError as e:
            logger.warning(f"Citation index not found in sources: {e}. Treating as false positive.")
            fp += 1
            continue

    logger.info(f"Created {len(tasks)} LLM evaluation tasks")

    if tasks:
        scores = await asyncio.gather(*tasks)
        for i, score in enumerate(scores):
            if score > 0.5:
                tp += 1
                logger.debug(f"Task {i+1}: Score {score:.3f} -> tp (tp={tp})")
            else:
                fp += 1
                logger.debug(f"Task {i+1}: Score {score:.3f} -> fp (fp={fp})")

    precision = tp / (tp + fp + eps)
    recall = tp / (tp + fn + eps)
    f1 = 2 * precision * recall / (precision + recall + eps)

    if tp + fp + fn == 0:
        precision = recall = f1 = 0.0

    logger.info(f"Citation verification results: tp={tp}, fp={fp}, fn={fn}")
    logger.info(f"Precision: {precision:.3f}, Recall: {recall:.3f}, F1: {f1:.3f}")

    return precision, recall, f1


class CitationQualityEvaluator:

    def __init__(self, llm: BaseLanguageModel, max_concurrency: int = 4, output_dir: str = None):
        self.llm = llm
        self.max_concurrency = max_concurrency
        self.output_dir = output_dir or ".tmp/aiq/aira_evaluator"

    async def evaluate_item(self, item: EvalInputItem) -> EvalOutputItem:
        """
        Evaluate citation quality for a single item with improved debugging.
        """
        if item.output_obj == "":
            # incase workflow is skipped (using --skip_workflow), input_obj contains the data source, as it contains the ground truth
            item.output_obj = item.input_obj

        try:
            data_source = AIResearcherEvalOutput.model_validate_json(item.output_obj)
        except Exception as e:
            logger.error(f"Failed to parse data source for item {item.id}: {str(e)}")
            return EvalOutputItem(
                id=item.id,
                score=0.0,
                reasoning={
                    "error": f"Failed to parse data source: {str(e)}",
                    "debug_info": {
                        "output_obj_type": type(item.output_obj).__name__,
                        "output_obj_length": len(item.output_obj) if isinstance(item.output_obj, str) else "N/A",
                    }
                })

        logger.info(f"Processing item {data_source.id}")

        fact_citation_pairs = data_source.fact_citation_pairs
        citation_section = data_source.citation_section

        # Enhanced validation with better error messages
        if not fact_citation_pairs or not isinstance(fact_citation_pairs, list) or not fact_citation_pairs:
            error_msg = "No fact_citation_pairs found in the input."
            if fact_citation_pairs is None:
                error_msg += " fact_citation_pairs is None."
            elif not isinstance(fact_citation_pairs, list):
                error_msg += f" fact_citation_pairs is {type(fact_citation_pairs)}, expected list."
            elif len(fact_citation_pairs) == 0:
                error_msg += " fact_citation_pairs is empty list."

            logger.warning(error_msg)
            return EvalOutputItem(
                id=item.id,
                score=0.0,
                reasoning={
                    "error": error_msg,
                    "debug_info": {
                        "has_fact_citation_pairs":
                            data_source.fact_citation_pairs is not None,
                        "fact_citation_pairs_type":
                            type(data_source.fact_citation_pairs).__name__,
                        "fact_citation_pairs_length":
                            len(data_source.fact_citation_pairs) if data_source.fact_citation_pairs else 0,
                        "has_citation_section":
                            data_source.citation_section is not None,
                        "keys_in_item":
                            list(data_source.model_dump().keys()),
                    }
                })

        if not citation_section:
            logger.warning("No citation_section found in the input.")
            return EvalOutputItem(id=item.id,
                                  score=0.0,
                                  reasoning={
                                      "error": "No citation_section found in the input.",
                                      "debug_info": {
                                          "has_fact_citation_pairs": data_source.fact_citation_pairs is not None,
                                          "has_citation_section": data_source.citation_section is not None,
                                          "citation_section_type": type(data_source.citation_section).__name__,
                                          "keys_in_item": list(data_source.model_dump().keys()),
                                      }
                                  })

        logger.info(f"Citation quality evaluation for item {item.id}: fact_citation_pairs={len(fact_citation_pairs)}")

        # Debug the structure of fact_citation_pairs
        if fact_citation_pairs:
            sample_pair = fact_citation_pairs[0]
            logger.debug(f"Sample fact_citation_pair structure: {type(sample_pair)}")
            if isinstance(sample_pair, (list, tuple)) and len(sample_pair) >= 2:
                logger.debug(f"Sample fact type: {type(sample_pair[0])}")
                logger.debug(f"Sample citations type: {type(sample_pair[1])}")
                logger.debug(f"Sample citations value: {sample_pair[1]}")

        # Parse citation sources from the citation section
        parsed_sources = parse_sources(citation_section)

        if not parsed_sources:
            logger.warning(f"No sources could be parsed from citation section for item {item.id}")
            return EvalOutputItem(id=item.id,
                                  score=0.0,
                                  reasoning={
                                      "error": "No sources could be parsed from citation section.",
                                      "debug_info": {
                                          "citation_section_length":
                                              len(citation_section),
                                          "citation_section_preview":
                                              citation_section[:200] +
                                              "..." if len(citation_section) > 200 else citation_section,
                                          "total_facts":
                                              len(fact_citation_pairs),
                                      }
                                  })

        # Use the proper notebook implementation to verify citations
        try:
            precision, recall, f1_score = await verify_citations(
                fact_citation_pairs,
                parsed_sources,
                self.llm,
                self.max_concurrency
            )
        except Exception as e:
            logger.error(f"Citation verification failed for item {item.id}: {str(e)}")
            return EvalOutputItem(id=item.id,
                                  score=0.0,
                                  reasoning={
                                      "error": f"Citation verification failed: {str(e)}",
                                      "debug_info": {
                                          "has_fact_citation_pairs": data_source.fact_citation_pairs is not None,
                                          "has_citation_section": data_source.citation_section is not None,
                                          "parsed_sources_count": len(parsed_sources),
                                          "keys_in_item": list(data_source.model_dump().keys()),
                                      }
                                  })

        # Calculate additional metrics for debugging
        total_facts = len(fact_citation_pairs)
        facts_with_citations = sum(1 for fact, citations in fact_citation_pairs if citations and len(citations) > 0)
        parsed_sources_count = len(parsed_sources)

        logger.info(
            f"Item {item.id} results: total_facts={total_facts}, facts_with_citations={facts_with_citations}, parsed_sources={parsed_sources_count}"
        )

        reasoning = {
            "precision": precision,
            "recall": recall,
            "f1_score": f1_score,
            "total_facts": total_facts,
            "facts_with_citations": facts_with_citations,
            "parsed_sources_count": parsed_sources_count,
        }

        # Return the f1_score as the main score (for backwards compatibility)
        return EvalOutputItem(id=item.id, score=f1_score, reasoning=reasoning)

    async def evaluate_item_all_metrics(self, item: EvalInputItem) -> List[EvalOutputItem]:
        """Evaluate all three citation quality metrics (precision, recall, f1) for separate tracking."""
        # Get the base evaluation with all metrics calculated
        base_result = await self.evaluate_item(item)

        precision = base_result.reasoning.get("precision", 0.0)
        recall = base_result.reasoning.get("recall", 0.0)
        f1_score = base_result.reasoning.get("f1_score", 0.0)

        base_reasoning = {
            "total_facts": base_result.reasoning.get("total_facts", 0),
            "facts_with_citations": base_result.reasoning.get("facts_with_citations", 0),
            "parsed_sources_count": base_result.reasoning.get("parsed_sources_count", 0),
        }

        # Log individual metrics
        logger.info(f"Item {item.id} Citation Quality Metrics:")
        logger.info(f"  - Precision: {precision:.3f}")
        logger.info(f"  - Recall: {recall:.3f}")
        logger.info(f"  - F1 Score: {f1_score:.3f}")

        # Create separate evaluation items for each metric
        results = []

        # Precision
        results.append(
            EvalOutputItem(id=f"{item.id}_precision",
                           score=precision,
                           reasoning={
                               **base_reasoning, "metric_type": "precision", "precision": precision
                           }))

        # Recall
        results.append(
            EvalOutputItem(id=f"{item.id}_recall",
                           score=recall,
                           reasoning={
                               **base_reasoning, "metric_type": "recall", "recall": recall
                           }))

        # F1 Score
        results.append(
            EvalOutputItem(id=f"{item.id}_f1",
                           score=f1_score,
                           reasoning={
                               **base_reasoning, "metric_type": "f1_score", "f1_score": f1_score
                           }))

        return results

    async def evaluate(self, eval_input: EvalInput) -> EvalOutput:
        semaphore = asyncio.Semaphore(self.max_concurrency)

        async def wrapped_evaluate_item(item: EvalInputItem) -> List[EvalOutputItem]:
            async with semaphore:
                return await self.evaluate_item_all_metrics(item)

        # Get results for all items (each item returns multiple metrics)
        all_results = await asyncio.gather(*[wrapped_evaluate_item(item) for item in eval_input.eval_input_items])

        # Flatten the results (each item returned a list of metric results)
        eval_output_items = []
        for item_results in all_results:
            eval_output_items.extend(item_results)

        # Calculate average scores for each metric type
        precision_scores = [
            item.score for item in eval_output_items if item.reasoning.get("metric_type") == "precision"
        ]
        recall_scores = [item.score for item in eval_output_items if item.reasoning.get("metric_type") == "recall"]
        f1_scores = [item.score for item in eval_output_items if item.reasoning.get("metric_type") == "f1_score"]

        # Use F1 as the overall average score (for backwards compatibility)
        avg_score = sum(f1_scores) / len(f1_scores) if f1_scores else 0.0

        logger.info(f"Citation Quality Evaluation Complete:")
        logger.info(
            f"  - Precision Average: {sum(precision_scores) / len(precision_scores) if precision_scores else 0.0:.3f}")
        logger.info(f"  - Recall Average: {sum(recall_scores) / len(recall_scores) if recall_scores else 0.0:.3f}")
        logger.info(f"  - F1 Average: {avg_score:.3f}")

        return EvalOutput(average_score=avg_score, eval_output_items=eval_output_items)


class CitationPrecisionEvaluator:
    """Evaluator that focuses only on citation precision metric."""

    def __init__(self, llm: BaseLanguageModel, max_concurrency: int = 4, output_dir: str = None):
        self.base_evaluator = CitationQualityEvaluator(llm, max_concurrency, output_dir)

    async def evaluate(self, eval_input: EvalInput) -> EvalOutput:
        """Evaluate citation precision only."""
        # Get base results
        base_result = await self.base_evaluator.evaluate(eval_input)

        # Filter to only precision items
        precision_items = [
            item for item in base_result.eval_output_items if item.reasoning.get("metric_type") == "precision"
        ]

        # Calculate precision average
        precision_scores = [item.score for item in precision_items]
        avg_precision = sum(precision_scores) / len(precision_scores) if precision_scores else 0.0

        logger.info(f"Citation Precision Evaluation Complete: Average = {avg_precision:.3f}")

        return EvalOutput(average_score=avg_precision, eval_output_items=precision_items)


class CitationRecallEvaluator:
    """Evaluator that focuses only on citation recall metric."""

    def __init__(self, llm: BaseLanguageModel, max_concurrency: int = 4, output_dir: str = None):
        self.base_evaluator = CitationQualityEvaluator(llm, max_concurrency, output_dir)

    async def evaluate(self, eval_input: EvalInput) -> EvalOutput:
        """Evaluate citation recall only."""
        # Get base results
        base_result = await self.base_evaluator.evaluate(eval_input)

        # Filter to only recall items
        recall_items = [item for item in base_result.eval_output_items if item.reasoning.get("metric_type") == "recall"]

        # Calculate recall average
        recall_scores = [item.score for item in recall_items]
        avg_recall = sum(recall_scores) / len(recall_scores) if recall_scores else 0.0

        logger.info(f"Citation Recall Evaluation Complete: Average = {avg_recall:.3f}")

        return EvalOutput(average_score=avg_recall, eval_output_items=recall_items)


class CitationF1Evaluator:
    """Evaluator that focuses only on citation f1 metric."""

    def __init__(self, llm: BaseLanguageModel, max_concurrency: int = 4, output_dir: str = None):
        self.base_evaluator = CitationQualityEvaluator(llm, max_concurrency, output_dir)

    async def evaluate(self, eval_input: EvalInput) -> EvalOutput:
        """Evaluate citation f1 only."""
        # Get base results
        base_result = await self.base_evaluator.evaluate(eval_input)

        # Filter to only f1 items
        f1_items = [item for item in base_result.eval_output_items if item.reasoning.get("metric_type") == "f1_score"]

        # Calculate f1 average
        f1_scores = [item.score for item in f1_items]
        avg_f1 = sum(f1_scores) / len(f1_scores) if f1_scores else 0.0

        logger.info(f"Citation F1 Evaluation Complete: Average = {avg_f1:.3f}")

        return EvalOutput(average_score=avg_f1, eval_output_items=f1_items)
