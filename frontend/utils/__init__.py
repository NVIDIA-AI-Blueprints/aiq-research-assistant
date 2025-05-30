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

# utils/__init__.py
"""
Package for utility functions supporting the AI Research Assistant frontend.

This package houses modules that provide general-purpose utility functions
used throughout the Streamlit application. These utilities are not specific
to any single UI component or application step but offer common services.

A key example is the `api_calls.py` module, which centralizes all functions
responsible for communication with backend APIs. This includes managing API
configurations, constructing requests, handling responses and errors, and
supporting streaming data.

By organizing such utilities into this package, the main application code
(`app.py`) and other modules (like those in `steps/` and `components/`)
can remain focused on their specific UI and logic tasks, importing utility
functions as needed.
"""
# This file makes the 'utils' directory a Python package. 