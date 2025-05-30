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

# components/__init__.py
"""
Package for reusable UI components in the AI Research Assistant application.

This package is intended to house modules that define self-contained, reusable
Streamlit UI components. These components can be imported and used across
different parts of the application, promoting modularity and code reuse.

For example, a `chat.py` module within this package might define a `chat_box`
function that renders a complete chat interface.

By centralizing common UI elements here, the main application logic and step-specific
rendering functions can remain cleaner and more focused on their primary tasks.
"""
# This file makes the 'components' directory a Python package. 