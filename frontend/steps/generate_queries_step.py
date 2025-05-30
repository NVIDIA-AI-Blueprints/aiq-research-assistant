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
from utils.api_calls import generate_query
from components.chat import chat_box
import ast
from streamlit_extras.stylable_container import stylable_container
from code_editor import code_editor
import json

# --- Step 2: Generate Queries ---
def render_generate_queries_step():
    """
    Renders the 'Generate Queries' step in the AI Research Assistant application.

    This step is responsible for:
    1.  Initializing session state variables specific to query generation (e.g.,
        `is_generating_queries`, `accumulated_thinking`, `final_queries`).
    2.  Providing a UI layout with two main columns:
        -   Left column: Displays the model's "thinking" process (streamed from the API)
            and the final generated queries in an editable code editor.
        -   Right column: Features a chat interface (`chat_box`) allowing users to
            refine or modify the generated queries.
    3.  Triggering the API call to `generate_query` when queries are not yet present
        and the generation process is initiated by the user (implicitly from a
        previous step or action).
    4.  Handling the streaming response from the API, displaying intermediate thoughts,
        and parsing the final query list.
    5.  Managing the state of the "Execute Queries" button, enabling it only when
        queries are available.
    6.  Navigating to the next step ('Execute Queries') upon button click.

    The generated queries are stored in `st.session_state.final_queries` and can be
    edited directly in the UI or via the chat interface.
    """
    # Initialize session state variables specific to this step if they don't exist.
    # These ensure that the state persists across Streamlit reruns.
    if 'is_generating_queries' not in st.session_state:
        st.session_state.is_generating_queries = False
    if 'accumulated_thinking' not in st.session_state:
        st.session_state.accumulated_thinking = ""
    if 'final_queries' not in st.session_state:
        st.session_state.final_queries = []

    placeholder = st.empty()

    with placeholder.container():
        # --- UI Layout for Query Generation ---
        # Use columns for layout: main content on the left, chat/refinement on the right.
        col1, col2 = st.columns([3, 2])

    with col1:
        # Placeholder for status messages (e.g., success, error).
        status_placeholder_gq = st.empty()
        
        # st.status is used to show the progress of the query generation.
        # It can be expanded to show detailed "thoughts" or collapsed when complete.
        status = st.status("Model Thoughts", expanded=False, state="complete")
        
        # Display the final generated queries.
        if st.session_state.final_queries:
            with st.container(height=500, border=False):
                response_dict = code_editor(json.dumps(st.session_state.final_queries, indent='\t'), lang="json5", buttons=[{
                    "name": "Save",
                    "feather": "Save",
                    "hasText": True,
                    "commands": ["save-state", ["response","saved"]],
                    "response": "saved",
                    "alwaysOn": True,
                    "style": {"top": "0.46rem", "right": "0.4rem"}
                }])
                if response_dict["type"] == "saved":
                    st.session_state.final_queries = json.loads(response_dict["text"])
        
    
    with col2:
        # If queries exist, enable the chat box for refinement.
        if len(st.session_state.final_queries) > 0:
            st.subheader("Chat: Update/Refine Queries")
            def on_artifact_update(updated_artifact):
                if isinstance(updated_artifact, str):
                    try:
                        st.session_state.final_queries = ast.literal_eval(updated_artifact)
                    except Exception as e:
                        st.error(f"Error parsing updated artifact: {e}")
                else:
                    st.session_state.final_queries = updated_artifact
                st.rerun()

            st.session_state.pop("query_refinement", None)
            chat_box(
                chat_key="query_refinement",
                artifact=str(st.session_state.final_queries),
                initial_prompt="Hi, I can help you refine the queries!",
                placeholder="Ask for changes or additions to the plan",
                use_internet=False,
                rewrite_mode="entire",
                additional_context=None,
                on_artifact_update=on_artifact_update,
                height=500,
            )

    # Button to proceed to the next step (Execute Queries).
    # Disabled if no queries have been generated yet.
    cols = st.columns(4)
    
    with cols[3]:
        submit_button = st.button(
            "✨ Execute Queries", 
            type="primary", 
            use_container_width=True, 
            key="execute_queries_button", 
            disabled=len(st.session_state.final_queries) == 0
        )

    # --- Query Generation Logic ---
    # This block executes if no queries are present and the generation process is triggered.
    if len(st.session_state.final_queries) == 0 and st.session_state.is_generating_queries:
        status.update(label="thinking...", expanded=True, state="running") # Update status to indicate activity
        
        # Call the API to generate queries. This is expected to be a streaming call.
        stream = generate_query(
            topic=st.session_state.topic,
            report_organization=st.session_state.report_structure,
            num_queries=st.session_state.num_queries,
            llm_name=st.session_state.llm_name
        )
        try:
            # Display the streaming output within the status container.
            with status:
                with stylable_container(
                    key="auto-scroll-container",
                    css_styles="""
                        {
                            height: 300px; /* Set desired height */
                            overflow-y: auto;
                            display: flex;
                            flex-direction: column-reverse;
                            padding-bottom: 1em; /* Adjust as needed */
                        }
                        """,
                ):
                    st.write_stream(stream)
                status.update(label="completed!", state="complete") # Mark generation as complete.
            status_placeholder_gq.success("Query generation complete!")
            st.session_state.is_generating_queries = False # Reset flag
            st.rerun() # Rerun to reflect updated final_queries and button state

        except Exception as e:
            status_placeholder_gq.error(f"Error during query streaming: {e}")
            st.error(f"Detailed error: {e}")
            st.session_state.is_generating_queries = False # Reset flag on error
    else:
        # If queries are already generated or not in generation mode, display stored thoughts.
        with status:
            with st.container(height=300, border=False):
                # This implies 'thinking_queries_tokens' was populated during stream
                st.write(st.session_state.thinking_queries_tokens)
            
    if submit_button:
        st.session_state.current_main_step = 2 # Move to step "Execute Queries"
        st.session_state.final_report_content = None
        placeholder.empty()
        st.rerun()