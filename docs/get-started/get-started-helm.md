<!--
  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
  SPDX-License-Identifier: Apache-2.0
-->

# Get Started with AI-Q NVIDIA Research Assistant Blueprint Helm Deployment

This guide provides instructions for deploying the NVIDIA AI-Q Research Assistant blueprint using Helm on a Kubernetes cluster.

## Prerequisites 


1. A NGC API key that is able to access the AI-Q blueprint images. A key can be generated at https://org.ngc.nvidia.com/setup/api-keys. For **Services Included**, select **NGC Catalog** and **Public API Endpoints**.
2. Kubernetes and Helm with [NVIDIA GPU Operator installed](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/getting-started.html#operator-install-guide). This helm chart was tested on [Cloud Native Stack](https://github.com/NVIDIA/cloud-native-stack?tab=readme-ov-file)
3. [Optional] A Tavily API key to support web search.

## Hardware Requirements

The AI-Q Research Assistant blueprint requires the deployment of the NVIDIA RAG blueprint. To deploy both blueprints using Helm requires the following hardware configurations:

| Option | RAG Deployment | AIRA Deployment | Total Hardware Requirement |
|--------|----------------|-----------------|---------------------------|
| Single Node - MIG Sharing | [Use MIG sharing](https://github.com/NVIDIA-AI-Blueprints/rag/blob/main/docs/mig-deployment.md) | [Default Deployment](#deploy-the-ai-q-research-assistant) | 4xH100 80GB for RAG<br/>2xH100 80GB for AIRA<br/>---<br/>6xH100 80GB total |
| Multi Node | [Default Deployment](https://github.com/NVIDIA-AI-Blueprints/rag/blob/main/docs/quickstart.md#deploy-with-helm-chart) | [Default Deployment](#deploy-the-ai-q-research-assistant) | 8xH100 80GB for RAG<br/>2xH100 80GB for AIRA<br/>---<br/>10xH100 80GB total |

> **Note:** Mixed MIG support requires GPU operator 25.3.2 or higher and NVIDIA Driver 570.172.08 or higher.

## Deployment

### Deploy RAG

Follow the [NVIDIA RAG blueprint Helm deployment guide](https://github.com/NVIDIA-AI-Blueprints/rag/blob/main/docs/quickstart.md#deploy-with-helm-chart).

### Deploy the AI-Q Research Assistant

#### Set environment variables

```bash
export NGC_API_KEY="<your-ngc-api-key>"
export TAVILY_API_KEY="<your-tavily-api-key>"
```

#### Clone the repo

```bash
git clone https://github.com/NVIDIA-AI-Blueprints/aiq-research-assistant
```

#### Navigate to the helm chart directory

```bash
cd aiq-research-assistant/deploy/helm
```

#### Create a namespace for AIQ helm chart

```bash
kubectl create namespace aiq
```

#### Deploy the chart

To deploy pre-built chart from NGC:

```bash
helm install aiq-aira https://helm.ngc.nvidia.com/nvidia/blueprint/charts/aiq-aira-v1.2.0.tgz \
--username='$oauthtoken'  \
--password=$NGC_API_KEY \
--set imagePullSecret.password=$NGC_API_KEY \
--set ngcApiSecret.password=$NGC_API_KEY \
--set tavilyApiSecret.password=$TAVILY_API_KEY -n aiq
```

To deploy from source:

```bash
helm install aiq-aira aiq-aira/ \
--set imagePullSecret.password=$NGC_API_KEY \
--set ngcApiSecret.password=$NGC_API_KEY \
--set tavilyApiSecret.password=$TAVILY_API_KEY -n aiq
```

The deployment commands above assume the RAG deployment instructions were followed in [Deploy RAG](#deploy-rag) with the RAG services running in the `rag` namespace. If using a different RAG deployment, the default service URLs can be overridden by setting `backendEnvVars.RAG_SERVER_URL` and `backendEnvVars.RAG_INGEST_URL`. For example:

```bash
helm install aiq-aira aiq-aira/ \
--set imagePullSecret.password=$NGC_API_KEY \
--set ngcApiSecret.password=$NGC_API_KEY \
--set tavilyApiSecret.password=$TAVILY_API_KEY \
--set backendEnvVars.RAG_SERVER_URL=<RAG_SERVER_URL> \
--set backendEnvVars.RAG_INGEST_URL=<INGESTOR_SERVER_URL> -n aiq
```

#### Instruct LLM profile selection

By default, the deployment of the instruct LLM automatically selects the most suitable profile from the list of compatible profiles based on the detected hardware. If you encounter issues with the selected profile or prefer to use a different compatible profile, you can explicitly select the profile by setting `NIM_MODEL_PROFILE` environment variable in the `nim-llm` section of the [values.yaml](../../deploy/helm/aiq-aira/values.yaml). 

You can list available profiles by running the NIM container directly:
```bash
USERID=$(id -u) docker run --rm --gpus all \
  nvcr.io/nim/meta/llama-3.3-70b-instruct:1.13.1 \
  list-model-profiles
```

It is preferrable to select `tensorrt_llm-*` profiles for best performance. Here is an example of selecting one of these profiles for two H100 GPUs:
```
env:
 - name: NIM_MODEL_PROFILE
   value: "tensorrt_llm-h100-fp8-tp2-pp1-throughput-2330:10de-82333b6cf4e6ddb46f05152040efbb27a645725012d327230367b0c941c58954-4"
```
More information about model profile selection can be found [here](https://docs.nvidia.com/nim/large-language-models/latest/profiles.html#profile-selection) in the NVIDIA NIM for Large Language Models (LLMs) documentation.

#### Check status of pods
```bash
kubectl get pods -n aiq
```

Response should look like this:
```
NAME                                      READY   STATUS             RESTARTS       AGE
aiq-aira-aira-backend-5797589756-td5b2    1/1     Running            0              5m
aiq-aira-aira-frontend-74ff7cc5c8-wf9jx   1/1     Running            0              5m
aiq-aira-nim-llm-0                        1/1     Running            0              5m
aiq-aira-phoenix-78fd7584b7-s9bwc         1/1     Running            0              5m
```

#### Access to UI

Since the frontend service has a `nodePort` configured for port 30080, you can view the UI from a web browser on the host running `kubectl` at http://localhost:30080.

The UI can also be viewed from outside the cluster at: `http://<cluster-node-name-or-ip>:30080`


## Create Default Collections

The AI-Q NVIDIA Research Assistant demo web application requires two default collections. One collection supports a biomedical research prompt and contains reports on Cystic Fibrosis. The second supports a financial research prompt and contains public financial documents from Alphabet, Meta, and Amazon.

Follow the steps in [Bulk Upload via Python](../../data/readme.md#bulk-upload-via-python) to create these default collections.

## Stopping Services

To stop all services, run the following commands:

1. Delete the AIRA deployment:
```bash
helm delete aiq-aira -n aiq
```

2. Delete the RAG deployment:
```bash
helm delete rag -n rag
```

3. Delete the namespaces:
```bash
kubectl delete namespace aiq
kubectl delete namespace rag
```
