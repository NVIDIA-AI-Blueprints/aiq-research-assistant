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

from aiq.builder.builder import EvalBuilder
from aiq.builder.evaluator import EvaluatorInfo
from aiq.builder.framework_enum import LLMFrameworkEnum
from aiq.cli.register_workflow import register_evaluator

from aiq_aira.eval.evaluators.citation_quality_evaluator import CitationQualityEvaluator
from aiq_aira.eval.evaluators.citation_quality_evaluator import CitationQualityEvaluatorConfig
# Import evaluator classes and configs
from aiq_aira.eval.evaluators.coverage_evaluator import CoverageEvaluator
from aiq_aira.eval.evaluators.coverage_evaluator import CoverageEvaluatorConfig
from aiq_aira.eval.evaluators.hallucination_evaluator import HallucinationEvaluator
from aiq_aira.eval.evaluators.hallucination_evaluator import HallucinationEvaluatorConfig
from aiq_aira.eval.evaluators.ragas_wrapper_evaluator import RagasWrapperEvaluator
from aiq_aira.eval.evaluators.ragas_wrapper_evaluator import RagasWrapperEvaluatorConfig
from aiq_aira.eval.evaluators.synthesis_evaluator import SynthesisEvaluator
from aiq_aira.eval.evaluators.synthesis_evaluator import SynthesisEvaluatorConfig

# from aiq_aira.eval.evaluators.weave_evaluator import WeaveEvaluator, WeaveEvaluatorConfig
# from aiq_aira.eval.evaluators.artifact_uploader import ArtifactUploader, ArtifactUploaderConfig  # Commented out to avoid duplicate registration


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


@register_evaluator(config_type=RagasWrapperEvaluatorConfig)
async def register_ragas_wrapper_evaluator(config: RagasWrapperEvaluatorConfig, builder: EvalBuilder):
    """This function creates an instance of the RagasWrapperEvaluator."""
    llm = await builder.get_llm(config.llm, wrapper_type=LLMFrameworkEnum.LANGCHAIN)

    evaluator = RagasWrapperEvaluator(llm=llm, metric=config.metric)
    yield EvaluatorInfo(config=config, evaluate_fn=evaluator.evaluate, description="Ragas Wrapper Evaluator")


# @register_evaluator(config_type=WeaveEvaluatorConfig)
# async def register_weave_evaluator(config: WeaveEvaluatorConfig, builder: EvalBuilder):
#     """This function creates an instance of the WeaveEvaluator."""

#     evaluator = WeaveEvaluator(
#         config=config,
#         builder=builder
#     )
#     yield EvaluatorInfo(config=config, evaluate_fn=evaluator.evaluate, description="Weave Evaluator - Automatically integrates configured evaluators with Weave's evaluation framework")

# Commented out to avoid duplicate registration error
# @register_evaluator(config_type=ArtifactUploaderConfig)
# async def register_artifact_uploader(config: ArtifactUploaderConfig, builder: EvalBuilder):
#     """This function creates an instance of the ArtifactUploader."""
#     uploader = ArtifactUploader(
#         project_name=config.project_name,
#         run_name=config.run_name,
#         enabled=config.enabled,
#         wait_for_fresh_results=config.wait_for_fresh_results,
#         max_wait_time=config.max_wait_time,
#         output_dir=builder.eval_general_config.output_dir
#     )
#     yield EvaluatorInfo(config=config, evaluate_fn=uploader.evaluate, description="Artifact Uploader")
