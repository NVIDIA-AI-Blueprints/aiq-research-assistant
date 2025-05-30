import os
ASYNC_TIMEOUT=120 

# Only needed if RAG endpoint requires an API key
RAG_API_KEY = os.getenv("RAG_API_KEY", "")

# INCLUDE WHITELIST DOMNAINS FOR TAVILY SEARCH
TAVILY_INCLUDE_DOMAINS = []
# TAVILY_INCLUDE_DOMAINS = [
#     "wikipedia.org",
#     "arxiv.org",
#     "medlineplus.gov",
#     "pubmed.ncbi.nlm.nih.gov",
#     "go.drugbank.com",
#     "clinicaltrials.gov",
#     "open.fda.gov",
#     "patents.google.com",
#     "cysticfibrosisjournal.com",
#     "cff.org",
#     "nhlbi.nih.gov",
#     "hopkinscf.org",
#     "reuters.com",
#     "cnbc.com",
#     "finance.yahoo.com",
#     "marketwatch.com",
#     "forbes.com"
# ]