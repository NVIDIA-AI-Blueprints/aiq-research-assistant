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
import math
from dataclasses import dataclass
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from nat.data_models.component_ref import LLMRef
from nat.data_models.evaluator import EvaluatorBaseConfig
from nat.eval.evaluator.evaluator_model import EvalInput
from nat.eval.evaluator.evaluator_model import EvalInputItem
from nat.eval.evaluator.evaluator_model import EvalOutput
from nat.eval.evaluator.evaluator_model import EvalOutputItem
from langchain_core.language_models import BaseLanguageModel
from pydantic import Field
from ragas import SingleTurnSample
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import AnswerAccuracy
from ragas.metrics import ContextRelevance
from ragas.metrics import MetricWithLLM
from ragas.metrics import ResponseGroundedness

from aiq_aira.eval.schema import AIResearcherEvalOutput

logger = logging.getLogger(__name__)

METRIC_MAP = {
    "AnswerAccuracy": AnswerAccuracy,
    "ContextRelevance": ContextRelevance,
    "ResponseGroundedness": ResponseGroundedness,
}


class RagasWrapperEvaluatorConfig(EvaluatorBaseConfig, name="ragas_wrapper"):
    metric: str = Field(description="The RAGAs metric to use (e.g., AnswerAccuracy).")
    llm: LLMRef = Field(description="The LLM to use for evaluation.")


