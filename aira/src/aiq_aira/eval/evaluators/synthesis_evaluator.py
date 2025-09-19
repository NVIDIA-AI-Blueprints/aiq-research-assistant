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

# --- Pydantic Models and Config ---


class SynthesisEvaluatorConfig(EvaluatorBaseConfig, name="synthesis"):
    """Configuration for the synthesis evaluator."""
    llm: LLMRef = Field(description="The LLM to use for evaluation.")
    is_workflow_output: bool = Field(
        False, description="Flag to indicate if this is a workflow output file with complete data.")


class SynthesisJudgment(BaseModel):
    """LLM Judgment of synthesis quality (0-4 scale)."""
    rationale: str = Field(description="Brief explanation of your reasoning")
    score: int = Field(description="Score from 0 to 4")


# --- Core Metric Logic ---

template_synthesis_a = """You are an expert evaluator tasked with assessing the quality of information synthesis from multiple sources. You will evaluate how well a report integrates and synthesizes information from provided source excerpts.

## Scoring Rubric

You will assign a score from 0-4 based on the following criteria:

For any level, **all bullets under that level (and every lower level) must be met**.
If even one required bullet is missing, grade at the next lower level.  
A perfect **4** should be rare (≈ ≤ 10 % of reports).

---

### **0 - Pure extraction (merely copies facts, no synthesis)**
- Discusses each source in isolation; no cross-referencing or linking of ideas  
- Merely restates or paraphrases source content sentence-by-sentence  
- No attempt to weigh, prioritise, or interpret information  
- **Automatic knock-out:** any report that is essentially a stitched-together summary of individual sources  

---

### **1 - Aggregation (lists facts, minimal integration)**
- Draws material from at least two sources but presents it sequentially rather than relationally  
- Groups similar points superficially (e.g., simple bullet clusters)  
- Mentions multiple sources without comparing or contrasting them  
- **Automatic knock-out:** no explicit statements highlighting relationships between sources  

---

### **2 - Basic integration (combines sources, little insight / no conflict resolution)**
- Mixes evidence from multiple sources within thematic sections  
- Makes simple connections (e.g., "Both studies suggest X")  
- Notes—but does not analyse or resolve—conflicting findings  
- Generates only basic, surface-level inferences  
- **Automatic knock-out:** leaves a clear contradiction unaddressed **or** "resolves" it using speculation lacking evidence  

---

### **3 - Solid synthesis (addresses conflicts, some original insight)**
- Interleaves evidence from three or more sources into a single narrative argument  
- Explicitly compares/contrasts sources and justifies why some evidence carries more weight (e.g., based on methodology, sample size, recency)  
- Analytically explains agreements **and** disagreements, offering evidence-based reasoning  
- Produces at least one new takeaway that combines information across sources  
- **Automatic knock-out:** omits discussion of a major, known contradiction among cited sources  

---

### **4 - Expert, insight-rich synthesis (reconciles conflicts, draws novel conclusions)**
- Covers **all** relevant sources for the topic (breadth) while emphasising the highest-quality and most recent evidence (depth)  
- Systematically reconciles every key discrepancy using methodological critique, context, or data-quality considerations  
- Generates multiple original conclusions, frameworks, or hypotheses that do **not** appear in any single source but logically follow from the combined evidence  
- Clearly articulates residual uncertainties, limitations, and potential future directions  
- Demonstrates critical thinking throughout—moving beyond summary to construct a coherent, logically progressive argument  
- **Automatic knock-out:** any unsupported assertion presented as synthesis **or** failure to explain resolution of a critical contradiction  

---

### Usage tips
1. **Grade down** if **any** required bullet under the intended level is missing.  
2. **Grade up** only when every bullet for that level *and below* is satisfied **and** no knock-out conditions apply.  
3. If a report straddles two levels, assign the lower score.


## Source Excerpts

<sources>
{sources}
</sources>

## Report to Evaluate

<report>
{report}
</report>

## Evaluation Process

1. First, carefully read and understand all source excerpts.
2. Then, read the report thoroughly.
3. Analyze how information from the sources has been incorporated into the report:
    - Does it merely copy or paraphrase individual facts?
    - Does it make connections between related information from different sources?
    - Does it identify and resolve conflicts between sources?
    - Does it draw insights or conclusions not explicitly stated in any single source?
4. Consider the overall coherence and depth of understanding demonstrated in the report.
5. Provide a brief but specific rationale for your score.
6. Assign the appropriate score (0, 1, 2, 3, or 4) based on the rubric.

## Output Format

Return your evaluation in JSON format as follows:
```json
{{
"rationale": "<brief reason>",
"score": <int 0-4>,
}}
```

Your rationale should be concise (1-3 sentences) but should specifically reference how the report handled information from the sources.
"""

