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

logger = logging.getLogger(__name__)


class HallucinationEvaluatorConfig(EvaluatorBaseConfig, name="hallucination"):
    """
    Configuration for the custom hallucination evaluator.
    This evaluator checks if a generated report contains any hallucinations.
    """
    llm: LLMRef = Field(description="The LLM to use for evaluation.")


class HallucinationJudgment(BaseModel):
    """LLM Judgment of whether a report contains hallucination or not"""
    rationale: str = Field(description="Brief explanation of your reasoning")
    score: int = Field(description="Score from 0 to 1")


@dataclass
class AIRAHallucination(MetricWithLLM, SingleTurnMetric):
    """
    This is adapted from the user's `custom_metrics.py`.
    It calculates if a given report contains hallucinations.
    """
    name: str = "hallucination_score"
    _required_columns: t.Dict[MetricType, t.Set[str]] = field(default_factory=lambda: {
        MetricType.SINGLE_TURN: {
            "response",
            "retrieved_contexts",
            "user_input", }, })
    rationale_a: str = ""
    rationale_b: str = ""

    template_hallucination_a = """# In this task, you will be presented with a query, a reference text and an answer.
# The answer is generated for the question based on the reference text.
# The response may contain false information.
# Your goal is to determine whether the answer text contains factual information and is not a hallucination.
# A 'hallucination' refers to an answer that is not based on the reference text or assumes information that is not available in the reference text.
# A 'hallucination' also refers to any fact in the answer that is not substantiated by the facts in the reference text.

[BEGIN DATA]
************
# [Query]: {question}
************
# [Reference text]: {passage}
************
# [Answer]: {answer}
************
[END DATA]

# Does the answer contain any hallucinations?
# Please read the question, reference text and answer carefully, then write a step-by-step EXPLANATION to determine whether a 'hallucination' is present.
# Avoid simply stating the correct answer at the outset.
# FINISH the last token of your answer with LABEL, which must be a SINGLE number: 1 or 0, and must NOT include any other text or characters such as ". 1 indicates hallucinations and 0 indicates no hallucinations (faithful to the reference text).
# If a 'hallucination' is detected, explain why in the EXPLANATION session.

## Your Response
Provide your evaluation in JSON format with two fields:
1. "rationale": A brief explanation (1-3 sentences) justifying your score
2. "score": An integer from 0 to 1

Your response should follow this format:
```json
{{
"rationale": "<brief explanation of your reasoning>",
"score": <integer 0-1>,
}}
```
"""

    template_hallucination_b = """# In this task, you will be presented with a query, a reference text and an answer.
# The answer is generated for the question based on the reference text.
# The response may contain false information.
# Your goal is to determine whether the answer text contains factual information and is not a hallucination.
# A 'hallucination' refers to an answer that is not based on the reference text or assumes information that is not available in the reference text.
# A 'hallucination' also refers to any fact in the answer that is not substantiated by the facts in the reference text.

[BEGIN DATA]
************
# [Query]: {question}
************
# [Answer]: {answer}
************
# [Reference text]: {passage}
************
[END DATA]

# Does the answer contain any hallucinations?
# Please read the question, reference text and answer carefully, then write a step-by-step EXPLANATION to determine whether a 'hallucination' is present.
# Avoid simply stating the correct answer at the outset.
# FINISH the last token of your answer with LABEL, which must be a SINGLE number: 1 or 0, and must NOT include any other text or characters such as ". 1 indicates hallucinations and 0 indicates no hallucinations (faithful to the reference text).
# If a 'hallucination' is detected, explain why in the EXPLANATION session.

## Your Response
Provide your evaluation in JSON format with two fields:
1. "rationale": A brief explanation (1-3 sentences) justifying your score
2. "score": An integer from 0 to 1

Your response should follow this format:
```json
{{
"rationale": "<brief explanation of your reasoning>",
"score": <integer 0-1>,
}}
```
"""
    retry: int = 5

    async def _single_turn_ascore(self, sample: SingleTurnSample, callbacks: Callbacks) -> float:
        """
        Calculates the hallucination score for a single row.
        """
        assert self.llm is not None, "LLM is not set"
        assert sample.response is not None, "Report is not set"
        assert sample.retrieved_contexts is not None, "retrieved_contexts are not set"
        assert sample.user_input is not None, "query are not set"

        if sample.user_input.strip() == "":
            return 0.0  # If no user_input, consider no hallucination
        if sample.response.strip() == "":
            return 0.0  # If no report, consider no hallucination
        if isinstance(sample.retrieved_contexts, list):
            sources = "\n".join(sample.retrieved_contexts)
        else:
            sources = sample.retrieved_contexts

        # Template A evaluation
        score_a = 0.0
        # Rationale stored in self.rationale_a
        for retry in range(self.retry):
            try:
                formatted_prompt = StringPromptValue(text=self.template_hallucination_a.format(
                    question=sample.user_input, answer=sample.response, passage=sources))

                try:
                    llm_with_so = self.llm.with_structured_output(HallucinationJudgment)
                    req_a = llm_with_so.ainvoke(formatted_prompt)
                    resp_a = await req_a
                    parsed = json.loads(resp_a.model_dump_json())
                except Exception as inner:
                    if "json_schema" not in str(inner):
                        raise
                    # Fallback to plain text generation for NVIDIA NIM
                    from langchain_core.messages import HumanMessage
                    raw = await self.llm.ainvoke([HumanMessage(content=formatted_prompt.text)])
                    raw_text = raw.content if hasattr(raw, 'content') else str(raw)

                    logger.info(f"Template A raw LLM response (attempt {retry + 1}):\n{raw_text}")

                    # Enhanced JSON extraction with multiple patterns
                    patterns = [
                        r'```json\s*(\{.*?\})\s*```',  # ```json {...} ```
                        r'```\s*(\{.*?\})\s*```',  # ``` {...} ```
                        r'(\{[^{}]*"rationale"[^{}]*"score"[^{}]*\})',  # Simple JSON with required fields
                        r'(\{.*?\})',  # Any JSON-like object
                    ]

                    parsed = None
                    for i, pattern in enumerate(patterns):
                        matches = re.findall(pattern, raw_text, re.DOTALL | re.IGNORECASE)
                        logger.info(f"Template A pattern {i+1} found {len(matches)} matches")
                        for match in matches:
                            try:
                                if isinstance(match, tuple):
                                    match = match[0] if match else ""
                                logger.info(f"Template A trying to parse match: {match}")

                                # Clean up the JSON string - remove trailing commas and fix formatting
                                cleaned_match = match.strip()
                                # Remove trailing comma before closing brace
                                cleaned_match = re.sub(r',(\s*})', r'\1', cleaned_match)

                                parsed = json.loads(cleaned_match)
                                if "score" in parsed:  # Verify it has the required field
                                    logger.info(f"Template A successfully parsed: {parsed}")
                                    break
                            except json.JSONDecodeError as jde:
                                logger.info(f"Template A JSON decode failed for: {match}, error: {jde}")
                                continue
                        if parsed:
                            break

                    # If regex patterns fail, try to extract JSON more aggressively
                    if not parsed:
                        # Look for any text that starts with { and ends with }
                        json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', raw_text, re.DOTALL)
                        if json_match:
                            try:
                                match_text = json_match.group(0)
                                # Clean up trailing commas
                                match_text = re.sub(r',(\s*})', r'\1', match_text)
                                parsed = json.loads(match_text)
                                logger.info(f"Template A fallback parsing succeeded: {parsed}")
                            except json.JSONDecodeError as jde:
                                logger.info(f"Template A fallback parsing failed: {jde}")

                    if not parsed:
                        logger.error(f"Template A failed to extract JSON from raw text: {raw_text}")
                        raise ValueError("LLM did not return a JSON object")

                score_a = parsed.get("score", 0) / 1.0
                self.rationale_a = parsed.get("rationale", "")
                break

            except Exception as e:
                logger.warning(f"Attempt {retry + 1} for HallucinationMetric template A failed: {str(e)}")
                if retry == self.retry - 1:
                    logger.error(
                        f"Failed to get/parse LLM response for HallucinationMetric template A after {self.retry} attempts: {str(e)}"
                    )

        # Template B evaluation
        score_b = 0.0
        # Rationale stored in self.rationale_b
        for retry in range(self.retry):
            try:
                formatted_prompt = StringPromptValue(text=self.template_hallucination_b.format(
                    question=sample.user_input, answer=sample.response, passage=sources))

                try:
                    llm_with_so = self.llm.with_structured_output(HallucinationJudgment)
                    req_b = llm_with_so.ainvoke(formatted_prompt)
                    resp_b = await req_b
                    parsed = json.loads(resp_b.model_dump_json())
                except Exception as inner:
                    if "json_schema" not in str(inner):
                        raise
                    # Fallback to plain text generation for NVIDIA NIM
                    from langchain_core.messages import HumanMessage
                    raw = await self.llm.ainvoke([HumanMessage(content=formatted_prompt.text)])
                    raw_text = raw.content if hasattr(raw, 'content') else str(raw)

                    logger.info(f"Template B raw LLM response (attempt {retry + 1}):\n{raw_text}")

                    # Enhanced JSON extraction with multiple patterns
                    patterns = [
                        r'```json\s*(\{.*?\})\s*```',  # ```json {...} ```
                        r'```\s*(\{.*?\})\s*```',  # ``` {...} ```
                        r'(\{[^{}]*"rationale"[^{}]*"score"[^{}]*\})',  # Simple JSON with required fields
                        r'(\{.*?\})',  # Any JSON-like object
                    ]

                    parsed = None
                    for i, pattern in enumerate(patterns):
                        matches = re.findall(pattern, raw_text, re.DOTALL | re.IGNORECASE)
                        logger.info(f"Template B pattern {i+1} found {len(matches)} matches")
                        for match in matches:
                            try:
                                if isinstance(match, tuple):
                                    match = match[0] if match else ""
                                logger.info(f"Template B trying to parse match: {match}")

                                # Clean up the JSON string - remove trailing commas and fix formatting
                                cleaned_match = match.strip()
                                # Remove trailing comma before closing brace
                                cleaned_match = re.sub(r',(\s*})', r'\1', cleaned_match)

                                parsed = json.loads(cleaned_match)
                                if "score" in parsed:  # Verify it has the required field
                                    logger.info(f"Template B successfully parsed: {parsed}")
                                    break
                            except json.JSONDecodeError as jde:
                                logger.info(f"Template B JSON decode failed for: {match}, error: {jde}")
                                continue
                        if parsed:
                            break

                    # If regex patterns fail, try to extract JSON more aggressively
                    if not parsed:
                        # Look for any text that starts with { and ends with }
                        json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', raw_text, re.DOTALL)
                        if json_match:
                            try:
                                match_text = json_match.group(0)
                                # Clean up trailing commas
                                match_text = re.sub(r',(\s*})', r'\1', match_text)
                                parsed = json.loads(match_text)
                                logger.info(f"Template B fallback parsing succeeded: {parsed}")
                            except json.JSONDecodeError as jde:
                                logger.info(f"Template B fallback parsing failed: {jde}")

                    if not parsed:
                        logger.error(f"Template B failed to extract JSON from raw text: {raw_text}")
                        raise ValueError("LLM did not return a JSON object")

                score_b = parsed.get("score", 0) / 1.0
                self.rationale_b = parsed.get("rationale", "")
                break

            except Exception as e:
                logger.warning(f"Attempt {retry + 1} for HallucinationMetric template B failed: {str(e)}")
                if retry == self.retry - 1:
                    logger.error(
                        f"Failed to get/parse LLM response for HallucinationMetric template B after {self.retry} attempts: {str(e)}"
                    )

        # Print rationales if hallucinations detected
        if score_a > 0:
            print("Hallucination rationale (Template A):\n", self.rationale_a)
        if score_b > 0:
            print("Hallucination rationale (Template B):\n", self.rationale_b)

        # Return average of both template scores
        return (score_a + score_b) / 2.0


