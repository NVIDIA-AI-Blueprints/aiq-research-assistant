# Data

## Overview 

The AI-Q Research Assistant web demo allows users to test with two default collections:

- Biomedical_Dataset: Scientific journals on the Cystic Fibrosis CFTR gene from 2021-2024
- Financial_Dataset: Financial reports from Apple, Facebook, Google, Meta from 2020-2024

These two collections should be pre-populated. Instructions for adding the default collections are included in the deployment guides and outline below. Users can also create their own collections and upload their own files through the web frontend.

*Note*: The ingestion of the default collections will take 20-30 minutes on most systems.

## Bulk Upload using Docker Compose

Ensure you have followed the [Docker Compose deployment guide](/docs/get-started/get-started-docker-compose.md). Run the command:

```bash
docker run \
  -e RAG_INGEST_URL=http://ingestor-server:8082/v1 \
  -e PYTHONUNBUFFERED=1 \
  -v /tmp:/tmp-data \
  --network nvidia-rag \
  nvcr.io/nvidia/blueprint/aira-load-files:v1.2.0
```

## Bulk Upload via Python 

Set the `RAG_INGEST_URL` environment variable based on your RAG deployment. For example, if running bulk upload on the same node as the RAG ingestion server in Docker Compose deployment:

```bash
export RAG_INGEST_URL="http://localhost:8082"
```

For the Helm deployment, run the following on the node running `kubectl`:
```bash
kubectl port-forward -n rag service/ingestor-server 8082:8082
export RAG_INGEST_URL="http://localhost:8082"
```

On the same node where `RAG_INGEST_URL` was set above, create a Python environment with the correct dependencies:

```bash
uv python install 3.12
uv venv --python 3.12 --python-preference managed
uv run pip install -r data/requirements.txt
```

Copy the zip files you wnat to upload to the current directory:

```bash
cd data
cp files/* .
```

Run the ingest: 

```bash
uv run python zip_to_collection.py
```

## Bulk Uploading Custom Data

You can re-use the utility file here with your own custom dataset. Create a zip file containing the files you wish to upload. The name of the zip file will become the name of the collection. Run the zip_to_collection.py file manually, or build and run a docker image.
