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
import typing as t
from dataclasses import dataclass
from dataclasses import field

from nat.data_models.component_ref import LLMRef
from nat.data_models.evaluator import EvaluatorBaseConfig
from nat.eval.evaluator.evaluator_model import EvalInput
from nat.eval.evaluator.evaluator_model import EvalInputItem
from nat.eval.evaluator.evaluator_model import EvalOutput
from nat.eval.evaluator.evaluator_model import EvalOutputItem
from langchain_core.callbacks.base import Callbacks
from langchain_core.language_models.base import BaseLanguageModel
from langchain_core.prompt_values import StringPromptValue
from pydantic import BaseModel
from pydantic import Field
from ragas.dataset_schema import SingleTurnSample
from ragas.metrics.base import MetricType
from ragas.metrics.base import MetricWithLLM
from ragas.metrics.base import SingleTurnMetric

from aiq_aira.eval.schema import AIResearcherEvalOutput


class CoverageEvaluatorConfig(EvaluatorBaseConfig, name="coverage"):
    """Configuration for the coverage evaluator."""
    llm: LLMRef = Field(description="The LLM to use for evaluation.")
    max_concurrency: int = Field(4, description="Maximum number of concurrent evaluation tasks.")


logger = logging.getLogger(__name__)


class CoverageJudgment(BaseModel):
    """LLM Judgment of whether a key fact/claim is supported by a report"""
    fact_or_claim: str = Field(description="Fact/claim being verified")
    relevant_snippet: str = Field(description="1-2 sentences from the report most relevant to the fact/claim")
    judgment: str = Field(description="LLM judgment of whether the fact/claim is supported by the report")


@dataclass
class AIRACoverage(MetricWithLLM, SingleTurnMetric):
    """
    This is adapted from the user's `custom_metrics.py`.
    It calculates if a given fact/claim is covered by the report.
    """
    name: str = "coverage_score"
    _required_columns: t.Dict[MetricType, t.Set[str]] = field(default_factory=lambda: {
        MetricType.SINGLE_TURN: {
            "response",
            "reference", }, })
    template_coverage1 = """You are tasked with verifying whether the provided fact/claim can be inferred from a given report. This requires careful analysis and comparison between the report content and the fact/claim.

## The Report

First, carefully read the following report:

<report>
{report}
</report>

## Fact/Claim to Verify

Now, examine the following fact/claim that needs to be verified against the report:

<fact_or_claim>
{fact_or_claim}
</fact_or_claim>

## Your Task

For the fact/claim provided above, you need to:

1. **Extract relevant snippets** - Identify the most relevant 1-2 sentences from the report that relate to the fact/claim. If no relevant content exists, leave this empty.

2. **Compare the fact/claim with the report content** - Analyze whether the information in the fact/claim is directly stated or can be reasonably inferred from the report.

3. **Make a judgment** - Determine if the fact/claim is supported by the report:
    - Answer "Yes" if the key fact/claim can be directly inferred from the report
    - Answer "No" if the key fact/claim cannot be inferred from the report

## Output Format

Return your analysis as a JSON object with exactly these three keys:

{{
    "fact_or_claim": "〈repeat the fact/claim here〉",
    "relevant_snippet": "〈1-2 sentences from the report most relevant to the fact/claim (or empty)〉",
    "judgment": "Yes"  // or "No"
}}

Be thorough in your analysis and precise in your judgments. Ensure that your relevant snippets directly relate to the fact/claim being verified."""

    retry: int = 5

    async def _single_turn_ascore(self, sample: SingleTurnSample, callbacks: Callbacks) -> float:
        """
        Calculates the coverage score for a single row with simple exponential backoff.
        """
        assert self.llm is not None, "LLM is not set"
        assert sample.response is not None, "Report is not set"
        assert sample.reference is not None, "Fact/claim is not set"

        if sample.response.strip() == "":
            return 0.0  # If no report, consider no fact/claim covered
        if len(sample.reference.strip()) == 0:
            return 1.0  # If no fact/claim, consider all fact/claims covered

        fact_or_claim_data = sample.reference.strip()

        for retry_attempt in range(self.retry):
            try:
                formatted_prompt = StringPromptValue(
                    text=self.template_coverage1.format(report=sample.response, fact_or_claim=fact_or_claim_data))
                resp = await self.llm.ainvoke(formatted_prompt)

                # Extract the string content from the response
                response_content = resp.content

                # Clean the response content in case it's wrapped in markdown
                if "```json" in response_content:
                    response_content = response_content.split("```json")[1].split("```")[0]

                response_data = json.loads(response_content)
                judgment = response_data["judgment"]
                score = 1.0 if judgment == "Yes" else 0.0
                return score

            except Exception as e:
                logger.warning(f"Attempt {retry_attempt + 1} for CoverageMetric failed: {str(e)}")

                if retry_attempt < self.retry - 1:
                    # Simple exponential backoff: 2, 4, 8, 16 seconds
                    sleep_time = 2**(retry_attempt + 1)
                    logger.info(f"Retrying in {sleep_time} seconds...")
                    await asyncio.sleep(sleep_time)
                else:
                    logger.error(
                        f"Failed to get/parse LLM response for CoverageMetric after {self.retry} attempts: {str(e)}")
                    return 0.0
        return 0.0


