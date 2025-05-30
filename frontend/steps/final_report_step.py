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
from components.chat import chat_box
from streamlit_extras.stylable_container import stylable_container

# --- Step 5: Final Report ---
def render_final_report_step():
    """
    Renders the 'Final Report' step in the AI Research Assistant application.

    This function is responsible for:
    1.  Checking if `st.session_state.final_report_content` exists. If not, it displays
        an informational message and exits, as there is no report to show.
    2.  If report content is available, it sets up a two-column layout:
        -   **Left Column**: Displays the `final_report_content` within a scrollable,
            styled container using `st.markdown`. `unsafe_allow_html=True` is used,
            implying the report content might contain HTML.
        -   **Right Column**: Contains:
            a.  A subheader for "Chat: Q&A on Report".
            b.  A `chat_box` component for interacting with the report. This chat
                can operate in two modes (controlled by a conceptual `mode` variable,
                though its direct implementation via `st.segmented_control` might be
                elsewhere or implied by `rewrite_mode`):
                -   **Edit Mode**: Allows the user to refine the entire report content.
                    The `on_artifact_update` callback updates
                    `st.session_state.final_report_content` and reruns the app.
                -   **Chat Mode**: Allows Q&A about the report content without direct editing.
            c.  A (likely intended) `st.segmented_control` to switch between "Edit Mode" and
                "Chat Mode" for the chat box.
            d.  A `st.download_button` that allows the user to download the
                `final_report_content` as a Markdown file.
                The filename includes the `report_id` from session state.

    The primary purpose is to present the generated report to the user and provide
    tools for review, minor edits via chat, Q&A, and download.
    The `finalize_report` API call mentioned in the original docstring seems to be missing
    from the current implementation of this specific function but might be part of an
    earlier step or an intended feature.
    """
    # --- Finalization Logic ---
    # Check if the final report content is already populated.
    # If not, it means the report needs to be finalized (potentially via an API call).
    if not st.session_state.final_report_content:
        st.info("The report has not been finalized yet.")
        return
    # --- UI Layout for Final Report ---
    # Use columns for layout: report content on the left, Q&A chat on the right.
    col1, col2 = st.columns([3, 1.5])
    with col1:
        # Display the final report content using Markdown.
        # `unsafe_allow_html=True` is used; ensure content is trusted if sourced externally.
        with stylable_container(
            key="auto-scroll-container",
            css_styles="""
                {
                    height: 600px;
                    width: 100%;
                    max-width: 100%;
                    overflow-y: auto;
                    overflow-x: hidden;
                    padding: 10px;
                    font-family: monospace;
                }
                """,
        ):
            st.markdown(st.session_state.final_report_content, unsafe_allow_html=True)

    with col2:
        st.subheader("Chat: Q&A on Report")
        mode = "Edit Report"
        
        def on_artifact_update(updated_artifact):
            st.session_state.final_report_content = updated_artifact
            st.rerun()

        # Integrate the chat component for Q&A and edit report.
        chat_box(
            chat_key="final_qa_chat_main_step",
            artifact=str(st.session_state.final_report_content),
            initial_prompt="Hi, I can help you answer questions about the final report!",
            placeholder="Ask a question about the final report...",
            use_internet=False,
            rewrite_mode=None if mode == "Chat with Report" else "entire",
            additional_context=None,
            on_artifact_update=on_artifact_update if mode == "Edit Report" else None,
            height=500
        )
        
        col1_2, col2_2 = st.columns([1, 1])
        with col1_2:
            st.segmented_control(
                "",
                ["Edit Mode", "Chat Mode"],
                selection_mode="single",
                label_visibility="collapsed",
                default="Edit Mode"
            )
        with col2_2:
            # Download button for the report (as a Markdown file).
            st.download_button(
                label="Download Report", 
                type="primary",
                data=st.session_state.final_report_content,
                file_name=f"final_report_{st.session_state.report_id}.md",
                mime="text/markdown",
                use_container_width=True
            )
