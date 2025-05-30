## Testing AIRA

AIRA is a complex system with many integrations, which can make testing hard. Currently there are a few tests to avoid regressions. To run them: 

Open the `aira` directory. Create a virtual environment using uv, and then run:

```bash
uv sync
```

This will install the test dependencies which are included in the pyproject.toml file.

Create a file called test.env that includes the API key needed to access the staging nemotron model. If you have a .env file already that is loaded too and will work.

```bash
 DOCKER_HOST="unix://$HOME/.colima/default/docker.sock"         
 OPENAI_API_KEY="..."
```

### Test web_research 

```bash
uv run pytest test_aira/test_web_search.py -s --log-cli-level=DEBUG
```

This will run the `web_research` node used by `generate_summary`, *using a mock rag web server*; testing two cases: relevant results and non-relevant results. The pytest output will include the log messages from the AIRA backend and the stream writer results from the frontend. There are *minimal* assertions currently on the results.

The mock rag web server is designed to validate the inputs from web_research, and to respond with responses similar to the real RAG 2 server API spec, saved in rag_response...json files.



### Test docker image

```bash
uv run pytest test_aira/test_module_loads.py 
```

This test requires docker. The test runs the docker compose build of the aira backend and then confirms that the resulting image can start the AIQ webserver and that the aira functions can all be properly imported.

### Test configmap structure

```bash
uv run pytest test_aira/test_configmap_matches_config.py -s
```

This test validates that the Helm configmap template maintains the same structure as the reference configuration. It:
1. Compares the structure of `deploy/helm/aiq-aira/templates/configmap.yaml` with `aira/configs/config.yml`
2. Recursively checks that all keys match between the reference and generated configs
3. Provides a hierarchical view of any structural differences
4. Warns if the optional 'eval' key is missing
5. Errors if any other required keys are missing

The `-s` flag enables output of the hierarchical key comparison, which is helpful for debugging configuration mismatches.

### Test artifact QA functionality

**Requires running RAG server and proper AIRA config.yaml file**

```bash
uv run pytest test_aira/test_artifact_qa.py -s
```

This test suite validates the artifact QA functionality, which allows users to ask questions about or request modifications to previously generated artifacts. The tests cover several key scenarios:

1. Basic Q&A: Tests simple question-answering about an artifact's content
2. Entire Rewrite: Tests the ability to rewrite an entire artifact with new content
3. Highlighted Rewrite: Tests modifying specific sections of an artifact
4. Empty Context Handling: Tests behavior when no specific context is provided for highlighted rewrites

Each test verifies:
- Correct input/output types
- Expected content modifications
- Appropriate handling of different rewrite modes
- Proper integration with the workflow builder
- Model validation of input data

The `-s` flag enables output of the test execution, including any logging messages from the AIRA backend.

### Test query generation

```bash
uv run pytest test_aira/test_generate_query.py -s
```

This test suite validates the query generation functionality, which creates structured search queries for research topics. The tests cover several key scenarios:

1. Basic Query Generation: Tests generating queries with default settings (3 queries)
2. Custom Query Count: Tests generating a single query instead of the default count

Each test verifies:
- Correct input/output types
- Expected number of queries
- Query structure and content (query, report_section, and rationale fields)
- Model validation of input data

The `-s` flag enables output of the test execution, including any logging messages from the AIRA backend.

### Test summary generation

**Requires running RAG server and proper AIRA config.yaml file**

```bash
uv run pytest test_aira/test_generate_summary.py -s
```

This test suite validates the summary generation functionality, which creates comprehensive reports based on generated queries and web research. The tests cover several key scenarios:

1. Basic Summary Generation: Tests creating a summary with web research enabled
2. No Web Research: Tests summary generation without web research

Each test verifies:
- Correct input/output types
- Presence of citations and final report
- Content quality and relevance
- Proper handling of web research settings
- Model validation of input data
- Correct intermediate stream results

The `-s` flag enables output of the test execution, including any logging messages from the AIRA backend.