template_synthesis_b = """# Information Synthesis Evaluation

You are tasked with evaluating how well a report synthesizes information from multiple sources. Your goal is to assess the level of insight and integration demonstrated in the report, not just factual accuracy.

## Scoring System
You will assign a score from 0-4 based on the following criteria:
- **0 = Merely copies facts, no synthesis**: The report simply repeats or paraphrases information from the sources without connecting ideas or adding value.
- **2 = Combines sources but little insight**: The report brings together information from different sources but does little to identify patterns, implications, or deeper connections.
- **4 = Expertly synthesizes**: The report not only integrates information across sources but also identifies meaningful patterns, draws insightful conclusions, or provides a novel perspective that adds value beyond what's explicitly stated in the sources.

## Evaluation Criteria
Consider the following when evaluating:
- Does the report identify connections across sources that aren't obvious?
- Does it recognize patterns or themes across the information?
- Does it draw meaningful conclusions that require understanding multiple sources?
- Does it provide context or implications that demonstrate deeper understanding?
- Does it organize information in a way that creates new meaning?
- Does it go beyond summarizing to offer genuine insights?

## Report to Evaluate
Now, read the report that needs evaluation:

<report>
{report}
</report>

## Source Material
First, carefully read these source excerpts:

<sources>
{sources}
</sources>

## Analysis Process
1. First, carefully compare the report to the source material.
2. Identify which elements of the report come from which sources.
3. Analyze how information from different sources is integrated.
4. Determine whether the report adds value beyond what's in the sources.
5. Consider whether connections made across sources demonstrate insight.

## Your Response
Provide your evaluation in JSON format with two fields:
1. "rationale": A brief explanation (1-3 sentences) justifying your score
2. "score": An integer from 0 to 4

Your response should follow this format:
```json
{{
"rationale": "<brief explanation of your reasoning>",
"score": <integer 0-4>,
}}
```
"""


@dataclass
class AIRASynthesis(MetricWithLLM, SingleTurnMetric):
    name: str = "synthesis_score"
    _required_columns: t.Dict[MetricType, t.Set[str]] = field(default_factory=lambda: {
        MetricType.SINGLE_TURN: {
            "response",  # The generated report
            "reference",  # The combined source texts
        }, })
    retry: int = 5
    rationale_a: str = ""
    rationale_b: str = ""

    async def _get_score_with_retry(self, template: str, report: str, sources: str) -> t.Tuple[float, str]:
        for attempt in range(self.retry):
            try:
                formatted_prompt = StringPromptValue(text=template.format(report=report, sources=sources))

                # First, try with structured output
                llm_with_so = self.llm.with_structured_output(SynthesisJudgment)
                resp = await llm_with_so.ainvoke(formatted_prompt)
                parsed = json.loads(resp.model_dump_json())

                score = parsed.get("score", 0) / 4.0
                rationale = parsed.get("rationale", "")
                return score, rationale
            except Exception as e:
                # Fallback to parsing raw text if structured output fails
                logger.info(f"Structured output failed (attempt {attempt + 1}), trying raw text parsing: {str(e)}")
                try:
                    from langchain_core.messages import HumanMessage
                    raw_resp = await self.llm.ainvoke([HumanMessage(content=formatted_prompt.text)])
                    raw_text = raw_resp.content if hasattr(raw_resp, 'content') else str(raw_resp)

                    logger.info(f"Raw LLM response (attempt {attempt + 1}):\n{raw_text}")

                    json_match = re.search(r'```json\s*(\{.*?\})\s*```', raw_text, re.DOTALL)
                    if not json_match:
                        json_match = re.search(r'(\{.*?\})', raw_text, re.DOTALL)

                    if json_match:
                        json_str = json_match.group(1)
                        # Clean up common JSON errors like trailing commas
                        json_str = re.sub(r',(\s*})', r'\1', json_str)
                        parsed = json.loads(json_str)

                        score = parsed.get("score", 0) / 4.0
                        rationale = parsed.get("rationale", "")
                        logger.info(f"Successfully parsed fallback JSON: {parsed}")
                        return score, rationale

                    logger.error(f"Failed to extract JSON from raw text: {raw_text}")

                except Exception as fallback_e:
                    logger.warning(f"Fallback parsing also failed (attempt {attempt + 1}): {str(fallback_e)}")

            if attempt == self.retry - 1:
                logger.error(f"Failed to get/parse LLM response after {self.retry} attempts")
        return 0.0, ""

    async def _single_turn_ascore(self, sample: SingleTurnSample, callbacks: Callbacks) -> float:
        assert self.llm is not None, "LLM is not set"
        assert sample.response is not None, "Report is not set"
        assert sample.reference is not None, "Source texts are not set"

        if not sample.response.strip(): return 0.0
        if not sample.reference.strip(): return 1.0

        report = sample.response.strip()
        sources = sample.reference.strip()

        score_a, self.rationale_a = await self._get_score_with_retry(template_synthesis_a, report, sources)
        score_b, self.rationale_b = await self._get_score_with_retry(template_synthesis_b, report, sources)

        return (score_a + score_b) / 2.0


