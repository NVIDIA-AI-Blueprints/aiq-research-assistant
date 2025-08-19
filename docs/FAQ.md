# Frequently Asked Questions

This document contains frequently asked questions that are not covered in the deployment or troubleshooting guides.


## How Many Files can I Upload? Can I Bulk Upload Files?

The demo web application allows you to upload 10 files at a time. This process can be repeated to add additional files to a collection. Alternatively, you can bulk upload files. To do so, see the example utility `data/sync_files2.py`. To run this utility create a zip file containing your desired files, and then run the utility either directly in Python or by building and running the docker container, eg.

    ```
    # navigate to the helper directory
    cd data

    # replace the zip files in files/ with your desired files to upload
    # note that the zip file name will become the collection name

    # build the container with your custom files included
    docker build . -t file-upload:custom
    
    # assuming you have deployed RAG and AIRA via docker-compose, otherwise adjust the env vars accordingly
    docker run \
    -e RAG_INGEST_URL=http://ingestor-server:8082/v1 \
    -e PYTHONUNBUFFERED=1 \
    -v /tmp:/tmp-data \
    --network nvidia-rag \
    file-upload:custom 
    ```

## How Long Will it Take to Upload Documents?

See the NVIDIA RAG Blueprint documentation for performance guidelines. Typically uploading 10 PDFs, with a total size of ~10MB, should take <5 minutes.

## What File Types are Supported?

File types supported by Nvidia-Ingest are supported by this blueprint. This includes .pdf, .pptx, .txt, .md, and .docx. The default deployment of RAG does not support image captioning.

## Can I use Custom RAG or Other Data Sources?

The RAG service in this blueprint is accessed by a REST API call. Compatible services with the same API could be used instead. Support for additional data sources is on the roadmap.

## How many GPUs do I Need? Can I Deploy with Fewer GPUs?

The blueprint hardware requirements for the default Docker compose deployment with local NVIDIA NIM microservices are outlined in the [README](/README.md#hardware-requirements). Fewer GPUs can be used by deploying the NVIDIA RAG blueprint following [these guidelines](https://github.com/NVIDIA-AI-Blueprints/rag?tab=readme-ov-file#hardware-requirements-for-self-hosting-all-nvidia-nim-microservices).

## What is the Performance?

Report generation typically takes 5-10 minutes depending on the length of the report plan. Individual Q&A can take 45-90 seconds in order to support web and RAG research for each question. For specific metrics like latency or token throughput, [enable observability](/docs/phoenix-tracing.md).

## How do I Make the Report Longer?

The main driver of report length is the number of queries in the report plan. Add more queries through the UI by asking for additional questions in the chat box before running the report generation. Alternatively, you can invoke the `generate_query` backend API with the `num_queries` parameter.

## Has the Tool Been Evaluated?

The AI-Q Research Assistant is evaluated using metrics such as accuracy, groundness, and context relevance. For more information about evaluations, see the [evaluation page](/docs/evaluation.md).

## How are the REST Endpoints Served?

The REST endpoints are created using the [NVIDIA NeMo Agent Toolkit](https://github.com/NVIDIA/NeMo-Agent-Toolkit). Each endpoint is defined as a function and frontend endpoint in the `aira/configs/config.yml` configuration file. The docker compose entrypoint for the backend invokes the `aiq serve` command which makes these endpoints available as REST APIs. The functions are registered with the NeMo Agent toolkit in the `register.py` file, and the source code for the main endpoints is located in the `functions` directory. 

## How do I Debug a Hallucination?

To verify a fact, figure, or claim in the report, start by finding the claim within the report sources. If the claim is contained inside a query and answer pair, check if the source citation is a URL or a PDF. If the source citation is a URL, visit the URL and search for the fact, figure, or claim. If the source citation is a PDF, the answer came from RAG. If you have deployed RAG with the RAG frontend, you can copy the query into the RAG frontend web application to view detailed answers and citations from the original PDF documents. The RAG frontend application is normally hosted at `http://your-rag-server-ip:8090`. 

## How does the UI Stream Intermediate Steps?

The UI makes streaming requests to the REST endpoints. The endpoints are designed as async Python functions, which return intermediate data events. The intermediate data events are created using LangChain Stream writers. Throughout the code, `writer` calls are made to send events to the frontend. `logger` invocations send similar events to the backend service log.

## How do I Limit Tavily Search?

Update the file `aira/src/aiq_aira/constants.py` to include a list of approved domains. When this list is configured, the search function will only search these domains for web queries.

## How do I Increase Timeouts?

The report generation is designed to be robust to intermittent timeouts in LLM calls, RAG search, or web search. In these cases, the frontend web application will notify users about the timeout but proceed with report creation. The backend service log will also note the timeout. To increase the timeout, update the value `ASYNC_TIMEOUT` in the file `aira/src/aiq_aira/constants.py`. 

## How do I Update the Number of Reflections?

During report generation, a reflection agent using a reasoning LLM looks for gaps in the report draft based on the original user prompt. Each gap is addressed by a new query and further research and report writing. The demo web frontend performs two reflection cycles. The number of reflections can be changed by invoking the backend `generate_summary` API with the `num_reflections` argument.

## Can I use Different Models?

The blueprint has been tested with the following model configuration: 

```
llms:
  instruct_llm:
    _type: openai
    model_name: meta/llama-3.3-70b-instruct
    temperature: 0.0

  nemotron:
    _type: openai
    model_name : nvidia/llama-3.3-nemotron-super-49b-v1
    temperature: 0.5
    max_tokens: 5000
    stream: true
```

Other models can be used, though results may vary and some updates to prompt structure might be required. The `nemotron` model should support thinking tokens.