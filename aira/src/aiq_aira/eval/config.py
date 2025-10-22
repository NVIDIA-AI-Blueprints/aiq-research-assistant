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

import typing

from nat.data_models.common import BaseModelRegistryTag
from nat.data_models.common import TypedBaseModel
from nat.data_models.component_ref import FunctionRef
from nat.data_models.component_ref import LLMRef
from nat.data_models.function import FunctionBaseConfig
from pydantic import Discriminator
from pydantic import Field
from pydantic import Tag


class AIRAGeneratorBaseConfig(TypedBaseModel, BaseModelRegistryTag):
    description: str = "AI-Q Research Assistant Generator"


class AIRAGeneratorFullConfig(AIRAGeneratorBaseConfig, name="full"):
    llm_name: str = Field(default="nemotron")
    fact_extraction_llm: str = Field(default="fact_extraction_llm")
    citation_pairing_llm: str = Field(default="gpt-4o-20241120")  # Configurable LLM for citation pairing
    verbose: bool = True


class AIRAGeneratorGoldConfig(AIRAGeneratorBaseConfig, name="gold"):
    verbose: bool = True


class AIRAGeneratorSkeletonConfig(AIRAGeneratorBaseConfig, name="skeleton"):
    verbose: bool = False


AIRAGeneratorConfig = typing.Annotated[
    typing.Annotated[AIRAGeneratorFullConfig, Tag(AIRAGeneratorFullConfig.static_type())]
    | typing.Annotated[AIRAGeneratorGoldConfig, Tag(AIRAGeneratorGoldConfig.static_type())]
    | typing.Annotated[AIRAGeneratorSkeletonConfig, Tag(AIRAGeneratorSkeletonConfig.static_type())],
    Discriminator(TypedBaseModel.discriminator)]


class AIRAEvaluatorWorkflowConfig(FunctionBaseConfig, name="aira_evaluator_workflow"):
    generator: AIRAGeneratorConfig
