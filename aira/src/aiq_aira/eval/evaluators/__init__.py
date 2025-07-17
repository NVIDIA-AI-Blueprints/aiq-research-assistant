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
"""
AIRA Evaluator - Evaluation framework for AI Research Assistant workflows

This package provides evaluation capabilities for the AI Research Assistant (AIRA)
following the patterns established in the SWE bench evaluation framework.
"""
# Evaluators for AIRA workflow
from .coverage_evaluator import CoverageEvaluator, CoverageEvaluatorConfig
from .synthesis_evaluator import SynthesisEvaluator, SynthesisEvaluatorConfig
from .hallucination_evaluator import HallucinationEvaluator, HallucinationEvaluatorConfig
from .citation_quality_evaluator import CitationQualityEvaluator, CitationQualityEvaluatorConfig
from .ragas_wrapper_evaluator import RagasWrapperEvaluator, RagasWrapperEvaluatorConfig
# from .weave_evaluator import WeaveEvaluator, WeaveEvaluatorConfig

__all__ = [
    "CoverageEvaluator",
    "CoverageEvaluatorConfig",
    "SynthesisEvaluator",
    "SynthesisEvaluatorConfig",
    "HallucinationEvaluator",
    "HallucinationEvaluatorConfig",
    "CitationQualityEvaluator",
    "CitationQualityEvaluatorConfig",
    "RagasWrapperEvaluator",
    "RagasWrapperEvaluatorConfig",
]
