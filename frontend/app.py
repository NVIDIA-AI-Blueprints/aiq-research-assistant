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
Main Streamlit application file for the AI Research Assistant.

This module orchestrates the user interface and the multi-step process for
generating research reports. It handles page configuration, session state
management, navigation between different report generation stages, and
integrates various UI components and utility functions.

The application follows a step-by-step wizard:
1.  **Input Step**: User provides the research topic and defines the report structure.
2.  **Generate Queries Step**: The system suggests queries based on the input.
3.  **Execute Queries Step (Generate Report)**: Queries are run to gather information
    and the initial report content is generated.
4.  **Final Report Step**: The generated report is displayed for review and potential export.

Session state (`st.session_state`) is used extensively to maintain user input,
application status, and data across different steps and user interactions.
API calls to a backend service are made for tasks like managing data collections,
uploading files, and executing report generation queries.
"""
import streamlit as st
import os
from dotenv import load_dotenv
from utils.api_calls import (
    create_collection, upload_files, list_collections, list_files_in_collection,
    delete_document_from_collection,
)

# Import step renderers from the steps package
from steps import (
    render_input_step,
    render_generate_queries_step,
    render_execute_queries_step,
    render_final_report_step
)

from streamlit_extras.stylable_container import stylable_container

# Load environment variables from .env file, typically used for API keys and base URLs.
load_dotenv()

# --- Page Configuration ---
# Configures the Streamlit page with title, icon, layout, and menu items.
# This should be the first Streamlit command in your script, and it can only be set once.
st.set_page_config(
    page_title="AIQ Research Assistant",
    page_icon="🤖",
    layout="wide", # Use "wide" layout for more content space. "centered" is the default.
    initial_sidebar_state="expanded", # Can be "auto", "expanded", "collapsed".
    menu_items={
        'Get Help': 'mailto:help@example.com', # URL or mailto for the "Get Help" menu item.
        'Report a bug': "mailto:bugs@example.com", # URL or mailto for the "Report a bug" menu item.
        'About': """
        ## AIQ Research Assistant
        Streamlit Frontend for AI-powered research report generation.
        """ # Markdown content for the "About" menu item.
    },
)

# Custom CSS to adjust the sidebar width.
# st.markdown with unsafe_allow_html=True allows injecting raw HTML/CSS.
st.markdown(
    """
    <style>
        section[data-testid="stSidebar"] {
            width: 25% !important; /* Sets the sidebar width to 30% of the viewport. */
        }
    </style>