class CoverageEvaluator:

    def __init__(self,
                 llm: BaseLanguageModel,
                 max_concurrency: int = 4,
                 output_dir: str = None,
                 extraction_model: str = None,
                 extraction_provider: str = None,
                 extraction_max_retries: int = None,
                 extraction_temperature: float = None,
                 extraction_max_tokens: int = None):
        self.max_concurrency = max_concurrency
        self.llm = llm
        self.output_dir = output_dir or ".tmp/aiq_aira"

    async def evaluate_item(self, item: EvalInputItem) -> EvalOutputItem:
        """
        Computes the coverage score for an individual item.
        Extracts coverage facts from ground truth using LLM calls, just like in the notebook.
        """
        if item.output_obj == "":
            # incase workflow is skipped (using --skip_workflow), input_obj contains the data source, as it contains the ground truth
            item.output_obj = item.input_obj
        data_source = AIResearcherEvalOutput.model_validate_json(item.output_obj)
        logger.info(f"=== Processing item {data_source.id} ===")

        logger.info(f"Parsed data keys: {list(data_source.model_dump().keys())}")
        logger.info(f"Has finalized_summary: {'finalized_summary' in data_source.finalized_summary}")
        logger.info(f"Has coverage_facts_claims: {'coverage_facts_claims' in data_source.coverage_facts_claims}")

        # Extract the report
        report = data_source.finalized_summary

        if not report or not report.strip():
            return EvalOutputItem(
                id=item.id,
                score=0.0,
                reasoning={
                    "error": "Generated report (finalized_summary) is empty.",
                    "debug_info": {
                        "has_finalized_summary":
                            data_source.finalized_summary is not None,
                        "keys_in_item":
                            list(data_source.model_dump().keys()) if isinstance(data_source, dict) else None,
                        "item_id":
                            item.id,
                    }
                })

        # Extract the ground truth
        ground_truth = data_source.ground_truth

        if not ground_truth or not ground_truth.strip():
            return EvalOutputItem(
                id=item.id,
                score=0.0,
                reasoning={
                    "error": "No ground truth data found.",
                    "debug_info": {
                        "has_ground_truth":
                            data_source.ground_truth is not None,
                        "keys_in_item":
                            list(data_source.model_dump().keys()) if isinstance(data_source, dict) else None,
                        "item_id":
                            item.id,
                    }
                })

        try:
            # Always use coverage_facts_claims for evaluation regardless of mode
            # This ensures consistent evaluation across both E2E and pre-generated modes
            facts_claims = data_source.coverage_facts_claims
            facts_source = "coverage_facts_claims"

            logger.info(f"Item {data_source.id}: Found {len(facts_claims)} facts from {facts_source}")
            if facts_claims and len(facts_claims) > 0:
                logger.debug(f"Item {data_source.id}: First claim: {facts_claims[0]}")
                logger.debug(f"Item {data_source.id}: Last claim: {facts_claims[-1]}")

            if not facts_claims:
                return EvalOutputItem(
                    id=data_source.id,
                    score=0,
                    reasoning={
                        "skipped": True,
                        "reason": f"No facts could be extracted from {facts_source}.",
                        "ground_truth_snippet": ground_truth[:200] + "..." if len(ground_truth) > 200 else ground_truth,
                        "facts_source": facts_source,
                    })

            logger.info(f"Extracted {len(facts_claims)} facts from {facts_source}")

            # --- Replicating the Notebook's Coverage Loop ---
            scorer = AIRACoverage(llm=self.llm)

            # Use semaphore to limit concurrent requests and avoid rate limits
            semaphore = asyncio.Semaphore(self.max_concurrency)

            async def evaluate_single_claim(claim):
                async with semaphore:
                    sample = SingleTurnSample(response=report,
                                              reference=str(claim),
                                              user_input="",
                                              retrieved_contexts=[])
                    return await scorer._single_turn_ascore(sample=sample, callbacks=None)

            # Evaluate all claims concurrently
            scores = await asyncio.gather(*[evaluate_single_claim(claim) for claim in facts_claims])

            # Calculate average score
            average_score = sum(scores) / len(scores) if scores else 0.0

            logger.info(f"Item {data_source.id}: Coverage evaluation completed")
            logger.info(f"Item {data_source.id}: Average coverage score: {average_score:.2f}")
            logger.info(f"Item {data_source.id}: Individual scores: {scores}")

            # Prepare reasoning
            reasoning = {
                "average_score": average_score,
                "individual_scores": scores,
                "num_claims": len(facts_claims),
                "facts_source": facts_source,
                "report_snippet": report[:200] + "..." if len(report) > 200 else report,
            }

            return EvalOutputItem(id=data_source.id, score=average_score, reasoning=reasoning)

        except Exception as e:
            logger.error(f"Coverage evaluation failed for item {data_source.id}: {str(e)}")
            return EvalOutputItem(id=data_source.id,
                                  score=0.0,
                                  reasoning={"error": f"Coverage evaluation failed: {str(e)}"})

    async def evaluate(self, eval_input: EvalInput) -> EvalOutput:
        """
        Evaluate function that processes all items in the evaluation input.
        """
        # Process items concurrently with a limit on concurrency
        semaphore = asyncio.Semaphore(self.max_concurrency)

        async def wrapped_evaluate_item(item: EvalInputItem) -> EvalOutputItem:
            """
            Process an item asynchronously with concurrency control.
            """
            async with semaphore:
                return await self.evaluate_item(item)

        # Process all items concurrently
        eval_output_items = await asyncio.gather(*[wrapped_evaluate_item(item) for item in eval_input.eval_input_items])

        # Calculate average score
        scores = [item.score for item in eval_output_items if item.score is not None]
        avg_score = sum(scores) / len(scores) if scores else 0.0

        return EvalOutput(average_score=avg_score, eval_output_items=eval_output_items)
