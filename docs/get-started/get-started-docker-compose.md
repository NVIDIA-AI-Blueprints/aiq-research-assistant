# Get Started with AI-Q NVIDIA Research Assistant Blueprint Using Docker Compose

This guide describes how to deploy the AI-Q Research Assistant using Docker.

## Prerequisites 


1. This blueprint depends on the [NVIDIA RAG blueprint](https://github.com/NVIDIA-AI-Blueprints/rag). The deployment guide includes instructions for deploying RAG using docker compose, but please consult the latest RAG documentation as well. The RAG blueprint requires NVIDIA NIM microservices that are either running on-premise or hosted by NVIDIA, including the Nemo Retriever microservices and LLM, by default Llama 3.3 Nemotron Super 49B. For a self-contained local deployment, 2xH100, 3xA100, 3xB200 or 2xRTX PRO 6000 GPUs are required.

2. In addition to the LLM used by RAG, Llama 3.3 Nemotron Super 49B (llama-3_3-nemotron-super-49b-v1_5), the AI-Q Research Assistant also requires access to the Llama 3.3 Instruct 70B (llama-3.3-70b-instruct) model. Deploying this model requires an additional 2xB200, 2xH100 GPUs, 4xA100 GPUs or 2xRTX PRO 6000 GPUs.

3. Docker Compose

4. NVIDIA Container Toolkit

5. (Optional) This blueprint supports Tavily web search to supplement data from RAG. A Tavily API key can be supplied to enable this function. 


### Hardware Requirements

*For a self-contained local deployment*
- 5 B200 GPUs **or** 4 H100 GPUs with 80GB of memory each **or** 7 A100 GPUs with 80GB of memory each **or** 4 RTX PRO 6000 GPUs with 96GB of memory each

*For a deployment using hosted NVIDIA NIM microservices*
No GPUs are required

### NVIDIA NIM Microservices

Access the following NVIDIA NIM microservices 
- NemoRetriever
  - Page Elements
  - Table Structure
  - Graphic Elements
  - Paddle OCR 
- Llama Instruct 3.3 70B
- Llama Nemotron 3.3 Super 49B

## Deployment using on-prem
This section demonstrates how to deploy AI-Q Research Assistant.

### Git clone

Clone the aiq-research-assistant and set it as the working directory:

```bash
git clone https://github.com/NVIDIA-AI-Blueprints/aiq-research-assistant.git
cd aiq-research-assistant
```

### Setup Environment Variables

Start by setting the required environment variables:

```bash
export NVIDIA_API_KEY=nvapi-your-nvidia-api-key
export NGC_API_KEY=$NVIDIA_API_KEY
export TAVILY_API_KEY=your-tavily-api-key
export USERID=$(id -u)
```

Login to the NVIDIA Container Registry:

```bash
echo "${NGC_API_KEY}" | docker login nvcr.io -u '$oauthtoken' --password-stdin
```

Create a model cache directory:

```bash
mkdir -p ~/.cache/model-cache
export MODEL_DIRECTORY=~/.cache/model-cache
```

### Deploy RAG

Before deploying the AI-Q Research Assistant, deploy RAG by following [these instructions](https://github.com/NVIDIA-AI-Blueprints/rag/blob/main/docs/deploy-docker-self-hosted.md).

```bash
git clone https://github.com/NVIDIA-AI-Blueprints/rag.git
```

Open the file `rag/deploy/compose/.env` and confirm that all of the values in the section `# ==== Endpoints for using cloud NIMs ===` are commented out. Then source this file:


```bash
source rag/deploy/compose/.env
```

Deploy the RAG NVIDIA NIM microservices, including the LLM. *This step can take up to 45 minutes*.

```bash
docker compose -f rag/deploy/compose/nims.yaml up -d
```

For A100/B200 system, run the following commands

```bash
export LLM_MS_GPU_ID=1,2

docker compose -f rag/deploy/compose/nims.yaml up -d
```

TIP: You can watch the status with `watch -n 2 'docker ps --format "table {{.Names}}\t{{.Status}}"'`. 

To confirm that the deployment is successful, run `docker ps --format "table {{.Names}}\t{{.Status}}"`, you should see: 

```
   NAMES                                   STATUS

   nemoretriever-ranking-ms                Up 14 minutes (healthy)
   compose-page-elements-1                 Up 14 minutes
   compose-paddle-1                        Up 14 minutes
   compose-graphic-elements-1              Up 14 minutes
   compose-table-structure-1               Up 14 minutes
   nemoretriever-embedding-ms              Up 14 minutes (healthy)
   nim-llm-ms                              Up 14 minutes (healthy)
```

Deploy the Vector DB:

```bash
export VECTORSTORE_GPU_DEVICE_ID=0

docker compose -f rag/deploy/compose/vectordb.yaml up -d
```

To confirm that the deployment was successful, run `docker ps --format "table {{.Names}}\t{{.Status}}"`. In addition to the previously running containers, you should see: 

```
milvus-standalone                Up 2 minutes
milvus-minio                     Up 2 minutes (healthy)
milvus-etcd                      Up 2 minutes (healthy)
```

Deploy the ingestion server:

```bash
docker compose -f rag/deploy/compose/docker-compose-ingestor-server.yaml up -d
```

To confirm that the deployment was successful, run `docker ps --format "table {{.Names}}\t{{.Status}}"`. In addition to the previously running containers, you should see: 

```
compose-redis-1                  Up 3 minutes
compose-nv-ingest-ms-runtime-1   Up 3 minutes (healthy)
ingestor-server                  Up 3 minutes
```

Deploy the RAG server:

```bash
docker compose -f rag/deploy/compose/docker-compose-rag-server.yaml up -d
```

To confirm that the deployment was successful, run `docker ps --format "table {{.Names}}\t{{.Status}}"`. In addition to the previously running containers, you should see: 

```
rag-frontend                     Up 4 minutes
rag-server                       Up 4 minutes
```

### Deploy the instruct model

Next deploy the instruct model. *This step can take up to 45 minutes*.

#### Model profile selection

By default, the deployment of the instruct LLM attempts to automatically select the most suitable profile from the list of compatible profiles based on the detected hardware. Because of a known issue, vllm-based profiles are selected, so we recommend that you manually select a tensorrt_llm profile before you start the nim-llm service. 

You can list available profiles by running the NIM container directly:
```bash
USERID=$(id -u) docker run --rm --gpus all \
  nvcr.io/nim/meta/llama-3.3-70b-instruct:1.13.1 \
  list-model-profiles
```

Using the list of model profiles from the previous step, set the NIM_MODEL_PROFILE. It is ideal to select one of the tensorrt_llm profiles for best performance. Here is an example of selecting one of these profiles for two H100 GPUs:

```bash
export NIM_MODEL_PROFILE="tensorrt_llm-h100-fp8-tp2-pp1-throughput-2330:10de-bedaf1e0ba87272295f4fcb590e781436120751026098f448fd8bc4d711ba5d7-4"
```

#### Hardware-Specific Profiles

The following tensorrt_llm profiles are optimized for different common GPU configurations:

##### 2xH100 NVL
```
tensorrt_llm-h100_nvl-fp8-tp2-pp1-throughput-2321:10de-5e20634213cb4c32e86f048dbc274eb8bff74720af81fe400d8924e766f3e723-4
```

##### 2xH100 SXM
```
tensorrt_llm-h100-fp8-tp2-pp1-throughput-2330:10de-bedaf1e0ba87272295f4fcb590e781436120751026098f448fd8bc4d711ba5d7-4
```

##### 4xA100
```
tensorrt_llm-a100-bf16-tp4-pp1-throughput-20b2:10de-8dfffd86cd28a6ea7086f8d3d33f0d60c66df738652cea44c722766b77508b5c-4
```

##### 2xRTX PRO 6000
```
tensorrt_llm-rtx6000_blackwell_sv-nvfp4-tp2-pp1-latency-2bb5:10de-b5d32ce12a99b422e2c5a9a772bfd29493467cd5f22248ed936e2d43c5747771-2
```

##### 2xB200
```
tensorrt_llm-b200-bf16-tp2-pp1-latency-2901:10de-d89dfd90f9f326864bc6051f45b5aca8e758fdb009b1da43d93b1d5a2236026e-2
```

More information about model profile selection can be found [here](https://docs.nvidia.com/nim/large-language-models/latest/profiles.html#profile-selection) in the NVIDIA NIM for Large Language Models (LLMs) documentation.

#### Deploy the Model

```bash
docker compose -f deploy/compose/docker-compose.yaml --profile aira-instruct-llm up -d
```

For A100/B200 system, run the following commands 

```bash
export AIRA_LLM_MS_GPU_ID=3,4,5,6

docker compose -f deploy/compose/docker-compose.yaml --profile aira-instruct-llm up -d
```

TIP: you can watch the status with `watch -n 2 'docker ps --format "table {{.Names}}\t{{.Status}}"'`. 

To confirm that the deployment was successful, run `docker ps --format "table {{.Names}}\t{{.Status}}"`. In addition to the previously running containers, you should see:

```
aira-instruct-llm                Up 5 minutes (healthy)
```

### Deploy the AI-Q Research Assistant

This step deploys the AIRA backend, AIRA proxy, and the pre-built AIRA demo frontend. The AIRA demo frontend is provided as a pre-built docker container containing a fully functional web application. The source code for this web application is not distributed.

```bash
docker compose -f deploy/compose/docker-compose.yaml --profile aira up -d
```

To confirm that the deployment was successful, run `docker ps --format "table {{.Names}}\t{{.Status}}"`. In addition to the previously running containers, you should see:

```
aira-frontend                    Up 2 minutes
aira-backend                     Up 2 minutes
```

You can then view the web UI at:

```
localhost:3000
```

The backend will be running and visible at:

```
localhost:3838/docs
```

### Add Default Collections

The AI-Q Research Assistant demo web application requires two default collections. One collection supports a biomedical research prompt and contains reports on Cystic Fibrosis. The second supports a financial research prompt and contains public financial documents from Alphabet, Meta, and Amazon. To pre-populate RAG with these two collections, run:

```bash
docker run \
  -e RAG_INGEST_URL=http://ingestor-server:8082/v1 \
  -e PYTHONUNBUFFERED=1 \
  -v /tmp:/tmp-data \
  --network nvidia-rag \
  nvcr.io/nvidia/blueprint/aira-load-files:v1.2.0
```

This command will populate the default collections with sample documents. Note that this process can take up to 60 minutes to complete, during which time manual uploads from the frontend may not work properly.

Troubleshooting tips if the default collection creation fails: 


1. If you did not deploy RAG via docker compose, you will need to replace these values in the docker run command above:
  - `http://ingestor-server:8082/v1`: replace with your RAG ingestor server address
  - remove the line `--network nvidia-rag`

2. If you get an error that the zip file is not a valid zip file

  Install git LFS for your platform, eg `sudo apt-get install git-lfs` and then run: 

  ```bash
  git lfs install
  git lfs pull
  ```

### Stopping all services

To stop all services, run the following commands in order:

1. Stop the AI-Q Research Assistant services:
```bash
docker compose -f deploy/compose/docker-compose.yaml --profile aira down
```

2. Stop the instruct model:
```bash
docker compose -f deploy/compose/docker-compose.yaml --profile aira-instruct-llm down
```

3. Stop the RAG services:
```bash
docker compose -f rag/deploy/compose/docker-compose-rag-server.yaml down
docker compose -f rag/deploy/compose/docker-compose-ingestor-server.yaml down
docker compose -f rag/deploy/compose/vectordb.yaml down
docker compose -f rag/deploy/compose/nims.yaml down
```

4. Remove the cache directories used by the RAG vector database and minio service:
```bash
rm -rf rag/deploy/compose/volumes/minio
```

Tip: If you retain these directories, the collections you created will remain the next time you start the services.

To verify all services have been stopped, run:
```bash
docker ps
```


## Deployment - Hosted Models or Remote RAG Deployment

### Deploy RAG

> If you already have RAG deployed, skip to the next step.

To deploy using hosted NVIDIA NIM microservices, follow the instructions for [deploying the RAG blueprint using hosted models](https://github.com/NVIDIA-AI-Blueprints/rag/blob/main/docs/deploy-docker-nvidia-hosted.md). 

### Update AI-Q Research Assistant Configuration 

Edit the *AI-Q configuration file* located at `configs/config.yml`. 

Update the following values, leaving the rest of the file with the default values.

  - [ ] `llms.instruct_llm.api_key`: enter a NVIDIA API Key with access to required NVIDIA NIM microservices. Optional: update the model base_url and model_name if a different model is desired, such as an on-premise NVIDIA NIM microservice. The `instruct_llm` LLM is used for Q&A and report generation. An instruct model is recommended.

  - [ ] `llms.instruct_llm.base_url`: update to https://integrate.api.nvidia.com/v1

  - [ ] `llms.nemotron.api_key`: enter a NVIDIA API Key with access to required NVIDIA NIM microservices. Optional: update the model base_url and model_name if a different model is desired, such as an on-premise NVIDIA NIM microservice. The `instruct_llm` LLM is used for report planning and reflection. A reasoning model is recommended.

  - [ ] `llms.nemotron.base_url`: update to https://integrate.api.nvidia.com/v1

  - [ ] In the `functions` section, update `functions.generate_summary.rag_url` with the full public IP address and port for the `rag-server` from the RAG deployment. This step is only required if you have deployed RAG on a separate server. If you have deployed RAG using docker compose on the same server as AIRA, leave the default value.

  - [ ] In the `functions` section, update `functions.artifact_qa.rag_url` with the full public IP address and port for the `rag-server` from the deployment. This step is only required if you have deployed RAG on a separate server. If you have deployed RAG using docker compose on the same server as AIRA, leave the default value.

Edit the *Docker Compose file* located at `deploy/compose/docker-compose.yaml`.

  - [ ] Update the value `services.aira-backend.environment.TAVILY_API_KEY` with your TAVILY API Key
  - [ ] If you have deployed RAG on a different server than AIRA, update the value `services.aira-backend.environment.RAG_INGEST_URL` with the *public http IP address of the RAG ingestor service* such as `http://UPDATE-TO-YOUR-RAG-IP-SERVER:8082`. If you have deployed RAG using docker compose on the same server as AIRA, leave the default value.
  
  > **WARNING:** The rag ingest IP address must be resolvable outside the docker network, so addresses such as `localhost` or `rag-server` will not work. Currently only http addresses are supported. HTTPS rag deployments, or authenticated RAG deployments, will require updates to the NGINX proxy.


### Deploy AI-Q Research Assistant

```bash
# Uncomment and run this command if you have deployed RAG on a different server
# docker network create nvidia-rag
docker compose -f deploy/compose/docker-compose.yaml --profile aira up -d
```

## Troubleshooting

If you encounter any issues during deployment or operation, please refer to the comprehensive [Troubleshooting Guide](../troubleshooting.md) for detailed solutions and debugging steps.

## Optional: Tracing Using Phoenix

For detailed instructions on setting up Phoenix dashboard for OpenTelemetry tracing, please refer to [Phoenix Tracing Configuration](../phoenix-tracing.md).