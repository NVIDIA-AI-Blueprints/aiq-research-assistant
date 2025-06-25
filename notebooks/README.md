# AI-Q NVIDIA Research Assistant Blueprint - API Interaction and Deployment Notebooks

## Overview
This repository contains a Jupyter notebook demonstrating the usage of NVIDIA Agent Intelligence Research Assistant (AI-Q Research Assistant) Blueprint APIs.

### Notebook:
- **`get_started_nvidia_api.ipynb`**: Demonstrates how to deploy AI-Q Research Assistant, explore backend APIs, and create reports.


## Setting Up the Environment
To run these notebooks in a Python virtual environment, follow the steps below:

### 1. Create and Activate a Virtual Environment

To run locally, start by [installing the uv python package and project manager](https://docs.astral.sh/uv/getting-started/installation/). 

Next create a virtual environment using Python 3.12:

```bash
uv python install 3.12
uv venv --python 3.12 --python-preference managed
uv pip install -e "./aira"
uv pip install ipykernel jupyter
```

### 2. Start JupyterLab
Start JupyterLab and access from any IP:
```bash
uv run jupyter lab --allow-root --ip=0.0.0.0 --NotebookApp.token='' --port=8889 --no-browser
```

Once running, you can access JupyterLab by navigating to `http://<your-server-ip>:8889` in your browser.

## Running the Notebooks
- Open JupyterLab in your browser.
- Navigate to the desired notebook and run the cells sequentially.

## Deployment (Brev.dev)
For deploying `get_started_nvidia_api.ipynb` in [brev.dev](https://console.brev.dev/environment/new), follow the platform's instructions for executing Jupyter notebooks within a cloud-based environment selected based on the hardware requirements specified in the launchable.

## Notes
- Ensure API keys and credentials are correctly set up before making API requests.
- Modify endpoints or request parameters as necessary to align with your specific use case.
