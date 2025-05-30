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

import streamlit as st
import os

# --- Step 1: Input ---
def render_input_step():
    """
    Renders the initial 'Report Input' step of the AI Research Assistant application.

    This function is responsible for:
    1.  Initializing session state variables for user inputs if they don't already exist.
        These include `topic`, `report_structure`, `num_queries`, `llm_name`,
        `use_internet`, and `num_reflections`. Default values are provided for a
        smoother user experience.
    2.  Displaying UI elements for capturing user input:
        -   A text input for the 'Report Topic'.
        -   A text area for the 'Report Structure / Organization', pre-filled with a
            default template.
        -   A number input for 'Number of Queries to Generate'.
        -   A number input for 'Number of Reflections' (for report refinement).
        -   A text input for 'LLM Name'.
        -   A toggle switch for 'Use Internet Search?'.
    3.  Storing the user's input directly into the corresponding `st.session_state`
        variables as they are entered.
    4.  Providing a "Generate Queries" button. When clicked:
        -   It validates that the 'Report Topic' and 'Report Structure' are filled.
        -   If valid, it initializes session state variables required for the next step
            (query generation), such as `is_generating_queries` and `final_queries`.
        -   It advances the application to the next step (`current_main_step = 1`)
            and triggers a Streamlit rerun.

    User inputs from this step are crucial for subsequent API calls that generate
    queries and, eventually, the research report.
    """
    # Initialize session state for input fields if they don't exist
    # These values serve as defaults or persist user input across reruns.
    if 'topic' not in st.session_state:
        st.session_state.topic = "Comprehensive Financial Report"
    if 'report_structure' not in st.session_state:
        st.session_state.report_structure = """You are a research assistant tasked with producing a concise, well-organized, and professional report.
Instructions:
1. The report must be: Factual, based on verifiable and reputable sources. Concise, no more than a dozen pages. Professional in tone, suitable for a business or academic audience.
2. If there is insufficient information or if reliable sources cannot be found, clearly indicate this in the report. Do not speculate or fabricate content.
3. Organize the report with:A clear executive summary (1–2 paragraphs).Main sections with headings relevant to the topic (e.g., Background, Key Findings, Gaps in Knowledge, Conclusion).
4. Use neutral language. Avoid subjective or persuasive language unless explicitly asked to provide analysis."""
    if 'num_queries' not in st.session_state:
        st.session_state.num_queries = 3
    if 'llm_name' not in st.session_state:
        st.session_state.llm_name = os.getenv("DEFAULT_LLM_NAME", "nemotron")
    if 'use_internet' not in st.session_state:
        st.session_state.use_internet = False
    if 'num_reflections' not in st.session_state:
        st.session_state.num_reflections = 1
        
    placeholder = st.empty()

    with placeholder.container():
        # --- UI Elements for Input ---
        st.session_state.topic = st.text_input(
                "Report Topic:",
            placeholder="Enter the main topic for your report.",
            key="topic_input",
            help="Enter the main topic for your report."
        )
        st.session_state.report_structure = st.text_area(
            "Report Structure / Organization:",
            value=st.session_state.report_structure,
            key="report_structure_input",
            height=250,
            help="Outline the desired sections or organization of the report (e.g., Introduction, Methods, Results, Conclusion)."
        )

        cols = st.columns(2) # Create a single two-column layout
        # --- Left Column ---
        with cols[0]:
            # Number of Queries Input
            st.session_state.num_queries = st.number_input(
                "Number of Queries to Generate:",
                min_value=1,
                max_value=10,
                value=st.session_state.num_queries,
                key="num_queries_input",
                help="How many distinct queries should be generated?"
            )
            # Number of Reflections Input
            st.session_state.num_reflections = st.number_input(
                "Number of Reflections:",
                min_value=1,
                max_value=10,
                value=st.session_state.num_reflections,
                key="num_reflections_input",
                help="How many times should the LLM reflect on the draft report before generating the final report?"
            )

        # --- Right Column ---
        with cols[1]:
            # LLM Name Input
            st.session_state.llm_name = st.text_input(
                "LLM Name:",
                value=st.session_state.llm_name,
                key="llm_name_input",
                help="Specify the language model to use for query generation (e.g., gpt-4, claude-3)."
            )
            st.write('<div style="height: 28px;"></div>', unsafe_allow_html=True)
            # Use Internet Toggle
            st.session_state.use_internet = st.toggle(
                "Use Internet Search?",
                value=st.session_state.use_internet,
                key="use_internet_input",
                help="Should the LLM be allowed to use the internet to answer queries?"
            )

        cols = st.columns(4)
        
        with cols[3]:
            # --- Action Button ---
            if st.button("✨ Generate Queries", type="primary", use_container_width=True, key="generate_queries_button"):
                # Validate inputs before proceeding
                if not st.session_state.topic.strip():
                    st.warning("Please enter a Report Topic.")
                elif not st.session_state.report_structure.strip():
                    st.warning("Please enter the Report Structure.")
                else:
                    # Initialize states required for the next step (query generation)
                    st.session_state.is_generating_queries = True
                    st.session_state.accumulated_thinking = "" # Reset thinking content for new generation
                    st.session_state.final_queries = []
                    placeholder.empty()
                    
                    # Advance to the next step in the application flow
                    st.session_state.current_main_step = 1
                    st.rerun() # Rerun Streamlit to reflect the change in step 