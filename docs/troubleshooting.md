# Troubleshooting for AI-Q NVIDIA Research Assistant Blueprint

The software components in the blueprint interact in the following way:

![architecture](/docs/images/aira-service-architecture.png)

Start troubleshooting by narrowing down which sub-service is failing. The first step is to determine if the UI is misconfigured, the middleware proxy, or the backend. We also recommend following the RAG blueprint documentation to ensure RAG is fully functional prior to deploying the AI-Q Research Assistant.

## Errors with Collections or Document Upload

To identify errors with collections or document upload, follow the steps below.

1. Attempt to list the collections directly through the RAG `ingestor-server` API:

    ```bash
    # replace ingestor-server with the *PUBLIC* IP address of your rag service, or run this command from a container
    curl -v http://ingestor-server:8082/v1/collections
    ```

    If this doesn't work, follow the RAG documentation to fix the deployment. Check the ingestor-server logs, eg `docker logs ingestor-server -f`. 

2. Attempt to list the collections through the middleware proxy:

    ```bash
    # replace aira-nginx with the *PUBLIC* IP address of the nginx proxy, `localhost`, or run this command from a container 
    curl -v http://aira-nginx:8051/v1/collections
    ```

    If this doesn't work, double check the proxy configuration, which requires `RAG_INGEST_URL` and `AIRA_BASE_URL` to be set. If you are deploying with helm, the values.yaml file contains the entire nginx proxy configuration, be sure you have the appropriate service IP addresses in the proxy_pass lines. Check the nginx logs, eg `docker logs aira-nginx -f`. 


3. Attempt to list the collections through the application. Check the browser network logs and the application logs, `docker logs aira-frontend -f`. If this does not work, ensure you have configured the application via the `INFERENCE_ORIGIN` environment variable which should be set to the IP address of your NGINX proxy, `http://aira-nginx:8051`. 

4. If collection listing works, but documents fail to upload, check the logs in the RAG ingestor service, `docker logs ingestor-server -f`. 

**Note: During bulk file upload using the file upload utility, if you see 429 errors in the logs for the compose-nv-ingest-ms-runtime-1 service log it suggests a temporary error. You can re-run the file upload command multiple times, each time the process will pick up where it left off, uploading any documents that failed due to this error.**

## Errors with Report Plan Generation 

To identify errors with Rreport planning generation, follow the steps below.

1. Attempt to connect to the AI-Q Research Assistant backend API. In a browser, navigate to http://aira-backend:3838/docs, replacing aira-backend with the *PUBLIC* IP address of the AI-Q Research Assistant service or `localhost`. Use the API docs to run the `/generate_query`. If the docs do not load, check the AI-Q Research Assistant services logs `docker logs aira-backend -f`. 

2. If the docs load, but the example API request fails or the UI stalls after saying "Generating queries", the issue will likely be with the `nemotron` model configuration in the AI-Q Research Assistant configuration file. Verify this model configuration is correct, and attempt to make a sample request directly to the LLM. Example requests are provided on `build.nvidia.com`.


## Errors with Q&A

To identify errors with Q&A, follow the steps below.

1. Attempt to connect to the AI-Q Research Assistant backend API. In a browser, navigate to http://aira-backend:3838/docs, replacing aira-backend with the *PUBLIC* IP address of the AI-Q Research Assistant service or `localhost`. Use the API docs to run the `/artifact_qa` call. If the docs do not load, check the AI-Q Research Assistant services logs `docker logs aira-backend -f`. 

2. If the docs load, but the example API request fails or the UI stalls after showing "AIQ Thinking", the most likely issue is with the `instruct_llm` model configuration in the AI-Q Research Assistant configuration file. Verify this model configuration is correct, and attempt to make a sample request directly to the LLM. Example requests are provided on `build.nvidia.com`.

## Errors with RAG search during report generation

Ensure you have appropriately configured the `rag_url` settings in the AI-Q Research Assistant configuration file, or provided appropriate values in the helm values.yaml file.

If you are using one of the default report topics and prompts, ensure you have [loaded the default collections](./get-started-docker-compose.md#add-default-collections).

## Errors with web search during report generation

Ensure you have provided a valid TAVILY API KEY, and have set the `TAVILY_API_KEY` environment variable.