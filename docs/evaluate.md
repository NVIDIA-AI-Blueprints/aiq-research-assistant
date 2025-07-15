# AIQ AIRA Evaluation Suite

A complete evaluation framework for AI Research Assistant (AIRA) workflows, featuring **automatic dataset preprocessing** and comprehensive assessment of AI-generated research reports.


### Automatic Dataset Preprocessing
The evaluation suite now **automatically generates missing evaluation fields** from your dataset:
- **Context Relevance Questions**: Generates targeted questions for evaluating retrieved contexts
- **Coverage Facts/Claims**: Extracts key facts from ground truth for coverage assessment
- **Skip Workflow Method**: You can upload a dataset that already includes these fields, and the system will automatically detect them in the workflow, so no additional steps are required on your part.


## Prerequisites & Dependencies

### Required Versions
- **Python 3.12+**

### Dependency Management
If you encounter dependency conflicts, reference the tested dependency versions from the NeMo-Agent-Toolkit project:
- **Reference**: https://github.com/NVIDIA/NeMo-Agent-Toolkit/blob/develop/uv.lock

### API Keys Required
- `NVIDIA_API_KEY` - For LLM access
- `TAVILY_API_KEY` - For web search (optional)
- `WANDB_API_KEY` - For Weave tracing (optional)

## Quick Start

### 1. Branch Checkout
After cloning the repository, make sure to checkout to the correct branch:

```bash
git clone <repository-url> 
cd into it
git checkout ajay-nat-eval-updates 
```

### 2. Installation

