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
from utils.api_calls import artifact_qa
from typing import Optional, Any, Callable
import json

def chat_box(
    chat_key: str, 
    artifact: Optional[str] = None,
    initial_prompt: Optional[str] = "Hi, How can I help you?",
    placeholder: str = "Send a message...", 
    use_internet: bool = False,
    rewrite_mode: Optional[str] = None,
    additional_context: Optional[str] = None,
    on_artifact_update: Optional[Callable[[Any], None]] = None,
    height: int = 400
) -> Optional[str]:
    """
    Renders a reusable chat interface component for Streamlit applications.

    This component provides a complete chat experience, including:
    -   Displaying chat history (user and assistant messages).
    -   A text input area for users to send messages.
    -   A button to clear the chat history.
    -   Interaction with a backend API (`artifact_qa`) to get assistant responses.
    -   Optional handling of an 'artifact' (e.g., a document, code, or data structure)
        that the chat can be about, potentially modifying it based on the conversation.

    Args:
        chat_key (str): A unique key to identify this chat instance and store its
            history in `st.session_state`. Essential for having multiple independent
            chat boxes on the same page.
        artifact (Optional[str]): A string representation of an artifact (e.g., JSON
            string, text document) that the Q&A or editing is focused on.
        initial_prompt (Optional[str]): An initial message from the assistant to start
            the conversation. Defaults to "Hi, How can I help you?". If None, no
            initial prompt is shown.
        placeholder (str): Placeholder text for the chat input box.
            Defaults to "Send a message...".
        use_internet (bool): Flag to indicate if the backend `artifact_qa` call
            should be allowed to use internet search. Defaults to False.
        rewrite_mode (Optional[str]): Specifies if/how the artifact should be rewritten
            by the assistant (e.g., "entire", None). Passed to `artifact_qa`.
            Defaults to None.
        additional_context (Optional[str]): Any additional context to be passed to the
            `artifact_qa` API call. Defaults to None.
        on_artifact_update (Optional[Callable[[Any], None]]): A callback function
            that is called when the `artifact_qa` API returns an updated artifact.
            The callback receives the (potentially parsed JSON) updated artifact.
            Defaults to None.
        height (int): The height of the chat message display container in pixels.
            Defaults to 400.

    Returns:
        Optional[str]: Currently, this function always returns `None`. Its primary
            purpose is to render UI and manage chat state through `st.session_state`
            and callbacks.

    Session State Usage:
    -   `st.session_state[chat_key]`: Stores a list of chat messages for this instance.
        Each message is a dictionary with "role" (user/assistant) and "content".
    -   `st.session_state.selected_collection_name`: Used to pass the RAG collection
        name to the `artifact_qa` API call.

    The function handles displaying previous messages, capturing new user input,
    calling the `artifact_qa` backend, displaying the assistant's response, and
    optionally updating the linked artifact if the backend provides an update and
    an `on_artifact_update` callback is supplied.
    """
    # Initialize chat history in session state if it doesn't exist
    if chat_key not in st.session_state:
        st.session_state[chat_key] = []
        # Add initial prompt if provided
        if initial_prompt:
            st.session_state[chat_key].append({"role": "assistant", "content": initial_prompt})

    # --- Display Chat History --- #
    chat_container = st.container(height=height, border=False)
    with chat_container:
        for message in st.session_state[chat_key]:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

    # --- Chat Input and Clear Button --- #
    input_col, button_col = st.columns([8, 1]) # Using columns to place input and button on the same line

    with input_col:
        prompt = st.chat_input(placeholder=placeholder, key=f"{chat_key}_input")

    with button_col:
        if st.button("🧹", key=f"{chat_key}_clear_button", use_container_width=True, help="Clear Chat History"):
            if initial_prompt:
                st.session_state[chat_key] = [{"role": "assistant", "content": initial_prompt}]
            else:
                st.session_state[chat_key] = []
            st.rerun()

    if prompt:
        # Add user message to chat history
        st.session_state[chat_key].append({"role": "user", "content": prompt})

        # Display user message immediately
        with chat_container:
            with st.chat_message("user"):
                st.markdown(prompt)

        # --- Get Assistant Response --- #
        with st.spinner("Assistant is thinking..."):
            history_for_api = [message["content"] for message in st.session_state[chat_key]]

            response = artifact_qa(
                artifact=artifact,
                question=prompt,
                chat_history=history_for_api,
                use_internet=use_internet,
                rewrite_mode=rewrite_mode,
                additional_context=additional_context,
                rag_collection=st.session_state.selected_collection_name
            )
        
        # Display assistant response and add to history
        if response:
            st.session_state[chat_key].append({"role": "assistant", "content": response["assistant_reply"]})
            updated_artifact = response["updated_artifact"]
            if updated_artifact:
                parsed_artifact = None
                if isinstance(updated_artifact, str):
                    try:
                        parsed_artifact = json.loads(updated_artifact)
                    except json.JSONDecodeError:
                        parsed_artifact = updated_artifact
                        st.warning("Received updated_artifact as a string that is not valid JSON. Treating as plain text.")
                else:
                    parsed_artifact = updated_artifact

                if on_artifact_update:
                    on_artifact_update(parsed_artifact)
            st.rerun()
        else:
            st.session_state[chat_key].append({"role": "assistant", "content": "Sorry, I encountered an error."})
            st.rerun()

    return None
