# NVIDIA AI Research Assistant Deployment with Helm

This guide provides instructions for deploying the NVIDIA AI-Q Research Assistant blueprint using Helm on a Kubernetes cluster.

## Components

The system includes the following components:

- AI-Q Research Assistant Backend
- AI-Q Demo Frontend
- NGINX Proxy

*Note*: The demo frontend is provided as a pre-built docker container containing a fully functional web application. The source code for this web application is not distributed.

## Prerequisites

- A NGC API key that is able to access the AI-Q blueprint images.  
- Kubernetes and Helm with [NVIDIA GPU Operator installed](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/getting-started.html#operator-install-guide)
- [Optional] A Tavily API key to support web search.

## Deployment

### Deploy RAG

The [NVIDIA RAG blueprint Helm deployment guide](https://github.com/NVIDIA-AI-Blueprints/rag/blob/main/docs/quickstart.md#deploy-with-helm-chart) provides a few options for deploying the RAG blueprint. *How you deploy the RAG blueprint will impact how you deploy the AI-Q research assistant blueprint*. 

The following table provides the main alternatives:

Hardware | RAG Deployment | AIRA Deployment
--- | --- | ---
1 GPU | [Use Hosted NIM Microservices](https://github.com/NVIDIA-AI-Blueprints/rag/blob/main/docs/quickstart.md#start-using-nvidia-hosted-models) | [Configure for Hosted NIM Microservices](#deploying-with-nvidia-hosted-build-endpoints)
8x GPU | [Use MIG sharing](https://github.com/NVIDIA-AI-Blueprints/rag/blob/main/docs/mig-deployment.md) | [Default Deployment](#deploy-the-ai-q-research-assistant) 
Multi-node 8x GPU system (total of at least 10 GPUs) | [Default Deployment](https://github.com/NVIDIA-AI-Blueprints/rag/blob/main/docs/quickstart.md#deploy-with-helm-chart) | [Default Deployment](#deploy-the-ai-q-research-assistant)


### Deploy the AI-Q research assistant

Set environment variables:

```bash
export NGC_API_KEY=nvapi-xxx # your API key
export TAVILY_API_KEY=yyy # your Tavily API key, optional for web search
```

Create a namespace:

```bash
kubectl create namespace aira
```

### Deploy the chart:

```bash
helm upgrade --install aira -n aira https://helm.ngc.nvidia.com/nvidia/blueprint/charts/aiq-aira-v1.1.0.tgz \
  --username='$oauthtoken'  \
  --password=$NGC_API_KEY \
  --set imagePullSecret.password=$NGC_API_KEY \
  --set ngcApiSecret.password=$NGC_API_KEY \
  --set config.tavily_api_key=$TAVILY_API_KEY
```

To make the frontend available, you will want to add a node port, for example: 

```bash
kubectl patch svc aira-aira-frontend -n aira -p '{"spec": {"type": "NodePort", "ports": [{"name": "http", "port": 3001, "nodePort": 30001}]}}'
```

If you have enabled phoenix tracing, add a node port for the phoenix service as well:

```bash
kubectl patch svc aira-phoenix -n aira -p '{"spec": {"type": "NodePort", "ports": [{"port": 6006, "nodePort": 30006}]}}'
```

#### Deploy from source

Update the chart dependencies:

```bash
helm repo add nvidia-nim https://helm.ngc.nvidia.com/nim/nvidia/ --username='$oauthtoken' --password=$NGC_API_KEY
helm repo add nim https://helm.ngc.nvidia.com/nim/ --username='$oauthtoken' --password=$NGC_API_KEY
helm dependency update deploy/helm/aiq-aira
```


Deploy the chart:

```bash
helm upgrade --install aira -n aira deploy/helm/aiq-aira \
  --set imagePullSecret.password=$NGC_API_KEY \
  --set ngcApiSecret.password=$NGC_API_KEY \
  --set config.tavily_api_key=$TAVILY_API_KEY
```

To make the frontend available, you will want to add a node port, for example: 

```bash
kubectl patch svc aira-aira-frontend -n aira -p '{"spec": {"type": "NodePort", "ports": [{"name": "http", "port": 3001, "nodePort": 30001}]}}'
```

If you have enabled phoenix tracing, add a node port for the phoenix service as well:

```bash
kubectl patch svc aira-phoenix -n aira -p '{"spec": {"type": "NodePort", "ports": [{"port": 6006, "nodePort": 30006}]}}'
```


## Optional Configurations

### Create a `my-values.yaml` file

The default `values.yaml` file is located at `deploy/helm/aiq-aira/values.yaml`. Create a copy of this file called `my-values.yaml` and update any configuration sections according to your environment.


### Deploying with NVIDIA hosted build endpoints

Ensure the NVIDIA RAG blueprint has been deployed using hosted endpoints. Then:

- Update the value `config.instruct_api_key` with your NVIDIA API key 
- Update the value `config.nemotron_api_key` with your NVIDIA API key 
- Update the value `config.instruct_base_url` to be `https://integrate.api.nvidia.com/v1`
- Update the value `config.nemotron_base_url` to be `https://integrate.api.nvidia.com/v1`
- Set the value `nim-llm.enabled` to `false`

### Other options

The following configuration values have appropriate defaults, but may require updates depending on your Kubernetes provider or desired deployment.

- In the section `config`, update:
  - [ ] `instruct_model_name`: the model to use for general purpose Q&A, default is `meta/llama-3.3-70b-instruct`
  - [ ] `instruct_base_url`: the model to use for general purpose Q&A, default is a local NIM deployed as part of the AIRA helm chart. If you want to deploy this LLM separately, update this value AND set `nim-llm.enabled` to `false`
  - [ ] `instruct_api_key`: the api key for the instruct model, not needed if using a local NIM
  - [ ] `nemotron_model_name`: the model to use for reasoning, default is `nvidia/llama-3.3-nemotron-super-49b-v1` 
  - [ ] `nemotron_base_url`: the base URL for the nemotron model, default is to use a local NIM deployed as part of the RAG helm chart
  - [ ] `nemotron_api_key`: the API key for the nemotron model, not needed if using a local NIM
  - [ ] `rag_ingest_url`: the full address to the RAG ingest-server, default is to use the RAG local service address 
  - [ ] `rag_url`: the full address to the rag-server, default is to use the RAG local service address 

- In the nginx configuration section, the following values are used to direct traffic to the AI-Q research assistant backend and RAG backend.

  ```
    ... 
    proxy_pass http://ingestor-server.rag.svc.cluster.local:8082
    ...
    proxy_pass http://aira-aira-backend.aira.svc.cluster.local:3838
    ....
  ```
  
  These values are correct if you have deployed the RAG service using helm onto the same Kubernetes cluster, and your cluster supports local DNS resolution. If you deployed RAG differently, or your cluster does not support local DNS, update the RAG ingestion service and the AIRA backend service URLs. Include the entirety of the nginx configuration in your values.yaml file, but make updates to these specific lines:

  Update each occurrence of `ingestor-server.rag.svc.cluster.local:8082` to the IP address and port of the RAG ingestor server. This address must be DNS resolvable by the nginx proxy.

  Update each occurrence of `aira-aira-backend.aira.svc.cluster.local:3838` to the IP address and port that the AIRA backend server will have after your deployment is complete. This address must be DNS resolvable by the nginx proxy.


- Similarly, the default value of the configuration `frontend.proxyURL` is `http://aira-nginx.aira.svc.cluster.local:8051` which is the local DNS address of the backend proxy used to configure the frontend service. In most cases you do not need to update this value. However, if your cluster does not support local DNS resolution, update the value to the IP address and port of the AIRA nginx proxy service.


## Create default collections

The AI research assistant demo web application requires two default collections. One collection supports a biomedical research prompt and contains reports on Cystic Fibrosis. The second supports a financial research prompt and contains public financial documents from Alphabet, Meta, and Amazon. To include these default collections in your deployment, include this section in your custom values file:


```
loadFiles:
  enabled: true
  image:
    repository: nvcr.io/nvstaging/blueprint/aira-load-files
    tag: v1.1.0
    pullPolicy: IfNotPresent
```

**When this job is enabled, it will begin a file upload process during deployment that could take upwards of 60 minutes. During this period, manual file uploads through the AIRA frontend may not work.**

## Enable phoenix tracing

The configuration section `phoenix` determines whether or not to deploy and configure a Phoenix service for collecting trace logs.

```
phoenix:
  enabled: true
  image:
    repository: arizephoenix/phoenix
    tag: latest
    pullPolicy: IfNotPresent
  resources:
    limits:
      cpu: 500m
      memory: 512Mi
    requests:
      cpu: 200m
      memory: 256Mi
```

## Stopping Services

To stop all services, run the following commands:

1. Delete the AIRA deployment:
```bash
helm delete aira -n aira
```

2. Delete the RAG deployment:
```bash
helm delete rag -n rag
```

3. Delete the namespaces:
```bash
kubectl delete namespace aira
kubectl delete namespace rag
```
