# Get Started with NVIDIA AI Workbench 

The AI-Q NVIDIA Research Assistant Blueprint allows you to create a deep research assistant that can run on-premise, allowing anyone to create detailed research reports using on-premise data and web search. 

> **Note**
> This Blueprint runs in [NVIDIA AI Workbench](https://docs.nvidia.com/ai-workbench/user-guide/latest/overview/introduction.html). It is a free, lightweight developer platform that you can run on your own systems to get up and running with complex AI applications and workloads quickly. 

> You may want to [**fork**](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/working-with-forks/fork-a-repo#forking-a-repository) this repository into your own account before proceeding. Otherwise you won't be able to fully push any changes you make because this NVIDIA-owned repository is **read-only**.

*Navigating the README*: [Project Overview](#project-overview) | [Get Started](#get-started) | [Customize](#customization) | [License](#license)

*Other Resources*: [:arrow_down: Download AI Workbench](https://www.nvidia.com/en-us/deep-learning-ai/solutions/data-science/workbench/) | [:book: User Guide](https://docs.nvidia.com/ai-workbench/) |[:open_file_folder: Other Projects](https://docs.nvidia.com/ai-workbench/user-guide/latest/quickstart/example-projects.html) | [:rotating_light: Developer Forum](https://forums.developer.nvidia.com/t/support-workbench-example-blueprint-ai-q-research-assistant/336538)

## Project Overview

The main research agent is written in LangGraph and managed using NVIDIA Agent Intelligence Toolkit (AIQ). The research agent provides a unique deep research capability with these features:

- **Deep Research**: Given a report topic and desired report structure, an agent will do the following:
  1. Create a report plan
  2. Search data sources for answers
  3. Write a report
  4. Reflect on gaps in the report for further queries
  5. Complete a report with a list of sources

- **Parallel Search**: During the research phase, multiple research questions are searched in parallel. For each query, the RAG service is consulted and an LLM-as-a-judge is used to check the relevancy of the results. If more information is needed, a fallback web search is performed. This search approach ensures internal documents are given preference over generic web results while maintaining accuracy. Performing query search in parallel allows for many data sources to be consulted in an efficient manner.
- **Human-in-the-loop**: Human feedback on the report plan, interactive report edits, and Q&A with the final report.
- **Data Sources**: Integration with the NVIDIA RAG blueprint to search multimodal documents with text, charts, and tables. Optional web search through Tavily.
- **Demo Web Application**: Frontend web application showcasing end-to-end use of the AI-Q Research Assistant.

[Read More](../../README.md)

## Start Using the Deep Research Agent With NVIDIA AI Workbench

Ensure you meet the prerequisites for this Blueprint ([details](../../README.md)). 

Before you begin, run the  [RAG Blueprint](https://github.com/NVIDIA-AI-Blueprints/rag). This deep researcher will wrap around your RAG pipeline. 

1. Open NVIDIA AI Workbench. Select a **Location** to work in.

1. **Clone** the project using the repository URL: https://github.com/NVIDIA-AI-Blueprints/aiq-research-assistant. 

1. On the **Project Dashboard**, resolve the yellow unconfigured secrets warning:

   * ``NVIDIA_API_KEY``: NVIDIA API Key generated from build.nvidia.com or NGC (starts with "nvapi-")
   * ``TAVILY_API_KEY``: Tavily API Key for web search tool calling (starts with "tvly-")
   * ``RAG_INGEST_URL``: Accessible location of running RAG Blueprint, eg. 10.123.45.678

1. On the **Project Dashboard**, select the ``aira-no-gpu`` compose profile from the dropdown under the **Compose** section.

   * Alternatively, select the ``aira-gpu`` option to start an additional LLM NIM for report generation; 2x GPUs required.
   * (Optional) Select ``load-default-files`` to upload the default documents into the database.

1. On the **Project Dashboard**, select **Start** under the **Compose** section. The compose services may take several minutes to pull and build.

1. When the compose services are ready, you can access the frontend on the IP address, eg. ``http://<ip_addr>:3001``.

   * If ``ERR_CONNECTION_REFUSED``, try restarting the frontend container: **Environment** > **Compose** > **aira-frontend** > **restart**.

1. You can now interact with the deep research agent through its browser interface.

## Customization

There are many ways you can customize the blueprint, including the following:

* Use on-prem NIMs vs. cloud-hosted models
* Swap models names or endpoints
* Adjust default report organization prompts

To customize this blueprint, adjust the config files under ``aira/configs/`` in a code editor and save your changes. Note that ``config.yml`` refers to local deployment configurations and ``hosted-config.yml`` refers to deployments using NVIDIA-hosted model endpoints. 

When restarting the compose, any configuration changes you make will take effect. 

## License

This project will download and install additional third-party open source software projects. Review the license terms of these open source projects before use, found in [License-3rd-party.txt](../../LICENSE-3rd-party.txt). 

GOVERNING TERMS: The software and materials are governed by [NVIDIA Software License Agreement](https://www.nvidia.com/en-us/agreements/enterprise-software/nvidia-software-license-agreement/) and [Product Specific Terms for AI Product](https://www.nvidia.com/en-us/agreements/enterprise-software/product-specific-terms-for-ai-products/); except as follows: (a) the models, other than the Llama-3.3-Nemotron-Super-49B-v1 model, are governed by the [NVIDIA Community Model License](https://www.nvidia.com/en-us/agreements/enterprise-software/nvidia-community-models-license/); (b) the Llama-3.3-Nemotron-Super-49B-v1 model is governed by the [NVIDIA Open Model License Agreement](https://developer.download.nvidia.com/licenses/nvidia-open-model-license-agreement-june-2024.pdf), and (c) the NeMo Retriever extraction is released under the [Apache-2.0 license](https://github.com/NVIDIA/nv-ingest/blob/main/LICENSE).

ADDITIONAL INFORMATION: For NVIDIA Retrieval QA Llama 3.2 1B Reranking v2 model, NeMo Retriever Graphic Elements v1 model, and NVIDIA Retrieval QA Llama 3.2 1B Embedding v2: [Llama 3.2 Community License Agreement](https://www.llama.com/llama3_2/license/), Built with Llama. For Llama-3.3-70b-Instruct model, [Llama 3.3 Community License Agreement](https://www.llama.com/llama3_3/license/), Built with Llama.
