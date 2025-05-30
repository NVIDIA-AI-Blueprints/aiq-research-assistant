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
Package for UI rendering functions of distinct steps in the AI Research Assistant.

This package consolidates the individual UI rendering functions for each step
of the multi-stage report generation process within the Streamlit application.

Modules within this package typically define a primary function (e.g., `render_input_step`)
that is responsible for displaying the UI elements and handling the logic specific
to that particular stage of the workflow. This includes tasks like:
-   User input collection (e.g., report topic, parameters).
-   Query generation and refinement.
-   Report draft generation and display.
-   Final report presentation and interaction.

By organizing step-specific rendering logic into separate modules, this package
contributes to a more modular and maintainable codebase for the main application
(`app.py`). The `__all__` list explicitly defines the public interface of this
package, making these rendering functions easily importable by the main application.
"""

from .input_step import render_input_step
from .generate_queries_step import render_generate_queries_step
from .execute_queries_step import render_execute_queries_step
from .final_report_step import render_final_report_step

__all__ = [
    "render_input_step",
    "render_generate_queries_step",
    "render_execute_queries_step",
    "render_final_report_step",
] 