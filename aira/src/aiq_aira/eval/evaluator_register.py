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

from nat.builder.builder import EvalBuilder
from nat.builder.evaluator import EvaluatorInfo
from nat.builder.framework_enum import LLMFrameworkEnum
from nat.cli.register_workflow import register_evaluator

from aiq_aira.eval.evaluators.citation_quality_evaluator import CitationF1Evaluator
from aiq_aira.eval.evaluators.citation_quality_evaluator import CitationF1EvaluatorConfig
from aiq_aira.eval.evaluators.citation_quality_evaluator import CitationPrecisionEvaluator
from aiq_aira.eval.evaluators.citation_quality_evaluator import CitationPrecisionEvaluatorConfig
from aiq_aira.eval.evaluators.citation_quality_evaluator import CitationQualityEvaluator
from aiq_aira.eval.evaluators.citation_quality_evaluator import CitationQualityEvaluatorConfig
from aiq_aira.eval.evaluators.citation_quality_evaluator import CitationRecallEvaluator
from aiq_aira.eval.evaluators.citation_quality_evaluator import CitationRecallEvaluatorConfig
# Import evaluator classes and configs
from aiq_aira.eval.evaluators.coverage_evaluator import CoverageEvaluator
from aiq_aira.eval.evaluators.coverage_evaluator import CoverageEvaluatorConfig
from aiq_aira.eval.evaluators.hallucination_evaluator import HallucinationEvaluator
from aiq_aira.eval.evaluators.hallucination_evaluator import HallucinationEvaluatorConfig
from aiq_aira.eval.evaluators.ragas_wrapper_evaluator import RagasWrapperEvaluator
from aiq_aira.eval.evaluators.ragas_wrapper_evaluator import RagasWrapperEvaluatorConfig
from aiq_aira.eval.evaluators.synthesis_evaluator import SynthesisEvaluator
from aiq_aira.eval.evaluators.synthesis_evaluator import SynthesisEvaluatorConfig


@register_evaluator(config_type=CoverageEvaluatorConfig)
async def register_coverage_evaluator(config: CoverageEvaluatorConfig, builder: EvalBuilder):
    """This function creates an instance of the CoverageEvaluator."""
    llm = await builder.get_llm(config.llm, wrapper_type=LLMFrameworkEnum.LANGCHAIN)

    evaluator = CoverageEvaluator(
        llm=llm,
        max_concurrency=config.max_concurrency,
        output_dir=builder.eval_general_config.output_dir,
    )
    yield EvaluatorInfo(config=config, evaluate_fn=evaluator.evaluate, description="Coverage Evaluator")


@register_evaluator(config_type=HallucinationEvaluatorConfig)
async def register_hallucination_evaluator(config: HallucinationEvaluatorConfig, builder: EvalBuilder):
    """This function creates an instance of the HallucinationEvaluator."""
    llm = await builder.get_llm(config.llm, wrapper_type=LLMFrameworkEnum.LANGCHAIN)

    evaluator = HallucinationEvaluator(
        llm=llm,
        output_dir=builder.eval_general_config.output_dir,
    )
    yield EvaluatorInfo(config=config, evaluate_fn=evaluator.evaluate, description="Hallucination Evaluator")


@register_evaluator(config_type=SynthesisEvaluatorConfig)
async def register_synthesis_evaluator(config: SynthesisEvaluatorConfig, builder: EvalBuilder):
    """This function creates an instance of the SynthesisEvaluator."""
    llm = await builder.get_llm(config.llm, wrapper_type=LLMFrameworkEnum.LANGCHAIN)

    evaluator = SynthesisEvaluator(
        llm=llm,
        output_dir=builder.eval_general_config.output_dir,
    )
    yield EvaluatorInfo(config=config, evaluate_fn=evaluator.evaluate, description="Synthesis Evaluator")


@register_evaluator(config_type=CitationQualityEvaluatorConfig)
async def register_citation_quality_evaluator(config: CitationQualityEvaluatorConfig, builder: EvalBuilder):
    """This function creates an instance of the CitationQualityEvaluator."""
    llm = await builder.get_llm(config.llm, wrapper_type=LLMFrameworkEnum.LANGCHAIN)

    evaluator = CitationQualityEvaluator(
        llm=llm,
        output_dir=builder.eval_general_config.output_dir,
    )
    yield EvaluatorInfo(config=config, evaluate_fn=evaluator.evaluate, description="Citation Quality Evaluator")


@register_evaluator(config_type=CitationPrecisionEvaluatorConfig)
async def register_citation_precision_evaluator(config: CitationPrecisionEvaluatorConfig, builder: EvalBuilder):
    """This function creates an instance of the CitationPrecisionEvaluator."""
    llm = await builder.get_llm(config.llm, wrapper_type=LLMFrameworkEnum.LANGCHAIN)

    evaluator = CitationPrecisionEvaluator(
        llm=llm,
        output_dir=builder.eval_general_config.output_dir,
    )
    yield EvaluatorInfo(config=config, evaluate_fn=evaluator.evaluate, description="Citation Precision Evaluator")


@register_evaluator(config_type=CitationRecallEvaluatorConfig)
async def register_citation_recall_evaluator(config: CitationRecallEvaluatorConfig, builder: EvalBuilder):
    """This function creates an instance of the CitationRecallEvaluator."""
    llm = await builder.get_llm(config.llm, wrapper_type=LLMFrameworkEnum.LANGCHAIN)

    evaluator = CitationRecallEvaluator(
        llm=llm,
        output_dir=builder.eval_general_config.output_dir,
    )
    yield EvaluatorInfo(config=config, evaluate_fn=evaluator.evaluate, description="Citation Recall Evaluator")


@register_evaluator(config_type=CitationF1EvaluatorConfig)
async def register_citation_f1_evaluator(config: CitationF1EvaluatorConfig, builder: EvalBuilder):
    """This function creates an instance of the CitationF1Evaluator."""
    llm = await builder.get_llm(config.llm, wrapper_type=LLMFrameworkEnum.LANGCHAIN)

    evaluator = CitationF1Evaluator(
        llm=llm,
        output_dir=builder.eval_general_config.output_dir,
    )
    yield EvaluatorInfo(config=config, evaluate_fn=evaluator.evaluate, description="Citation F1 Evaluator")


@register_evaluator(config_type=RagasWrapperEvaluatorConfig)
async def register_ragas_wrapper_evaluator(config: RagasWrapperEvaluatorConfig, builder: EvalBuilder):
    """This function creates an instance of the RagasWrapperEvaluator."""
    llm = await builder.get_llm(config.llm, wrapper_type=LLMFrameworkEnum.LANGCHAIN)

    evaluator = RagasWrapperEvaluator(llm=llm, metric=config.metric)
    yield EvaluatorInfo(config=config, evaluate_fn=evaluator.evaluate, description="Ragas Wrapper Evaluator")