# --- Main Evaluator Class ---


class SynthesisEvaluator:

    def __init__(self, llm: BaseLanguageModel, max_concurrency: int = 4, output_dir: str = None):
        self.llm = llm
        self.max_concurrency = max_concurrency
        self.output_dir = output_dir or ".tmp/aiq_aira"

    async def evaluate_item(self, item: EvalInputItem) -> EvalOutputItem:
        """
        Evaluate synthesis quality for a single item.
        """
        if item.output_obj == "":
            # incase workflow is skipped (using --skip_workflow), input_obj contains the data source, as it contains the ground truth
            item.output_obj = item.input_obj
        data_source = AIResearcherEvalOutput.model_validate_json(item.output_obj)
        # Extract the report
        report = data_source.finalized_summary
        if not report.strip():
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

        # Extract contexts for synthesis evaluation
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
                    answer_content = web_answer.split("ANSWER:")[-1].strip()
                    if answer_content:
                        contexts.append(answer_content)

        if not contexts:
            return EvalOutputItem(id=item.id,
                                  score=0.0,
                                  reasoning={"error": "No contexts available for synthesis evaluation."})

        source_texts = "\n".join(contexts)
        logger.info(f"Synthesis evaluation for item {item.id}: Report Length={len(report)}, Contexts={len(contexts)}")

        # Evaluate synthesis quality
        sample = SingleTurnSample(response=report, reference=source_texts)
        scorer = AIRASynthesis(llm=self.llm)
        score = await scorer._single_turn_ascore(sample=sample, callbacks=None)

        reasoning = {
            "synthesis_score": score,
            "report_snippet": report[:200] + "..." if len(report) > 200 else "",
            "num_contexts": len(contexts),
            "rationale_a": scorer.rationale_a,
            "rationale_b": scorer.rationale_b,
        }

        return EvalOutputItem(id=item.id, score=score, reasoning=reasoning)

    async def evaluate(self, eval_input: EvalInput) -> EvalOutput:
        semaphore = asyncio.Semaphore(self.max_concurrency)

        async def wrapped_evaluate_item(item: EvalInputItem) -> EvalOutputItem:
            async with semaphore:
                return await self.evaluate_item(item)

        eval_output_items = await asyncio.gather(*[wrapped_evaluate_item(item) for item in eval_input.eval_input_items])

        scores = [item.score for item in eval_output_items if item.score is not None]
        avg_score = sum(scores) / len(scores) if scores else 0.0

        return EvalOutput(average_score=avg_score, eval_output_items=eval_output_items)