#### Development Installation (Recommended)
For local development, use [uv](https://docs.astral.sh/uv/getting-started/installation/) for better dependency management:

```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment with Python 3.12
uv python install 3.12
uv venv --python 3.12 --python-preference managed

# Install AIRA package in development mode
uv pip install -e "./aira[dev]"
```


#### Standard Installation
```bash
# Install AIRA package
cd aira/
pip install -e .
cd ..
```


### 2. Set Environment Variables

```bash
export NVIDIA_API_KEY="your_nvidia_api_key"
export TAVILY_API_KEY="your_tavily_api_key"  # Optional for web search
export WANDB_API_KEY="your_wandb_api_key" #optional again, there are more instructions below if you want to set up tracing to w&b weave
```

### 3. Run Evaluation

```bash

# Full workflow + evaluation (requires RAG server) + saving logs to txt file 
aiq eval --config_file aira/configs/eval_config.yml 
```
### 4. Run Evaluation saving it to .txt file 

```bash

# I would recommend running with > output.txt 2>&1 to better analyze the log statements / any errors
aiq eval --config_file aira/configs/eval_config.yml > output.txt 2>&1
```


## Dataset Requirements

### Minimal Dataset Format
Your dataset only needs these basic fields - **the system will automatically generate the rest**:

```json
[
  {
    "id": "example_1",
    "topic": "Write a report about...",
    "report_organization": "Executive Summary, Analysis, Conclusions",
    "reflection_count": 3,
    "num_queries": 3,
    "llm_name": "nemotron",
    "search_web": false,
    "rag_collection": "Biomedical_Dataset",
    "report_size": "Small",
    "ground_truth": "Your reference report content here..."
  }
]
```

**After Automatic Preprocessing:**
```json
{
  "id": "cystic_fibrosis_1",
  "topic": "Write a report about cystic fibrosis...",
  "ground_truth": "Cystic fibrosis is an inherited disease...",
  "context_relevance_questions": [
    {
      "question": "What role do airway epithelial cells play?",
      "rationale": "Understanding epithelial cell function is crucial...",
      "aspect": "Airway epithelial cells"
    }
  ],
  "coverage_facts_claims": [
    "Cystic fibrosis is an inherited disease that leads to thick mucus",
    "Neutrophils release powerful enzymes that harm lung tissue"
  ]
}
```

## Configuration

### Main Configuration File
Use `aira/configs/eval_config.yml` as your starting point:

```yaml
# LLM Configuration
llms:
  eval_llm:
    _type: openai
    model_name: meta/llama-3.1-70b-instruct
    base_url: https://integrate.api.nvidia.com/v1
    api_key: ${NVIDIA_API_KEY}

# Dataset Configuration
general:
  dataset:
    file: "data/eval_dataset.json"  # Your minimal dataset or it could be a fully processed one either works

# Workflow Configuration with Preprocessing
workflow:
  _type: aira_evaluator_workflow
  generator:
    _type: full
    fact_extraction_llm: meta/llama-3.1-70b-instruct  # LLM for preprocessing
    verbose: true  # Enable detailed logging

# Evaluation Configuration
eval:
  general:
    output_dir: ./.tmp/aiq_aira/
    cleanup: true
  evaluators:
    coverage:
      _type: coverage
      llm: eval_llm
    synthesis:
      _type: synthesis
      llm: eval_llm
```

## Setting Up Weave Tracing (Currently need to request weave access, contact Michael Demoret for enterprise weave access)

To enable Weights & Biases Weave for experiment tracking and observability:

### 1. Configure Weights & Biases
```bash
# Set your Weights & Biases API key
export WANDB_API_KEY=<your_api_key>

# Login to wandb
wandb login
```

### 2. Reinstall Package (if necessary)
```bash
uv pip install -e "./aira[dev]"
```

### 3. Configure Weave in Your Config File 
```yaml
general:
  telemetry:
    tracing:
      weave:
        _type: weave
        project: "your-project-name"

eval:
  general:
    workflow_alias: "my_experiment_name"  # This will label your evaluation in Weave 
    .tmp/aiq_aira
```

**Important**: The `workflow_alias` determines how your evaluation runs will be labeled and organized in Weave. Use descriptive names like:
- `"baseline_experiment"`
- `"v2_with_reflection"`  
- `"cystic_fibrosis_eval"`

**Information Tracked on Weave**: Weave will track your evaluation metrics (citation quality, etc.) for each individual run. Additionally, it will also contain information about your dataset and configuration information such as the llm_type that you used to run certain portions of your experiment allowing for better comparsions.

### Key Configuration Options

- **`fact_extraction_llm`**: LLM used for generating missing evaluation fields
- **`verbose`**: Enable detailed logging to see preprocessing progress
- **`output_dir`**: Where evaluation results are saved

### Citation Pairing LLM Configuration

The `citation_pairing_llm` setting controls which model pairs facts with citations. **Llama models struggle with citation pairing**, so GPT models are recommended (The team is looking to revamp the prompt so that nvidia models perform better but for now please try and use gpt if you can and you would need either a perflab key or LLM Gateway key):

**Option 1: Use GPT models (Recommended)**
```yaml
workflow:
  generator:
    citation_pairing_llm: gpt-4o-20241120  # Default, good performance
```
**Required environment variables if you want to use gpt models (LLM Gateway):**
```bash
export NV_CLIENT_ID="your_client_id"
export NV_CLIENT_SECRET="your_client_secret"
```

**Option 2: Use NVIDIA models**
```yaml
workflow:
  generator:
    citation_pairing_llm: nvdev/meta/llama-3.1-70b-instruct
```
**Uses existing:** `NVIDIA_API_KEY` (no additional setup required)


## Available Evaluators

The suite includes comprehensive evaluators for research report quality:

### Core Evaluators
- **Coverage**: Measures how well the report covers key facts from ground truth
- **Synthesis**: Evaluates integration of information from multiple sources  
- **Hallucination**: Detects unsupported claims in generated reports
- **Citation Quality**: Validates accuracy and relevance of citations

### RAGAS Integration
- **Context Relevance**: How relevant retrieved contexts are to the query
- **Answer Accuracy**: Factual correctness compared to ground truth
- **Groundedness**: Whether responses are supported by retrieved contexts

### Common Issues

1. **Import Errors**: Ensure both packages are installed in development mode (`pip install -e .`)
2. **API Key Issues**: Verify environment variables are set correctly
3. **RAG Server Connection**: Check `rag_url` in config matches your server



## Project Structure (will fix this later when merged)

```
aiq-bp-internal/
├── aira/                           # AIRA workflow package
│   ├── configs/
│   │   └── eval_config.yml        # Main configuration file
│   ├── src/aiq_aira/
│   │   ├── functions/             # Core AIRA functions  
│   │   └── eval/
│   │       ├── generators/
│   │       │   ├── generate_full.py      # Main generator with preprocessing
│   │       │   └── extraction_utils.py   # Preprocessing utilities
│   │       ├── evaluators/        # Custom evaluators
│   │       └── schema.py          # Data models
│   └── pyproject.toml
├── data/
│   ├── data/eval_dataset.json     # Complete dataset example
└── docs/
    └── evaluate.md                # This documentation
```

## Developer Workflow

### 1. Create Your Dataset
```json
[
  {
    "id": "my_experiment_1", 
    "topic": "Your research topic here...",
    "ground_truth": "Your reference content...",
    "report_organization": "Introduction, Analysis, Conclusion",
    "num_queries": 3,
    "llm_name": "nemotron",
    "search_web": false,
    "rag_collection": "Your_Collection",
    "reflection_count": 2
  }
]
```

### 2. Update Configuration
```yaml
general:
  dataset:
    file: "path/to/your/dataset.json"

workflow:
  generator:
    verbose: true  # See preprocessing & other logs in action
```

### 3. Run Evaluation
```bash
aiq eval --config_file aira/configs/eval_config.yml
```

### 4. Check Results
```
./.tmp/aiq_aira/
├── workflow_output.json         # Generated data (with preprocessing)
├── coverage_output.json         # Coverage evaluation results
├── synthesis_output.json        # Synthesis evaluation results
└── ...
```


## Troubleshooting

### Common Issues

**"No context_relevance_questions found" but they exist**:
- Check that the field contains actual data, not empty lists
- Verify JSON structure is correct

**Preprocessing takes too long**:
- Use a faster LLM model for `fact_extraction_llm`
- Reduce ground truth content length

**API rate limits**:
- The system automatically handles retries
- Consider using a different model endpoint

**Missing evaluation fields after preprocessing**:
- Check API key is valid
- Enable `verbose: true` to see detailed logs
- Verify LLM model name is correct

**Profiling error with `--skip_workflow`**:
```
ValueError: DataFrame is missing required columns: {'example_number', 'event_timestamp'}
```
- **Cause**: Profiler tries to compute workflow runtime metrics when no workflow was run
- **Solution**: Disable profiling in your config:
  ```yaml
  eval:
    general:
      profiler:
        base_metrics: false  # Disable when using --skip_workflow
  ```

Enable verbose logging (turn this off if you get too much logs):

```yaml
workflow:
  generator:
    verbose: true
```

This shows:
- Preprocessing progress
- Generated question/fact counts
- LLM call details
- Timing information

## Performance Tips

1. **Choose appropriate LLM models** - faster models for preprocessing, higher quality for evaluation. Would suggest using mistral for RAGAS metrics they provide much better variability than the llama models on build from my experience
2. **Use skip_workflow mode** (`--skip_workflow`) for faster iteration during development if you already have a workflow done running
3. **Batch similar experiments** to minimize setup overhead

The preprocessing system is designed to be extensible - you can easily add new evaluation fields by following the existing patterns in `extraction_utils.py`.

## License

Apache 2.0 - See LICENSE file for details.
