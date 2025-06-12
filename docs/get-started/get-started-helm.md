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
- Deploy the [NVIDIA RAG blueprint](https://github.com/NVIDIA-AI-Blueprints/rag/blob/main/docs/quickstart.md#deploy-with-helm-chart). This blueprint requires NVIDIA NIM microservices that are either running on-premise or hosted by NVIDIA. For a full on-premise deployment, 8xH100 or 8xA100 GPUs are required.  
- Access to a Llama 3.3 Nemotron Super 49B with an associated API key, or a RAG deployment that includes a local Nemotron Super 49B NIM.
- Access to a Llama 3.3 Instruct 70B model with an associated API key. **Note, by default a helm RAG deployment will use all 8 GPUs, and so it is not possible to run the instruct model on the same server. You MUST either deploy the instruct model on a separate server or use a hosted NVIDIA NIM endpoint. In either case, be sure to follow the instructions below to update the AIRA configuration with the appropriate base URL for the instruct model**.  
- Kubernetes and Helm with [NVIDIA GPU Operator installed](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/getting-started.html#operator-install-guide)
- [Optional] A Tavily API key to support web search.


## Deployment

### Deploy RAG

Follow the [NVIDIA RAG blueprint deployment guide](https://github.com/NVIDIA-AI-Blueprints/rag/blob/main/docs/quickstart.md#deploy-with-helm-chart) to deploy the RAG blueprint. **The configuration of the AI-Q Research Assistant assumes you have deployed RAG with the default settings into the `rag` namespace.**

### Configure your `my-values.yaml`

The `values.yaml` file is located at `deploy/helm/aiq-aira/values.yaml`. Create a copy of this file called `my-values.yaml` and update the configuration sections according to your environment. 

- Update the `imagePullSecret.password` with your NGC API key
- Update `tavily_api_key` with your Tavily API key if you want to enable web search

**Using a build endpoint**

If you want to use a NVIDIA build endpoint for the Llama 3.3 70B Instruct model:

- Update the value `instruct_api_key` with your NVIDIA API key 

**Using a separate NIM**

If you want to locally host the Llama 3.3 70B Instruct model:

- Deploy the model on a *separate server* following the [NIM deployment guides](https://docs.nvidia.com/nim/large-language-models/latest/deployment-guide.html)
- Update the value `instruct_base_url` to the base url for your deployed NIM


**Other options**

The following configuration values have appropriate defaults, but may require updates depending on your Kubernetes provider or desired deployment.

- In the section `config`, update:
  - [ ] `instruct_model_name`: the model to use for general purpose Q&A, default is meta/llama-3.3-70b-instruct
  - [ ] `nemotron_model_name`: the model to use for reasoning, default is `nvidia/llama-3.3-nemotron-super-49b-v1` 
  - [ ] `nemotron_base_url`: the base url for the nemotron model, default is to use a RAG deployment local NIM
  - [ ] `nemotron_api_key`: the api key for the nemotron model, not needed if using a local NIM
  - [ ] `rag_ingest_url`: the full address to the RAG ingest-server, default is to use the RAG local service address 
  - [ ] `rag_url`: the full address to the rag-server,  default is to use the RAG local service address 

- In the nginx configuration section, the following values are used to direct traffic to the AI research assistant backend and RAG backend.

  ```
    ... 
    proxy_pass http://ingestor-server.rag.svc.cluster.local:8082
    ...
    proxy_pass http://aira-aira-backend.aira.svc.cluster.local:3838
    ....
  ```
  
  These values are correct if you have deployed the RAG service using helm onto the same Kubernetes cluster, and your cluster supports local DNS resolution. If you deployed RAG differently, or your cluster does not support local DNS, update the RAG ingestion service and the AIRA backend service URLs. Include the entirety of the nginx configuration in your values.yaml file, but make updates to these specific lines:

  Update each occurence of `ingestor-server.rag.svc.cluster.local:8082` to the IP address and port of the RAG ingestor server. This address must be DNS resolvable by the nginx proxy.

  Update each occurence of `aira-aira-backend.aira.svc.cluster.local:3838` to the IP address and port that the AIRA backend server will have after your deployment is complete. This address must be DNS resolvable by the nginx proxy.


- Similarly, the default value of the configuration `frontend.proxyURL` is `http://aira-nginx.aira.svc.cluster.local:8051` which is the local DNS address of the backend proxy used to configure the frontend service. In most cases you do not need to update this value. However, if your cluster does not support local DNS resolution, update the value the IP address and port of the AIRA nginx proxy service.


### Create default collections

The AI research assistant demo web application requires two default collections. One collection supports a biomedical research prompt and contains reports on Cystic Fibrosis. The second supports a financial research prompt and contains public financial documents from Alphabet, Meta, and Amazon. To include these default collections in your deployment, include this section in your custom values file:


```
loadFiles:
  enabled: true
  image:
    repository: nvcr.io/nvstaging/blueprint/aira-load-files
    tag: v1.0.0
    pullPolicy: IfNotPresent
```

**When this job is enabled, it will begin a file upload process during deployment that could take upwards of 60 minutes. During this period, manual file uploads through the AIRA frontend may not work.**

### Enable Phoenix Tracing

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

### Deploy 

Create a namespace:

```bash
kubectl create namespace aira
```

Deploy the chart:

```bash
helm install aira -n aira deploy/helm/aiq-aira -f deploy/helm/aiq-aira/my-values.yaml
```

To make the frontend available you will want to add a node port, for example: 

```bash
kubectl patch svc aira-aira-frontend -n aira -p '{"spec": {"type": "NodePort", "ports": [{"name": "http", "port": 3001, "nodePort": 30001}]}}'
```

If you have enabled phoenix tracing, add a node port for the phoenix service as well:

```bash
kubectl patch svc aira-phoenix -n aira -p '{"spec": {"type": "NodePort", "ports": [{"port": 6006, "nodePort": 30006}]}}
```


## Stopping Services

To stop all services, run the following commands:

1. Delete the AIRA deployment:
```bash
helm uninstall aira -n aira
```

2. Delete the RAG deployment:
```bash
helm uninstall rag -n rag
```

3. Delete the namespaces:
```bash
kubectl delete namespace aira
kubectl delete namespace rag
```