""",
unsafe_allow_html=True,
)

# --- Application State Initialization ---
# st.session_state is Streamlit's way to store variables that persist across user interactions (reruns).
def init_session_state():
    """
    Initializes or ensures the existence of all necessary session state variables.

    This function is crucial for maintaining the application's state across
    user interactions and page reruns. It sets up default values for variables
    tracking the current step, selected data collections, API configurations,
    cached data, and UI element visibility.

    Key session state variables include:
    - `current_main_step`: Tracks the active step in the report generation wizard.
    - `selected_collection_name`: Stores the name of the currently chosen data collection.
    - `collections_list_cache`: Caches the list of available data collections.
    - `collection_files_cache`: Caches the list of files within each collection.
    - `report_id`: Identifier for the current report being processed.
    - `final_report_content`: Stores the generated report text.
    - `api_base_url`, `api_key`: Configuration for backend API communication.
    """
    # Manages the current step in the multi-step report generation process.
    if 'current_main_step' not in st.session_state:
        st.session_state.current_main_step = 0 # 0: Input, 1: Gen Queries, 2: Exec Queries, 3: Final Report

    # State related to data collections.
    if 'selected_collection_name' not in st.session_state:
        st.session_state.selected_collection_name = None
    if 'collections_list_cache' not in st.session_state: # Caches fetched collections to avoid repeated API calls.
        st.session_state.collections_list_cache = None
    if 'collection_files_cache' not in st.session_state: # Caches files within collections: {collection_name: [files_list]}.
        st.session_state.collection_files_cache = {}
    if 'show_file_viewer_for_selected' not in st.session_state: # Controls visibility of file list for the selected collection.
        st.session_state.show_file_viewer_for_selected = False

    # State for displaying intermediate "thinking" tokens from API streams.
    if 'thinking_summary_tokens' not in st.session_state:
        st.session_state.thinking_summary_tokens = dict()
    if 'thinking_queries_tokens' not in st.session_state:
        st.session_state.thinking_queries_tokens = ""

    # State related to the generated report.
    if 'report_id' not in st.session_state:
        st.session_state.report_id = None # Stores ID of the report being generated/worked on.
    if 'final_report_content' not in st.session_state:
        st.session_state.final_report_content = None # Stores the content of the final generated report.

    # API configuration, loaded from environment variables.
    if 'api_base_url' not in st.session_state:
        st.session_state.api_base_url = os.getenv("API_BASE_URL")
    if 'api_key' not in st.session_state:
        st.session_state.api_key = os.getenv("API_KEY")

    # State for query execution UI.
    if 'current_query_json' not in st.session_state: # Default or current JSON query string for execution.
        st.session_state.current_query_json = "{\n  \"action\": \"summarize_section\",\n  \"parameters\": {\n    \"section_topic\": \"Market Analysis\",\n    \"max_length\": 200\n  }\n}"
    if 'streaming_results' not in st.session_state: # Accumulates results from streaming API calls.
        st.session_state.streaming_results = []
    if 'is_streaming' not in st.session_state: # Flag to indicate if a streaming operation is in progress.
        st.session_state.is_streaming = False

# --- Dialog for Creating Collection ---
@st.dialog("Create New Collection") # Defines a modal dialog for creating a new collection.
def create_collection_dialog():
    """
    Renders a Streamlit dialog for creating a new data collection.

    The dialog prompts the user to enter a name for the new collection.
    Upon submission, it calls the `create_collection` API endpoint.
    If successful, it updates the session state with the new collection,
    invalidates relevant caches, closes the dialog, and triggers a UI rerun.
    Error handling for empty names or API failures is included.
    """
    st.markdown("Enter a name for your new collection.")
    new_collection_name_input = st.text_input("Collection Name:", key="dialog_collection_name_input")
    
    if st.button("Create Collection", key="dialog_create_button"):
        if new_collection_name_input:
            collection_name = create_collection(new_collection_name_input)
            if collection_name: # If creation was successful
                st.session_state.selected_collection_name = new_collection_name_input
                # Invalidate caches and reset dialog/viewer states.
                st.session_state.collections_list_cache = None 
                st.session_state.collection_files_cache.pop(new_collection_name_input, None)
                st.session_state.show_file_viewer_for_selected = False
                st.rerun() # Rerun the script to reflect changes in the UI.
        else:
            st.warning("Please enter a collection name.")

# --- Sidebar Collection Management ---
@st.fragment
def render_collection_management_sidebar():
    """
    Renders the data collection management interface in the Streamlit sidebar.

    This section allows users to:
    - View and select existing data collections.
    - Create new collections via a dialog.
    - View and manage files within the selected collection (view, upload, delete).

    It utilizes caching (`st.session_state.collections_list_cache`,
    `st.session_state.collection_files_cache`) to minimize redundant API calls
    for listing collections and files. User interactions like selecting a
    collection, uploading files, or deleting files trigger API calls and
    UI updates (reruns) to reflect changes.
    """
    st.header("Dataset Collections")
    # Load collections if cache is empty.
    if st.session_state.collections_list_cache is None:
        with st.spinner("Loading collections..."): # Shows a loading spinner during the API call.
            collections = list_collections()
            st.session_state.collections_list_cache = collections if collections else []

    if not st.session_state.collections_list_cache:
        st.caption("No existing collections found. Create one to begin.")
    else:
        # Automatically select the first collection if none is selected and collections exist.
        if not st.session_state.selected_collection_name and st.session_state.collections_list_cache:
            first_collection_data = st.session_state.collections_list_cache[0]
            # API might return 'collection_name' or 'name', handle both.
            st.session_state.selected_collection_name = first_collection_data.get('collection_name', first_collection_data.get('name'))
            st.session_state.show_file_viewer_for_selected = False # Default to not showing files for new selection.

        st.markdown("##### Select a Collection:")
        
        collection_names_display = [] # List for display in radio button.
        actual_collection_names = []  # Corresponding actual names for internal use.
        for coll_data in st.session_state.collections_list_cache:
            name = coll_data.get('collection_name', coll_data.get('name'))
            if name:
                collection_names_display.append(f"{name}") 
                actual_collection_names.append(name)
        
        current_selection_idx = 0
        if st.session_state.selected_collection_name in actual_collection_names:
            current_selection_idx = actual_collection_names.index(st.session_state.selected_collection_name)
        elif actual_collection_names: # If current selection is invalid, default to the first collection.
            st.session_state.selected_collection_name = actual_collection_names[0]
        else: # No collections available.
            st.session_state.selected_collection_name = None

        if actual_collection_names: # Only show radio selection if there are collections.
            # st.radio creates a radio button group for selecting a collection.
            selected_display_name = st.radio(
                "Available Collections:", 
                collection_names_display,
                index=current_selection_idx,
                key="collection_radio_select_main", # Unique key for the widget.
                label_visibility="collapsed" # Hides the label "Available Collections:".
            )
            
            selected_actual_name = actual_collection_names[collection_names_display.index(selected_display_name)]

            # If selection changed, update state and rerun.
            if selected_actual_name != st.session_state.selected_collection_name:
                st.session_state.selected_collection_name = selected_actual_name
                st.session_state.show_file_viewer_for_selected = False # Hide files on new collection selection.
                st.rerun(scope="fragment")
        elif not st.session_state.collections_list_cache:
            pass # "No existing collections found" caption handles this.
        else: 
            st.caption("Error: Could not display collections.") # Should ideally not be reached.

        # Button to toggle visibility of files for the currently selected collection.
        if st.session_state.selected_collection_name:
            sel_col_name = st.session_state.selected_collection_name
            icon_to_display = "✕" if st.session_state.show_file_viewer_for_selected else "🔎"
            button_text = f"{icon_to_display} Hide Files" if st.session_state.show_file_viewer_for_selected else f"{icon_to_display} View Files"
            help_text = f"Hide files for '{sel_col_name}'" if st.session_state.show_file_viewer_for_selected else f"View files for '{sel_col_name}'"
            
            if st.button(button_text, 
                         key=f"toggle_files_btn_for_{sel_col_name.replace(' ', '_')}", # Dynamic key.
                         help=help_text, 
                         use_container_width=True,
                         type="secondary"): # "secondary" gives a less prominent button style.
                st.session_state.show_file_viewer_for_selected = not st.session_state.show_file_viewer_for_selected
                st.rerun(scope="fragment")

    # Button to trigger the "Create New Collection" dialog.
    if st.button("＋ Create New Collection", use_container_width=True, type="secondary"):
        create_collection_dialog()

    # Conditional rendering of file management UI (viewer and uploader).
    if st.session_state.selected_collection_name: 
        collection_name_for_management = st.session_state.selected_collection_name
        
        # File Viewer: Shows files in the selected collection if toggled visible.
        if st.session_state.show_file_viewer_for_selected:
            st.subheader(f"Manage files for '{collection_name_for_management}'")
            # st.status creates an expandable section, here used for the file list.
            with st.status("File List", expanded=True): 
                # Fetch files if not in cache for the selected collection.
                if collection_name_for_management not in st.session_state.collection_files_cache:
                    with st.spinner("Fetching file list..."):
                        files = list_files_in_collection(collection_name_for_management)
                        st.session_state.collection_files_cache[collection_name_for_management] = files if files else []
                
                files_in_selected_collection = st.session_state.collection_files_cache.get(collection_name_for_management, [])
                
                # stylable_container allows applying custom CSS to a block of elements.
                with stylable_container(
                    key="file_list_container",
                    css_styles="""
                        {
                            max-height: 300px; /* Limits height and enables scrolling for long lists. */
                            min-height: 50px; /* Ensures a minimum height even if empty. */
                            overflow-y: auto; /* Enables vertical scrollbar if content exceeds max-height. */
                        }
                        """,
                ):
                    if not files_in_selected_collection:
                        st.caption("No files in this collection.")
                    else:
                        for f_idx, f in enumerate(files_in_selected_collection):
                            # st.columns creates a layout with multiple columns.
                            col1, col2 = st.columns([7, 1]) # Ratio of column widths.
                            with col1:
                                st.markdown(f"- {f.get('document_name', f'File {f_idx+1}')}")
                            with col2:
                                # Button to delete a specific document.
                                if st.button("🗑️", 
                                             key=f"delete_btn_{collection_name_for_management}_{f.get('document_name', f'File {f_idx+1}')}_{f_idx}", 
                                             help=f"Delete '{f.get('document_name', f'File {f_idx+1}')}'", 
                                             use_container_width=True):
                                    delete_document_from_collection(collection_name_for_management, f.get('document_name', f'File {f_idx+1}'))
                                    # Invalidate cache for the modified collection and rerun.
                                    st.session_state.collection_files_cache.pop(collection_name_for_management, None)
                                    st.rerun(scope="fragment")
        # File Uploader: Always visible if a collection is selected, allowing users to add files.
        # st.file_uploader provides a widget for uploading files.
        with st.form(key=f"uploader_form_{collection_name_for_management}", border=False, clear_on_submit=True):
            uploaded_sidebar_files = st.file_uploader(
                f"Upload to '{collection_name_for_management}'",
                accept_multiple_files=True, # Allows selecting multiple files.
            )
            submitted = st.form_submit_button(f"Upload File(s)", 
                use_container_width=True)
            if uploaded_sidebar_files and submitted:
                success = upload_files(collection_name_for_management, uploaded_sidebar_files, blocking=True) # alternative method: blocking=False (non-blocking)
                if success:
                    st.success("Files uploaded successfully.")
                    st.session_state.collection_files_cache.pop(collection_name_for_management, None)
                    st.rerun(scope="fragment")
                else:
                    st.error("Failed to upload files.")

    else: # No collection selected by the user.
        st.caption("Select or create a collection to manage files.")

# --- Main Application Flow ---
def main():
    """
    Main function to structure and run the Streamlit application.

    It performs the following key operations:
    1. Initializes the session state using `init_session_state()`.
    2. Sets up the sidebar, including the application title and the
       collection management UI rendered by `render_collection_management_sidebar()`.
    3. Defines the titles and rendering functions for each step of the
       report generation wizard.
    4. Implements navigation (Previous/Next buttons) and a progress bar
       to guide the user through the steps.
    5. Dynamically renders the content for the current step based on
       `st.session_state.current_main_step`.
    6. Includes logic to enable/disable the "Next" button based on whether
       prerequisites for the current step are met (e.g., topic entered,
       queries generated).
    """
    init_session_state() # Ensure all session state variables are initialized.

    # st.sidebar creates a sidebar panel for navigation or controls.
    with st.sidebar:
        st.title("🤖 AIQ Research Assistant") # Title for the sidebar.
        render_collection_management_sidebar() # Populate sidebar with collection management UI.

    main_step_titles = ["Report Input", "Generate Queries", "Generate Report", "Final Report"]
    current_step_index = st.session_state.current_main_step

    # Apply custom styling to the main step title.
    with stylable_container(
        key="main-step-title",
        css_styles="""
            {
                margin-top: -2rem !important; /* Adjust top margin. */
                margin-bottom: 2rem !important; /* Adjust bottom margin. */
            }
        """,
    ):
        st.markdown(f"### {main_step_titles[current_step_index]}")
        
    # Dictionary mapping step indices to their respective rendering functions.
    step_renderers = {
        0: render_input_step,
        1: render_generate_queries_step,
        2: render_execute_queries_step,
        3: render_final_report_step,
    }
    
    # Navigation buttons (Previous/Next) and progress bar for the multi-step process.
    nav_cols = st.columns([1, 15, 1]) # Layout for prev button, progress bar, next button.
    with nav_cols[0]: # Previous step button.
        if current_step_index > 0:
            if st.button("⬅️", use_container_width=True, key="prev_step_button"):
                st.session_state.current_main_step -= 1
                st.rerun() # Rerun to display the previous step.
    
    with nav_cols[1]: # Progress bar.
        # st.progress displays a progress bar.
        progress_value = (current_step_index) / (len(main_step_titles) - 1)
        st.progress(progress_value, text=f"Step {current_step_index + 1} of {len(main_step_titles)}")
    
    with nav_cols[2]: # Next step button.
        if current_step_index < len(main_step_titles) - 1:
            can_proceed = True # Flag to enable/disable the "Next" button.
            # Prerequisites for proceeding to the next step.
            if current_step_index == 0: # From "Report Input"
                # Topic and report structure must be filled.
                if not st.session_state.get('topic',"").strip() or not st.session_state.get('report_structure',"").strip():
                    can_proceed = False 
            elif current_step_index == 1: # From "Generate Queries"
                 # Final queries must exist.
                if not st.session_state.get('final_queries'):
                    can_proceed = False
            elif current_step_index == 2: # From "Generate Report" (Execute Queries)
                # Final report content must exist.
                if not st.session_state.get('final_report_content'):
                    can_proceed = False
            # The "Final Report" (index 3) is the last step; the "Next" button is not shown.

            if st.button("➡️", use_container_width=True, key="next_step_button", disabled=not can_proceed):
                st.session_state.current_main_step += 1
                st.rerun() # Rerun to display the next step.

    # Render the content for the current main step.
    if current_step_index in step_renderers:
        step_renderers[current_step_index]()
    else:
        st.error("Invalid step detected. Please restart the application or contact support.")

if __name__ == "__main__":
    main() 