def prepare_hallucination_data_from_aira_example(example_data: dict) -> tuple:
    """
    Extract and prepare hallucination evaluation data from AIRA example exactly like the notebook.
    
    Args:
        example_data: AIRA example dictionary
        
    Returns:
        Tuple of (query, contexts_list) for hallucination evaluation
    """
    # Prefer an explicit 'query' field if it exists (future-proofing),
    # otherwise default to the dataset's `topic`.  We no longer append the
    # `report_organization` string because the hallucination metric should
    # evaluate faithfulness strictly against the original user question.
    query = example_data.get("query") or example_data.get("topic", "")

    # Prepare contexts exactly like the notebook
    contexts = []

    # Add RAG contexts - extract "context" field from each context dict
    rag_contexts = example_data.get("rag_contexts", [])
    for context_item in rag_contexts:
        if isinstance(context_item, dict) and "context" in context_item:
            contexts.append(context_item["context"])
        elif isinstance(context_item, str):
            contexts.append(context_item)

    # Add web answers - extract answer content after "ANSWER:"
    web_answers = example_data.get("web_answers", [])
    for web_answer in web_answers:
        if isinstance(web_answer, str) and "ANSWER:" in web_answer:
            answer_content = web_answer.split("ANSWER:")[-1].strip()
            contexts.append(answer_content)
        elif isinstance(web_answer, str):
            contexts.append(web_answer)

    return query, contexts


