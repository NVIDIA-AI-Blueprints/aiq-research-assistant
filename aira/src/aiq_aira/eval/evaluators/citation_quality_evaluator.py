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

from aiq.data_models.component_ref import LLMRef
from aiq.data_models.evaluator import EvaluatorBaseConfig
from aiq.eval.evaluator.evaluator_model import EvalInput
from aiq.eval.evaluator.evaluator_model import EvalInputItem
from aiq.eval.evaluator.evaluator_model import EvalOutput
from aiq.eval.evaluator.evaluator_model import EvalOutputItem
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


def parse_sources(citation_section: str) -> Dict[int, str]:
    """
    Parse the citation section to get the source number and content mapping.
    Adapted from the notebook implementation.
    """
    if not isinstance(citation_section, str):
        logger.warning(f"citation_section is not a string, but {type(citation_section)}. Returning empty dict.")
        return {}

    # Updated pattern to handle the actual format with both Query and Answer sections
    pattern = re.compile(
        r"\*\*Source\*\*\s*(\d+)\s*\n\n"  # Match **Source** N
        r"\*\*Query:\*\*.*?\n\n"  # Skip the Query section
        r"\*\*Answer:\*\*\s*\n"  # Match **Answer:**
        r"(.*?)"  # Capture the answer content
        r"(?=\n\n---|\nCITATION:|\Z)",  # Stop at next source delimiter, citation, or end
        flags=re.S,
    )

    sources = {}
    for num, answer in pattern.findall(citation_section):
        sources[int(num)] = answer.strip()
    return sources


async def verify_citations(fact_citation_pairs: List[Tuple[str, List[int]]],
                           citation_sources: Dict[int, str],
                           evaluator_llm: BaseLanguageModel,
                           max_concurrency: int = 4) -> Tuple[float, float, float]:
    """
    Verify citation quality and return precision, recall, F1.
    This matches the notebook's verify_citations function.
    """
    tp = fp = fn = 0
    eps = 1e-8

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
    for fact, citations in fact_citation_pairs:
        if not citations:
            fn += 1
            continue

        try:
            contexts = [citation_sources[c] for c in citations]
            sample = SingleTurnSample(response=fact, retrieved_contexts=contexts)
            tasks.append(score_with_retry(sample))
        except KeyError as e:
            logger.warning(f"Citation index not found in sources: {e}. Treating as false positive.")
            fp += 1
            continue

    if tasks:
        scores = await asyncio.gather(*tasks)
        for score in scores:
            if score > 0.5:
                tp += 1
            else:
                fp += 1

    precision = tp / (tp + fp + eps)
    recall = tp / (tp + fn + eps)
    f1 = 2 * precision * recall / (precision + recall + eps)

    if tp + fp + fn == 0:
        precision = recall = f1 = 0.0

    return precision, recall, f1


class CitationQualityEvaluator:

    def __init__(self, llm: BaseLanguageModel, max_concurrency: int = 4, output_dir: str = None):
        self.llm = llm
        self.max_concurrency = max_concurrency
        self.output_dir = output_dir or ".tmp/aiq/aira_evaluator"

    async def evaluate_item(self, item: EvalInputItem) -> EvalOutputItem:
        """
        Evaluate citation quality for a single item.
        """
        if item.output_obj == "":
            # incase workflow is skipped (using --skip_workflow), input_obj contains the data source, as it contains the ground truth
            item.output_obj = item.input_obj
        data_source = AIResearcherEvalOutput.model_validate_json(item.output_obj)
        logger.info(f"=== Processing item {data_source.id} ===")
        logger.info(f"Parsed data keys: {list(data_source.model_dump().keys())}")
        logger.info(f"Has fact_citation_pairs: {'fact_citation_pairs' in data_source.fact_citation_pairs}")
        logger.info(f"Has citation_section: {'citation_section' in data_source.citation_section}")

        fact_citation_pairs = data_source.fact_citation_pairs
        citation_section = data_source.citation_section

        if not fact_citation_pairs or not isinstance(fact_citation_pairs, list) or not fact_citation_pairs:
            return EvalOutputItem(id=item.id,
                                  score=0.0,
                                  reasoning={
                                      "error": "No fact_citation_pairs found in the input.",
                                      "debug_info": {
                                          "has_fact_citation_pairs": data_source.fact_citation_pairs is not None,
                                          "has_citation_section": data_source.citation_section is not None,
                                          "keys_in_item": list(data_source.model_dump().keys()),
                                      }
                                  })

        if not citation_section:
            return EvalOutputItem(id=item.id,
                                  score=0.0,
                                  reasoning={
                                      "error": "No citation_section found in the input.",
                                      "debug_info": {
                                          "has_fact_citation_pairs": data_source.fact_citation_pairs is not None,
                                          "has_citation_section": data_source.citation_section is not None,
                                          "keys_in_item": list(data_source.model_dump().keys()),
                                      }
                                  })

        logger.info(f"Citation quality evaluation for item {item.id}: fact_citation_pairs={len(fact_citation_pairs)}")

        # Parse citation sources from the citation section
        parsed_sources = parse_sources(citation_section)

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
                                          "keys_in_item": list(data_source.model_dump().keys()),
                                      }
                                  })

        # Calculate additional metrics for debugging
        total_facts = len(fact_citation_pairs)
        facts_with_citations = sum(1 for fact, citations in fact_citation_pairs if citations and len(citations) > 0)
        parsed_sources_count = len(parsed_sources)

        reasoning = {
            "precision": precision,
            "recall": recall,
            "f1_score": f1_score,
            "total_facts": total_facts,
            "facts_with_citations": facts_with_citations,
            "parsed_sources_count": parsed_sources_count,
        }

        return EvalOutputItem(id=item.id, score=f1_score, reasoning=reasoning)

    async def evaluate(self, eval_input: EvalInput) -> EvalOutput:
        semaphore = asyncio.Semaphore(self.max_concurrency)

        async def wrapped_evaluate_item(item: EvalInputItem) -> EvalOutputItem:
            async with semaphore:
                return await self.evaluate_item(item)

        eval_output_items = await asyncio.gather(*[wrapped_evaluate_item(item) for item in eval_input.eval_input_items])

        scores = [item.score for item in eval_output_items if item.score is not None]
        avg_score = sum(scores) / len(scores) if scores else 0.0

        return EvalOutput(average_score=avg_score, eval_output_items=eval_output_items)