class RagasWrapperEvaluator:
    """
    A wrapper evaluator that uses built-in RAGAs metrics but prepares
    the data accordingly. This allows it to correctly parse the 
    workflow output that we use for evaluation.
    """

    def __init__(self, llm: BaseLanguageModel, metric: str, max_concurrency: int = 4):
        if metric not in METRIC_MAP:
            raise ValueError(f"Unsupported metric: {metric}. Supported metrics are: {list(METRIC_MAP.keys())}")

        self.llm = llm
        self.ragas_llm = LangchainLLMWrapper(langchain_llm=llm)
        self.metric_name = metric
        self.metric_class = METRIC_MAP[metric]

        # Initialize the metric with the LLM
        logger.info(f"Initializing {metric} metric with LLM")
        logger.info(f"LLM type: {type(llm)}, LLM model: {getattr(llm, 'model_name', 'unknown')}")
        logger.info(f"LLM temperature: {getattr(llm, 'temperature', 'unknown')}")
        logger.info(f"LLM base_url: {getattr(llm, 'openai_api_base', getattr(llm, 'base_url', 'unknown'))}")

        # Check if API key is set
        api_key = getattr(llm, 'openai_api_key', getattr(llm, 'api_key', None))
        if api_key:
            logger.info(f"Openai key is set (length: {len(api_key)})")
        else:
            logger.warning("Openai key is not set, just a warning, if you're using NVIDIA API key please ignore this")

        self.scorer: MetricWithLLM = self.metric_class(llm=self.ragas_llm)
        logger.info(f"Successfully initialized {metric} metric")
        logger.info(f"Scorer LLM: {type(self.scorer.llm) if hasattr(self.scorer, 'llm') else 'No LLM attribute'}")

        self.max_concurrency = max_concurrency

    async def evaluate_item(self, item: EvalInputItem) -> EvalOutputItem:
        """
        Evaluates a single item using the specified RAGAs metric.
        """
        try:
            if item.output_obj == "":
                # incase workflow is skipped (using --skip_workflow), input_obj contains the data source, as it contains the ground truth
                item.output_obj = item.input_obj

            # Add detailed logging for debugging schema issues
            logger.info(f"=== EVALUATOR VALIDATION LOGGING ===")
            logger.info(f"Item ID: {item.id}")
            logger.info(f"Item output_obj type: {type(item.output_obj)}")
            logger.info(
                f"Item output_obj length: {len(item.output_obj) if isinstance(item.output_obj, str) else 'N/A'}")

            # Log the first 500 characters of the output_obj to see what we're trying to parse
            if isinstance(item.output_obj, str):
                logger.info(f"Item output_obj preview: {item.output_obj[:500]}...")

            data_source = AIResearcherEvalOutput.model_validate_json(item.output_obj)
            logger.info(f"Successfully parsed data_source for item {data_source.id}")
            logger.info(f"=== END EVALUATOR VALIDATION ===")

            logger.info(f"Starting evaluation for item {data_source.id} with metric {self.metric_name}")
            logger.info(f"Item {data_source.id}: Loaded example with keys: {list(data_source.model_dump().keys())}")

            # Prepare contexts - exactly like the notebook
            rag_contexts = data_source.rag_contexts
            web_answers = data_source.web_answers
            logger.info(
                f"Item {data_source.id}: Found {len(rag_contexts)} RAG contexts and {len(web_answers)} web answers")

            contexts = [c.get("context", "") for c in rag_contexts if c.get("context")]
            contexts += [str(c).split("ANSWER:")[-1].strip() for c in web_answers]
            logger.info(f"Item {data_source.id}: Extracted {len(contexts)} total contexts")

            response = data_source.finalized_summary
            ground_truth = data_source.ground_truth
            logger.info(
                f"Item {data_source.id}: Response length: {len(response)}, Ground truth length: {len(ground_truth)}")

            # Handle different metrics with EXACT notebook implementation
            if self.metric_name == "ContextRelevance":
                # EXACT notebook implementation: Use multiple questions and average scores
                questions = [q["question"] for q in data_source.context_relevance_questions]
                logger.info(f"Item {data_source.id}: Evaluating context relevance with {len(questions)} questions")

                scores = []
                for q in questions:
                    sample = SingleTurnSample(user_input=q, retrieved_contexts=contexts)
                    score = await self.scorer.single_turn_ascore(sample)
                    scores.append(score)
                    logger.debug(f"Item {data_source.id}: Question '{q[:50]}...' scored {score}")

                final_score = sum(scores) / len(scores) if scores else 0.0
                logger.info(f"Item {data_source.id}: Context relevance average score: {final_score}")

                return EvalOutputItem(
                    id=data_source.id,
                    score=final_score,
                    reasoning={
                        "metric": self.metric_name,
                        "individual_scores": scores,
                        "questions_evaluated": len(questions),
                        "num_contexts": len(contexts),
                        "score_details": f"Average of {len(scores)} question evaluations: {final_score}",
                        "has_contexts": bool(contexts),
                    })

            elif self.metric_name == "ResponseGroundedness":
                # EXACT notebook implementation: Use individual extracted statements
                statements = data_source.groundness_facts_claims
                logger.info(f"Item {data_source.id}: Evaluating groundedness with {len(statements)} statements")

                scores = []
                for statement in statements:
                    sample = SingleTurnSample(response=statement, retrieved_contexts=contexts)
                    score = await self.scorer.single_turn_ascore(sample)
                    scores.append(score)
                    logger.debug(f"Item {data_source.id}: Statement '{statement[:50]}...' scored {score}")

                final_score = sum(scores) / len(scores) if scores else 0.0
                logger.info(f"Item {data_source.id}: Groundedness average score: {final_score}")

                return EvalOutputItem(
                    id=data_source.id,
                    score=final_score,
                    reasoning={
                        "metric": self.metric_name,
                        "individual_scores": scores,
                        "statements_evaluated": len(statements),
                        "num_contexts": len(contexts),
                        "score_details": f"Average of {len(scores)} statement evaluations: {final_score}",
                        "has_contexts": bool(contexts),
                    })

            elif self.metric_name == "AnswerAccuracy":
                # EXACT notebook implementation: Use combined question format
                question = f"{data_source.topic}, {data_source.report_organization}."
                logger.info(f"Item {data_source.id}: Evaluating answer accuracy")
                logger.info(f"Item {data_source.id}: Question: {question[:100]}...")

                sample = SingleTurnSample(user_input=question,
                                          retrieved_contexts=contexts,
                                          reference=ground_truth,
                                          response=response)

                score = await self.scorer.single_turn_ascore(sample)
                logger.info(f"Item {data_source.id}: Answer accuracy score: {score}")

                return EvalOutputItem(
                    id=data_source.id,
                    score=score,
                    reasoning={
                        "metric": self.metric_name,
                        "user_input": question[:200] + "..." if len(question) > 200 else question,
                        "response_snippet": response[:200] + "..." if len(response) > 200 else response,
                        "num_contexts": len(contexts),
                        "score_details": f"{self.metric_name} score: {score}",
                        "has_ground_truth": bool(ground_truth),
                        "has_response": bool(response),
                        "has_contexts": bool(contexts),
                    })

            else:
                # Fallback for other metrics - use original implementation
                question = f"{data_source.topic}, {data_source.report_organization}."

                # Create SingleTurnSample with the fields required by the specific metric
                sample_kwargs = {}
                # Get required fields from the metric
                if hasattr(self.scorer, '_required_columns'):
                    from ragas.metrics.base import MetricType
                    required_fields = self.scorer._required_columns.get(MetricType.SINGLE_TURN, set())
                else:
                    required_fields = {'user_input', 'retrieved_contexts', 'response', 'reference'}

                logger.info(f"Item {data_source.id}: Required fields for {self.metric_name}: {required_fields}")

                if "user_input" in required_fields:
                    sample_kwargs["user_input"] = question
                if "retrieved_contexts" in required_fields:
                    sample_kwargs["retrieved_contexts"] = contexts
                if "response" in required_fields:
                    sample_kwargs["response"] = response
                if "reference" in required_fields:
                    sample_kwargs["reference"] = ground_truth

                logger.info(f"Item {data_source.id}: Created sample with fields: {list(sample_kwargs.keys())}")
                sample = SingleTurnSample(**sample_kwargs)

                logger.info(f"Item {data_source.id}: Calling RAGAs {self.metric_name} scorer...")
                try:
                    score = await self.scorer.single_turn_ascore(sample)
                    logger.info(f"Item {data_source.id}: RAGAs {self.metric_name} returned score: {score}")
                except Exception as e:
                    logger.error(f"Item {data_source.id}: Error calling RAGAs {self.metric_name}: {str(e)}",
                                 exc_info=True)
                    score = float('nan')

                # Handle NaN scores
                if math.isnan(score):
                    logger.warning(
                        f"Item {data_source.id}: RAGAs {self.metric_name} returned NaN score, setting to 0.0")
                    score = 0.0

                return EvalOutputItem(
                    id=data_source.id,
                    score=score,
                    reasoning={
                        "metric": self.metric_name,
                        "user_input": question[:200] + "..." if len(question) > 200 else question,
                        "response_snippet": response[:200] + "..." if len(response) > 200 else response,
                        "num_contexts": len(contexts),
                        "score_details": f"{self.metric_name} score: {score}",
                        "has_ground_truth": bool(ground_truth),
                        "has_response": bool(response),
                        "has_contexts": bool(contexts),
                    })

        except Exception as e:
            logger.exception(f"Error evaluating item {data_source.id} with RAGAs metric {self.metric_name}")
            return EvalOutputItem(id=data_source.id,
                                  score=0.0,
                                  reasoning={
                                      "error": str(e),
                                      "metric": self.metric_name,
                                  })

    async def evaluate(self, eval_input: EvalInput) -> EvalOutput:
        """
        Evaluates the entire batch of inputs.
        """
        logger.info(
            f"Starting batch evaluation with {len(eval_input.eval_input_items)} items using metric {self.metric_name}")

        semaphore = asyncio.Semaphore(self.max_concurrency)

        async def wrapped_evaluate_item(item: EvalInputItem) -> EvalOutputItem:
            async with semaphore:
                return await self.evaluate_item(item)

        eval_output_items = await asyncio.gather(*[wrapped_evaluate_item(item) for item in eval_input.eval_input_items])

        # Filter out None and NaN scores for average calculation
        valid_scores = []
        for item in eval_output_items:
            if item.score is not None and not math.isnan(item.score):
                valid_scores.append(item.score)
        
        avg_score = sum(valid_scores) / len(valid_scores) if valid_scores else 0.0

        logger.info(f"Completed batch evaluation for {self.metric_name}:")
        logger.info(f"  - Total items: {len(eval_output_items)}")
        logger.info(f"  - Valid scores: {len(valid_scores)}")
        logger.info(f"  - Average score: {avg_score:.4f}")
        logger.info(
            f"  - Score distribution: min={min(valid_scores) if valid_scores else 'N/A'}, max={max(valid_scores) if valid_scores else 'N/A'}")

        return EvalOutput(average_score=avg_score, eval_output_items=eval_output_items)