class HallucinationEvaluator:

    def __init__(self, llm: BaseLanguageModel, max_concurrency: int = 4, output_dir: str = None):
        self.llm = llm
        self.max_concurrency = max_concurrency
        self.output_dir = output_dir or ".tmp/aiq_aira"

    async def evaluate_item(self, item: EvalInputItem) -> EvalOutputItem:
        """
        Computes the hallucination score for an individual item.
        """
        if item.output_obj == "":
            # incase workflow is skipped (using --skip_workflow), input_obj contains the data source, as it contains the ground truth
            item.output_obj = item.input_obj
        data_source = AIResearcherEvalOutput.model_validate_json(item.output_obj)
        report = data_source.finalized_summary

        # Extract the report
        if not isinstance(report, str) or not report.strip():
            return EvalOutputItem(
                id=item.id,
                score=0.0,
                reasoning={
                    "error": "Generated report (finalized_summary) is empty or not a string.",
                    "debug_info": {
                        "has_finalized_summary":
                            data_source.finalized_summary is not None,
                        "keys_in_item":
                            list(data_source.model_dump().keys()) if isinstance(data_source, dict) else None,
                        "item_id":
                            item.id,
                    }
                })

        # The 'topic' field from the dataset is the most direct representation of the user's original query.
        query = data_source.topic

        # Prepare contexts from RAG and web search results
        contexts = []
        rag_contexts = data_source.rag_contexts
        if isinstance(rag_contexts, list):
            for context_item in rag_contexts:
                if isinstance(context_item, dict) and "context" in context_item:
                    contexts.append(context_item["context"])
                elif isinstance(context_item, str):
                    contexts.append(context_item)

        web_answers = data_source.web_answers
        if isinstance(web_answers, list):
            for web_answer in web_answers:
                if isinstance(web_answer, str):
                    # Handle cases where web_answer might be a simple string or contain "ANSWER:"
                    answer_content = web_answer.split("ANSWER:")[-1].strip()
                    if answer_content:
                        contexts.append(answer_content)

        # --- Sanity checks ---
        if not query.strip():
            query = "Assess hallucination for the provided report."

        if not contexts:
            # Without contexts, we cannot judge hallucination, so we return a neutral score of 0.
            return EvalOutputItem(id=item.id,
                                  score=0.0,
                                  reasoning={"error": "No contexts were available to evaluate for hallucination."})

        logger.info(
            f"Hallucination evaluation for item {item.id}: Query='{query[:50]}...', Contexts={len(contexts)}, Report Length={len(report)}"
        )

        # Evaluate hallucination
        sample = SingleTurnSample(user_input=query, response=report, retrieved_contexts=contexts)

        scorer = AIRAHallucination(llm=self.llm)
        score = await scorer._single_turn_ascore(sample=sample, callbacks=None)

        reasoning = {
            "hallucination_score": score,
            "report_snippet": report[:200] + ("..." if len(report) > 200 else ""),
            "query": query,
            "num_contexts": len(contexts),
            "rationale_a": scorer.rationale_a,
            "rationale_b": scorer.rationale_b,
        }

        return EvalOutputItem(id=item.id, score=score, reasoning=reasoning)

    async def evaluate(self, eval_input: EvalInput) -> EvalOutput:
        """
        Evaluate function that processes all items in the evaluation input.
        """
        semaphore = asyncio.Semaphore(self.max_concurrency)

        async def wrapped_evaluate_item(item: EvalInputItem) -> EvalOutputItem:
            async with semaphore:
                return await self.evaluate_item(item)

        eval_output_items = await asyncio.gather(*[wrapped_evaluate_item(item) for item in eval_input.eval_input_items])

        scores = [item.score for item in eval_output_items if item.score is not None]
        avg_score = sum(scores) / len(scores) if scores else 0.0

        return EvalOutput(average_score=avg_score, eval_output_items=eval_output_items)
