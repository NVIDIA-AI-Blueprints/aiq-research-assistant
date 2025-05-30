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

from typing import Iterator
import streamlit as st
import json # Ensure json is imported
from utils.api_calls import generate_summary
from streamlit_extras.stylable_container import stylable_container

# --- Step 3: Execute Queries (Generate Summary/Draft) ---
def render_execute_queries_step():
    """
    Renders the 'Generate Report' step (internally, query execution and draft generation).

    This step is responsible for:
    1.  Checking if queries (`st.session_state.final_queries`) have been generated in the
        previous step. If not, it displays a warning and prevents further action.
    2.  If `st.session_state.final_report_content` is None (meaning the draft hasn't
        been generated yet for the current set of inputs/queries):
        a.  Initializing API log states (`st.session_state.api_logs`, `st.session_state.last_updated_log_key`).
        b.  Calling the `generate_summary` API endpoint. This API call uses the
            topic, report structure, finalized queries, and other settings (like
            web search permission, RAG collection, reflection count, LLM name) from
            `st.session_state` to produce an initial draft of the report.
        c.  Streaming the API response (which often includes thinking steps or logs)
            into a styled, scrollable container that mimics a terminal view.
        d.  Updating a `st.status` element to reflect the generation progress (running,
            completed).
    3.  If `st.session_state.final_report_content` already exists (e.g., user navigated
        back to this step), it displays previously captured logs or thinking process
        from `st.session_state.thinking_summary_tokens`.
    4.  Providing a "View Draft" button, which is enabled only after the
        `final_report_content` is populated. Clicking this button advances the user
        to the final report viewing step (`current_main_step += 1`) and triggers a rerun.

    The core outcome of this step is the population of `st.session_state.final_report_content`
    with the generated draft report from the API.
    """

    # Check if queries have been generated; if not, display a warning and placeholder.
    if len(st.session_state.final_queries) == 0:
        st.warning("No queries generated. Please generate queries first.")
        # Display a placeholder image or message if no queries are available.
        st.image("https://static.streamlit.io/examples/dog.jpg", width=200) 
        return
    
    status = st.status("Generating initial draft and citations...", expanded=False, state="complete")
    # --- Initial Draft Generation ---
    # This block executes if the draft report content hasn't been populated yet.
    # It calls the `generate_summary` API, which is responsible for using the queries
    # to fetch information and synthesize it into a draft.
    if st.session_state.final_report_content is None:
        # Initialize logs for the current generation
        st.session_state.api_logs = {}
        st.session_state.last_updated_log_key = None        
        # Call the API to generate the summary/draft.
        # Parameters include the topic, report structure, generated queries, and other settings.
        stream = generate_summary(
            topic=st.session_state.topic,
            report_organization=st.session_state.report_structure,
            queries=st.session_state.final_queries,
            search_web=True, # Option to include web search in information gathering
            rag_collection=st.session_state.selected_collection_name, # RAG collection to use
            reflection_count=st.session_state.num_reflections, # Parameter for the generation process (e.g., self-reflection steps)
            llm_name=st.session_state.llm_name # LLM to use for summary generation
        )
        
        # Create a container for the dynamic log display
        log_display_container = stylable_container(
                    key="auto-scroll-container",
                    css_styles="""
                        {
                            background-color: #1e1e1e; /* Dark gray background */
                            color: #d4d4d4; /* Light gray text */
                            font-family: 'Menlo', 'Monaco', 'Consolas', monospace; /* Monospaced font */
                            height: 500px; /* Set desired height */
                            overflow-y: auto; /* Allow vertical scrolling */
                            display: flex;
                            flex-direction: column-reverse; /* Newest content at the bottom */
                            padding: 15px; /* Padding inside the terminal */
                            border-radius: 6px; /* Rounded corners */
                            border: 1px solid #333; /* Subtle border */
                        }
                        """,
                )

        status.update(expanded=True, state="running")
        st.session_state.thinking_summary_tokens = dict()
        with status:
            with log_display_container:
                with st.empty():
                    for v in stream:
                        current_key = list(v.keys())[0]
                        if current_key not in st.session_state.thinking_summary_tokens:
                            status.update(label=current_key, state="running", expanded=True)
                            st.session_state.thinking_summary_tokens[current_key] = v[current_key]
                        else:
                            st.session_state.thinking_summary_tokens[current_key] += v[current_key]
                            st.json(st.session_state.thinking_summary_tokens)
            status.update(label="Draft generated!", state="complete", expanded=False)
            st.rerun()
    else:
        # Display previously generated logs if they exist
        if "thinking_summary_tokens" in st.session_state and st.session_state.thinking_summary_tokens:
            status.update(label="Previously Captured Logs", expanded=True)
            with status:
                with stylable_container(
                    key="auto-scroll-container",
                    css_styles="""
                        {
                            background-color: #1e1e1e; /* Dark gray background */
                            color: #d4d4d4; /* Light gray text */
                            font-family: 'Menlo', 'Monaco', 'Consolas', monospace; /* Monospaced font */
                            height: 500px; /* Set desired height */
                            overflow-y: auto; /* Allow vertical scrolling */
                            display: flex;
                            flex-direction: column-reverse; /* Newest content at the bottom */
                            padding: 15px; /* Padding inside the terminal */
                            border-radius: 6px; /* Rounded corners */
                            border: None; /* Subtle border */
                        }
                        """,
                ):
                    st.write(st.session_state.thinking_summary_tokens)

        # Button to proceed to the next step (Execute Queries).
        # Disabled if no queries have been generated yet.
        cols = st.columns(4)
        
        with cols[3]:
            # --- Action Button ---
            # Button to proceed to the next step (View Draft).
            # This button should ideally be enabled only after the draft is generated.
            if st.button("✨ View Draft", type="primary", use_container_width=True, key="view_draft_button", disabled=(st.session_state.final_report_content is None)):
                st.session_state.current_main_step += 1 # Advance to final report step
                st.rerun()