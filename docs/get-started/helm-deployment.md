<!--
  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
  SPDX-License-Identifier: Apache-2.0
-->

# Get Started With NVIDIA AIQ helm deployment

## Hardware Requirements

The AIQ blueprint requires 1 or 2 additional GPUs on top of the [RAG blueprint](https://github.com/NVIDIA-AI-Blueprints/rag/blob/v2.2.1/docs/quickstart.md#prerequisites-1) depending on the which report writermodel you choose to use, the default is llama 3.3 70b which requires 2 GPUs.

## Software Requirements

1. This helm chart was tested on [Cloud Native Stack](https://github.com/NVIDIA/cloud-native-stack?tab=readme-ov-file)

2. A NVIDIA API Key
To generate an API key, use the following procedure.

1. Go to https://org.ngc.nvidia.com/setup/api-keys.
2. Click **+ Generate Personal Key**.
3. Enter a **Key Name**.
4. For **Services Included**, select **NGC Catalog** and **Public API Endpoints**.
5. Click **Generate Personal Key**.

After you generate your key, export your key as an environment variable by using the following code.

```bash
export NGC_API_KEY="<your-ngc-api-key>"
```

## Deployment

1. Clone the repo

```bash
git clone https://github.com/NVIDIA-AI-Blueprints/aiq-research-assistant
```

2. Navigate to the helm chart directory

```bash
cd aiq-research-assistant/deploy/helm
```

3. Install the RAG helm chart by following the instructions [here](https://github.com/NVIDIA-AI-Blueprints/rag/blob/v2.2.1/docs/mig-deployment.md)

4. Create a namespace for AIQ helm chart

```bash
kubectl create namespace aiq
```

5. Run the AIQ helm chart

```bash
helm install aiq-aira aiq-aira/ \
--set imagePullSecret.password=$NGC_API_KEY \
--set ngcApiSecret.password=$NGC_API_KEY \
--set tavilyApiSecret.password=<YOUR_TAVILY_API_KEY>
--set backendEnvVars.RAG_SERVER_URL=<RAG_SERVER_URL> \
--set backendEnvVars.RAG_INGEST_URL=<INGESTOR_SERVER_URL> -n aiq
```

You can get the RAG_SERVER_URL and INGESTOR_SERVER_URL by running ```kubectl get svc``` in the namespace where you installed rag. If you installed it in the ```rag``` namespace. The values are typically
```rag-server.rag.svc.cluster.local``` and ```ingestor-server.rag.svc.cluster.local```. 

