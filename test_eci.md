# Testing with ECI 

1. Create a file, test.env with values

```
AIQ_STARFLEET_CLIENT_ID=""
AIQ_SSA_CLIENT_ID="nvssa-stg-"
AIQ_SSA_CLIENT_SECRET="ssap-"
```

2. Create starfleet token

```
uv pip install jwt # only extra dep beyond whats in aira
uv run --env-file test.env scripts/test_client_auth.py starfleet
```

3. Run backend 

```
uv run --env-file test.env aiq serve --config_file aira/configs/config.yaml
```

4. Execute a POST request to `http://localhost:8000/generate_summary/stream` with body: 

```
{
  "topic": "nvidia benefits",
  "report_organization": "overview of nvidia benefits",
  "queries": [
    {
      "query": "summary of nvidia benefits",
      "report_section": "all",
      "rationale": "important"
    }
  ],
  "search_web": true,
  "rag_collection": "fake",
  "reflection_count": 2,
  "llm_name": "nemotron"
}
```

Sample output: 

```
2025-07-08 08:25:23,711 - aiq_aira.nodes - INFO - STARTING WEB RESEARCH
2025-07-08 08:25:23,711 - aiq_aira.tools - INFO - RAG SEARCH
2025-07-08 08:25:24,263 - aiq_aira.tools - INFO - RAG SEARCH with http://10.185.119.221:8081/generate and {'messages': [{'role': 'user', 'content': 'summary of nvidia benefits'}], 'use_knowledge_base': True, 'enable_citations': True, 'collection_name': 'fake'}
2025-07-08 08:25:24,264 - aiq_aira.search_utils - INFO - RAG ANSWER: 
2025-07-08 08:25:24,264 - aiq_aira.search_utils - INFO - CHECK RELEVANCY
2025-07-08 08:25:24,755 - aiq_aira.search_utils - INFO - RAG NOT RELEVANT, SEARCHING ECI
2025-07-08 08:25:24,755 - aiq_aira.tools - INFO - ECI SEARCH summary of nvidia benefits
calling ECI
Existing Starfleet Credentials found and still valid.
Current Starfleet Credentials:
 - ID token: eyJraWQiOiJvYXV0aC1zaWduLWtpZC0yMDI1MDQwOTA5NTMyOCIsImFsZyI6IkVTMjU2In0.eyJzdWIiOiJfbHg3ZFFJZDNobHRFS3BlR0daR0JpT3VkYXNsQnRqTHVkSzIwZ0piZ3E0IiwiaWRwX25hbWUiOiJOVi1BRCIsImlkcF9pZCI6IjF6VThTQ0hZVFIwNHRnN1VlZGt0TFVIaU1OTlRBdkpnWk4wWThuY3dtRzgiLCJpc3MiOiJodHRwczovL3N0Zy5sb2dpbi5udmlkaWEuY29tIiwiZXh0ZXJuYWxfaWQiOiI1YzkwM2ZjYS0zOThjLTQ2NTYtYWIzYS02NDkxMGNmZjk4YmMiLCJwcmVmZXJyZWRfdXNlcm5hbWUiOiJzbG9wcEBudmlkaWEuY29tIiwic2lkIjoiN0U1T21HaDFBeWI0SDJwM1RQb3p5U2FDbERxdG8yampZVV91RlIzaDhKcyIsImF1ZCI6WyJoY3A4bVFZUFh6Z3hiWjlmdmxTT1plQVVmLVk0U19KQXRfcHpHMFBQalRzIiwiczpDbWl5UmpLcVl6bVhUUFRfT1pNYlkyX0t6ZFZrX2VpRU42V1pBcWkzS3d3Il0sInVwZGF0ZWRfYXQiOjE3NTE5ODI2NjUsImF6cCI6ImhjcDhtUVlQWHpneGJaOWZ2bFNPWmVBVWYtWTRTX0pBdF9wekcwUFBqVHMiLCJleHAiOjE3NTE5ODYyNzAsImlhdCI6MTc1MTk4MjY3MCwianRpIjoiTFgwWmVlbFJZQzJrRmsyaVJpSUI5NFRucmtsMjZOb3BiV2VXc0Vqd2U4QSJ9.gVBqCl0USj7jRQHgddScTh-_-udTLuOWLsf2RmXfQr_rtU2QKEvfWj3ciW4Ec6Lv0dM2I120qQBmBcY9AzHq5A
   Expiration: 2025-07-08 08:51:10 MDT
 - Access token: 7E5OmGh1Ayb4H2p3TPozySaClDqto2jjYU_uFR3h8JtHExpM8IzbeoqREts7wMsVwAB6A552gTKDoXEBEKSGeg
   Token type: Bearer
 - Client token: 7E5OmGh1Ayb4H2p3TPozySaClDqto2jjYU_uFR3h8Jsvj4zcEiwzeXx_x0BVGYmlrePHNkK4eZAQ45qmrFWFGw
   Expiration: 2025-07-09 07:51:11 MDT
Existing SSA Credentials found and still valid.
Current SSA Credentials:
 - Access token: eyJraWQiOiJhYmQ5Y2I5Mi1kYTNlLTRjMDUtOGMwYy0xMjA0OTAwYzlmZTYiLCJhbGciOiJFUzI1NiJ9.eyJzdWIiOiJudnNzYS1zdGctY0RkUFg2SEFoOFpoN1Z5Z1FVbkl6eFdDWVBwVWxnQWN5UkhIQi1HUjBkUSIsImF1ZCI6WyJudnNzYS1zdGctY0RkUFg2SEFoOFpoN1Z5Z1FVbkl6eFdDWVBwVWxnQWN5UkhIQi1HUjBkUSIsInM6MGVrMWJ4ZHc2ZndwaG81Znp2c2Jvbm1taGh1Ym90Zm9kYWt4YnB3bWVwbSJdLCJhenAiOiJudnNzYS1zdGctY0RkUFg2SEFoOFpoN1Z5Z1FVbkl6eFdDWVBwVWxnQWN5UkhIQi1HUjBkUSIsInNlcnZpY2UiOnsibmFtZSI6ImFpcWJwIiwiaWQiOiJqeXZtNnNueTRuYXF1YnBjb241dWtpb25qMWx6ZHVtZWV3M21mM3E2bGNnIn0sImlzcyI6Imh0dHBzOi8vMGVrMWJ4ZHc2ZndwaG81Znp2c2Jvbm1taGh1Ym90Zm9kYWt4YnB3bWVwbS5zdGcuc3NhLm52aWRpYS5jb20iLCJzY29wZXMiOlsiY29udGVudDpzZWFyY2giLCJjb250ZW50OnJldHJpZXZlIiwiY29udGVudDpjbGFzc2lmeSIsImFjY291bnQ6dmVyaWZ5X2FjY2VzcyIsImNvbnRlbnQ6cmV0cmlldmVfbWV0YWRhdGEiLCJjb250ZW50OnN1bW1hcml6ZSJdLCJleHAiOjE3NTE5ODY4MjksInRva2VuX3R5cGUiOiJzZXJ2aWNlX2FjY291bnQiLCJpYXQiOjE3NTE5ODMyMjksImp0aSI6ImEwMWQ0ZjYwLWJlMGQtNDdlMi04NGM5LWZlYmM4OTA5MmMyOSJ9.hq2om2k02CdoQtZRARYY4GnFj-YSP0cs7v6hgjwEEFRnr4xeITHFXlw8LOLsePbHooQTMuCilSb7XBemiU9GUA
 - Token type: bearer
 - Expires at: 2025-07-08 09:00:29 MDT
 - Scope: ['content:search', 'content:retrieve', 'content:classify', 'account:verify_access', 'content:retrieve_metadata', 'content:summarize']
2025-07-08 08:25:25,829 - aiq_aira.search_utils - INFO - ECI ANSWER: 
---
QUERY: 
summary of nvidia benefits

ANSWER: 

Benefits and Support Programs | NVIDIA Benefits
Bring the power of NVIDIA AI to the edge for real-time decision-making solutions
Bring the power of NVIDIA AI to the edge for real-time decision-making solutions

Q1 Fiscal 2023 Summary
costs, gains and losses from non-affiliated investments, interest expense related to amortization of debt discount, the associated tax impact of these items where applicable, domestication tax benefit, and foreign tax benefit. 

The release of NVIDIA’s CUDA software, in particular, was a game-changer, enabling AI developers to create applications that are in turn powered by our processors.
Read more about the energy benefits of accelerated computing in our

The release of NVIDIA’s CUDA software, in particular, was a game-changer, enabling AI developers to create applications that are in turn powered by our processors.
Read more about the energy benefits of accelerated computing in our

CITATION:
https://www.nvidia.com/en-us/benefits/ https://nvidia.sharepoint.com/sites/enterprise-content-intelligence-test-site/_layouts/15/Doc.aspx?sourcedoc=%7B114DCA6A-7CBC-4A6B-9DEB-5148C1903AE9%7D&file=NVIDIA%20Announces%20Financial%20Results%20for%20First%20Quarter%20Fiscal%202023.docx&action=default&mobileredirect=true https://confluence.nvidia.com/pages/viewpage.action?pageId=4012588330 https://nvidia.sharepoint.com/sites/enterprise-content-intelligence-test-site/_layouts/15/Doc.aspx?sourcedoc=%7B738CB620-CFC1-4852-A739-22F043BDC71E%7D&file=How%20Blackwell%20Will%20Transform%20AI.docx&action=default&mobileredirect=true


2025-07-08 08:25:25,829 - aiq_aira.search_utils - INFO - CHECK RELEVANCY
2025-07-08 08:25:31,305 - aiq_aira.search_utils - INFO - ECI NOT RELEVANT, SEARCHING WEB
2025-07-08 08:25:31,306 - aiq_aira.tools - INFO - TAVILY SEARCH
2025-07-08 08:25:31,306 - aiq_aira.tools - WARNING - TAVILY SEARCH FAILED 1 validation error for TavilySearchAPIWrapper
  Value error, Did not find tavily_api_key, please add an environment variable `TAVILY_API_KEY` which contains it, or pass `tavily_api_key` as a named parameter. [type=value_error, input_value={}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.10/v/value_error
2025-07-08 08:25:31,306 - aiq_aira.search_utils - INFO - WEB ANSWER: 
---
QUERY: 
summary of nvidia benefits

ANSWER: 

Benefits and Support Programs | NVIDIA Benefits
Bring the power of NVIDIA AI to the edge for real-time decision-making solutions
Bring the power of NVIDIA AI to the edge for real-time decision-making solutions

Q1 Fiscal 2023 Summary
costs, gains and losses from non-affiliated investments, interest expense related to amortization of debt discount, the associated tax impact of these items where applicable, domestication tax benefit, and foreign tax benefit. 

The release of NVIDIA’s CUDA software, in particular, was a game-changer, enabling AI developers to create applications that are in turn powered by our processors.
Read more about the energy benefits of accelerated computing in our

The release of NVIDIA’s CUDA software, in particular, was a game-changer, enabling AI developers to create applications that are in turn powered by our processors.
Read more about the energy benefits of accelerated computing in our

CITATION:
https://www.nvidia.com/en-us/benefits/ https://nvidia.sharepoint.com/sites/enterprise-content-intelligence-test-site/_layouts/15/Doc.aspx?sourcedoc=%7B114DCA6A-7CBC-4A6B-9DEB-5148C1903AE9%7D&file=NVIDIA%20Announces%20Financial%20Results%20for%20First%20Quarter%20Fiscal%202023.docx&action=default&mobileredirect=true https://confluence.nvidia.com/pages/viewpage.action?pageId=4012588330 https://nvidia.sharepoint.com/sites/enterprise-content-intelligence-test-site/_layouts/15/Doc.aspx?sourcedoc=%7B738CB620-CFC1-4852-A739-22F043BDC71E%7D&file=How%20Blackwell%20Will%20Transform%20AI.docx&action=default&mobileredirect=true


2025-07-08 08:25:31,306 - aiq_aira.search_utils - INFO - DEDUPLICATE RESULTS
2025-07-08 08:25:31,306 - aiq_aira.search_utils - INFO - DEDUPLICATE RESULTS <sources><source><query>summary of nvidia benefits</query><answer /><section>all</section><citation /></source></sources>
2025-07-08 08:25:31,309 - aiq_aira.nodes - INFO - SUMMARIZE
2025-07-08 08:26:00,578 - aiq_aira.nodes - INFO - REFLECTING
2025-07-08 08:26:00,578 - aiq_aira.nodes - INFO - REFLECTING 2 TIMES
2025-07-08 08:26:19,761 - aiq_aira.tools - INFO - RAG SEARCH
2025-07-08 08:26:20,337 - aiq_aira.tools - INFO - RAG SEARCH with http://10.185.119.221:8081/generate and {'messages': [{'role': 'user', 'content': 'What are the benchmark comparisons (training time, throughput) of NVIDIA H100/A100 GPUs versus competitors (e.g., AMD Instinct, Google TPU) in large-scale AI model training (e.g., LLMs)?'}], 'use_knowledge_base': True, 'enable_citations': True, 'collection_name': 'fake'}
2025-07-08 08:26:20,338 - aiq_aira.search_utils - INFO - RAG ANSWER: 
2025-07-08 08:26:20,339 - aiq_aira.search_utils - INFO - CHECK RELEVANCY
2025-07-08 08:26:20,752 - aiq_aira.search_utils - INFO - RAG NOT RELEVANT, SEARCHING ECI
2025-07-08 08:26:20,752 - aiq_aira.tools - INFO - ECI SEARCH What are the benchmark comparisons (training time, throughput) of NVIDIA H100/A100 GPUs versus competitors (e.g., AMD Instinct, Google TPU) in large-scale AI model training (e.g., LLMs)?
calling ECI
Existing Starfleet Credentials found and still valid.
Current Starfleet Credentials:
 - ID token: eyJraWQiOiJvYXV0aC1zaWduLWtpZC0yMDI1MDQwOTA5NTMyOCIsImFsZyI6IkVTMjU2In0.eyJzdWIiOiJfbHg3ZFFJZDNobHRFS3BlR0daR0JpT3VkYXNsQnRqTHVkSzIwZ0piZ3E0IiwiaWRwX25hbWUiOiJOVi1BRCIsImlkcF9pZCI6IjF6VThTQ0hZVFIwNHRnN1VlZGt0TFVIaU1OTlRBdkpnWk4wWThuY3dtRzgiLCJpc3MiOiJodHRwczovL3N0Zy5sb2dpbi5udmlkaWEuY29tIiwiZXh0ZXJuYWxfaWQiOiI1YzkwM2ZjYS0zOThjLTQ2NTYtYWIzYS02NDkxMGNmZjk4YmMiLCJwcmVmZXJyZWRfdXNlcm5hbWUiOiJzbG9wcEBudmlkaWEuY29tIiwic2lkIjoiN0U1T21HaDFBeWI0SDJwM1RQb3p5U2FDbERxdG8yampZVV91RlIzaDhKcyIsImF1ZCI6WyJoY3A4bVFZUFh6Z3hiWjlmdmxTT1plQVVmLVk0U19KQXRfcHpHMFBQalRzIiwiczpDbWl5UmpLcVl6bVhUUFRfT1pNYlkyX0t6ZFZrX2VpRU42V1pBcWkzS3d3Il0sInVwZGF0ZWRfYXQiOjE3NTE5ODI2NjUsImF6cCI6ImhjcDhtUVlQWHpneGJaOWZ2bFNPWmVBVWYtWTRTX0pBdF9wekcwUFBqVHMiLCJleHAiOjE3NTE5ODYyNzAsImlhdCI6MTc1MTk4MjY3MCwianRpIjoiTFgwWmVlbFJZQzJrRmsyaVJpSUI5NFRucmtsMjZOb3BiV2VXc0Vqd2U4QSJ9.gVBqCl0USj7jRQHgddScTh-_-udTLuOWLsf2RmXfQr_rtU2QKEvfWj3ciW4Ec6Lv0dM2I120qQBmBcY9AzHq5A
   Expiration: 2025-07-08 08:51:10 MDT
 - Access token: 7E5OmGh1Ayb4H2p3TPozySaClDqto2jjYU_uFR3h8JtHExpM8IzbeoqREts7wMsVwAB6A552gTKDoXEBEKSGeg
   Token type: Bearer
 - Client token: 7E5OmGh1Ayb4H2p3TPozySaClDqto2jjYU_uFR3h8Jsvj4zcEiwzeXx_x0BVGYmlrePHNkK4eZAQ45qmrFWFGw
   Expiration: 2025-07-09 07:51:11 MDT
Existing SSA Credentials found and still valid.
Current SSA Credentials:
 - Access token: eyJraWQiOiJhYmQ5Y2I5Mi1kYTNlLTRjMDUtOGMwYy0xMjA0OTAwYzlmZTYiLCJhbGciOiJFUzI1NiJ9.eyJzdWIiOiJudnNzYS1zdGctY0RkUFg2SEFoOFpoN1Z5Z1FVbkl6eFdDWVBwVWxnQWN5UkhIQi1HUjBkUSIsImF1ZCI6WyJudnNzYS1zdGctY0RkUFg2SEFoOFpoN1Z5Z1FVbkl6eFdDWVBwVWxnQWN5UkhIQi1HUjBkUSIsInM6MGVrMWJ4ZHc2ZndwaG81Znp2c2Jvbm1taGh1Ym90Zm9kYWt4YnB3bWVwbSJdLCJhenAiOiJudnNzYS1zdGctY0RkUFg2SEFoOFpoN1Z5Z1FVbkl6eFdDWVBwVWxnQWN5UkhIQi1HUjBkUSIsInNlcnZpY2UiOnsibmFtZSI6ImFpcWJwIiwiaWQiOiJqeXZtNnNueTRuYXF1YnBjb241dWtpb25qMWx6ZHVtZWV3M21mM3E2bGNnIn0sImlzcyI6Imh0dHBzOi8vMGVrMWJ4ZHc2ZndwaG81Znp2c2Jvbm1taGh1Ym90Zm9kYWt4YnB3bWVwbS5zdGcuc3NhLm52aWRpYS5jb20iLCJzY29wZXMiOlsiY29udGVudDpzZWFyY2giLCJjb250ZW50OnJldHJpZXZlIiwiY29udGVudDpjbGFzc2lmeSIsImFjY291bnQ6dmVyaWZ5X2FjY2VzcyIsImNvbnRlbnQ6cmV0cmlldmVfbWV0YWRhdGEiLCJjb250ZW50OnN1bW1hcml6ZSJdLCJleHAiOjE3NTE5ODY4MjksInRva2VuX3R5cGUiOiJzZXJ2aWNlX2FjY291bnQiLCJpYXQiOjE3NTE5ODMyMjksImp0aSI6ImEwMWQ0ZjYwLWJlMGQtNDdlMi04NGM5LWZlYmM4OTA5MmMyOSJ9.hq2om2k02CdoQtZRARYY4GnFj-YSP0cs7v6hgjwEEFRnr4xeITHFXlw8LOLsePbHooQTMuCilSb7XBemiU9GUA
 - Token type: bearer
 - Expires at: 2025-07-08 09:00:29 MDT
 - Scope: ['content:search', 'content:retrieve', 'content:classify', 'account:verify_access', 'content:retrieve_metadata', 'content:summarize']
2025-07-08 08:26:21,710 - aiq_aira.search_utils - INFO - ECI ANSWER: 
---
QUERY: 
What are the benchmark comparisons (training time, throughput) of NVIDIA H100/A100 GPUs versus competitors (e.g., AMD Instinct, Google TPU) in large-scale AI model training (e.g., LLMs)?

ANSWER: 


CITATION:



2025-07-08 08:26:21,711 - aiq_aira.search_utils - INFO - CHECK RELEVANCY
2025-07-08 08:26:22,111 - aiq_aira.search_utils - INFO - ECI NOT RELEVANT, SEARCHING WEB
2025-07-08 08:26:22,111 - aiq_aira.tools - INFO - TAVILY SEARCH
2025-07-08 08:26:22,111 - aiq_aira.tools - WARNING - TAVILY SEARCH FAILED 1 validation error for TavilySearchAPIWrapper
  Value error, Did not find tavily_api_key, please add an environment variable `TAVILY_API_KEY` which contains it, or pass `tavily_api_key` as a named parameter. [type=value_error, input_value={}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.10/v/value_error
2025-07-08 08:26:22,111 - aiq_aira.search_utils - INFO - WEB ANSWER: 
---
QUERY: 
What are the benchmark comparisons (training time, throughput) of NVIDIA H100/A100 GPUs versus competitors (e.g., AMD Instinct, Google TPU) in large-scale AI model training (e.g., LLMs)?

ANSWER: 


CITATION:



2025-07-08 08:26:22,111 - aiq_aira.search_utils - INFO - DEDUPLICATE RESULTS
2025-07-08 08:26:22,111 - aiq_aira.search_utils - INFO - DEDUPLICATE RESULTS <sources><source><query>What are the benchmark comparisons (training time, throughput) of NVIDIA H100/A100 GPUs versus competitors (e.g., AMD Instinct, Google TPU) in large-scale AI model training (e.g., LLMs)?</query><answer /><section>All</section><citation /></source></sources>
....
```