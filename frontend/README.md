# AI Research Assistant Customizable Frontend

The `frontend` directory includes code for a Python streamlit application that can be used as a starting point for creating a custom web frontend for the AI Research Assistant. 

This document outlines the structure of the frontend code, instructions for getting started with local development, and steps to deploy the frontend.

*Note*: The blueprint also includes a fully functional pre-built demo web application. This web application is provided as a pre-built Docker container only. This folder does NOT contain the source code for the pre-built demo web application. 

## Project Structure

```
frontend2/
├── app.py                     # Main Streamlit application script
├── steps/                     # Modules for UI and logic of distinct application steps
│   ├── __init__.py            # Package initializer for steps
│   ├── input_step.py          # Step 1: Report Input
│   ├── generate_queries_step.py # Step 2: Generate Queries
│   ├── execute_queries_step.py  # Step 3: Execute Queries (generates draft)
│   └── final_report_step.py     # Step 4: Final Report Viewing
├── components/                # Reusable UI components
│   └── chat.py                # Chat component for user interaction
├── utils/                     # Utility functions
│   └── api_calls.py           # Backend API communication functions
├── .env.example               # Example environment variables file
└── README.md                  # This file
```

### Key Components:

-   **`app.py`**: Main application script; handles page config, session state, navigation, and step orchestration.
-   **`steps/`**: Contains modules for each step of the report generation workflow (input, query generation, execution, final report viewing).
-   **`components/`**: Houses reusable UI elements like the `chat.py` component.
-   **`utils/`**: Includes helper modules, notably `api_calls.py` for all backend interactions.

### How it Works

The application guides the user through a multi-step process to generate a research report:
1.  **Input**: The user specifies the report parameters.
2.  **Generate Queries**: The system generates a set of queries based on the input to gather information.
The user can refine these queries.
3.  **Execute Queries**: The queries are run, and an initial draft/summary is generated.
4.  **Final Report**: The user views the finalized report, can ask questions about it, make edits via chat, and download it.

See the [API endpoint documentation](/docs/get-started-api.md) for details on the backend APIs called in each step.

## Running the Application

To run locally, start by [installing the uv python package and project manager](https://docs.astral.sh/uv/getting-started/installation/). 

Next create a virtual environment using Python 3.12:

```
cd frontend
uv python install 3.12
uv venv --python 3.12 --python-preference managed
uv pip install -r requirements.txt
```

Set the necessary environment variables:

```
RAG_INGEST_URL=http://localhost:8082 # Replace with your RAG ingestion service address
AIRA_BASE_URL=http://localhost:3838 # Replace with your AIRA backend service address
```

Run the frontend: 

```
uv run streamlit run app.py  --server.port=3003  --server.address=0.0.0.0
```

Access the application in your web browser at `http://localhost:3000`

## Deployment

To deploy the custom frontend using Docker Compose, uncomment the `aira-custom-frontend` section in `/deploy/compose/docker-compose.yaml`: 

```
  aira-frontend-custom:
     container_name: aira-frontend-custom
     build:
       context: ../../frontend
       dockerfile: Dockerfile
     ports:
       - "3003:3003"
     expose:
       - "3003"
     environment:
       - RAG_INGEST_URL=${RAG_INGEST_URL:-http://ingestor-server:8082}
       - AIRA_BASE_URL=${AIRA_BASE_URL:-http://aira-backend:3838}
     profiles: ["aira"]
     networks:
       - nvidia-rag
```

Follow the instructions in the [Docker Compose deployment guide](/docs/get-started/get-started-docker-compose.md).

