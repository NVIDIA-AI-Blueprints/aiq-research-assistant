# Create Research Reports with AI-Q Blueprint User Interface

The AI-Q Research Assistant builds off of the NVIDIA RAG Blueprint, allowing users to upload multi-modal PDFs and then create detailed research reports. 

- First a user can add documents. Example datasets are included, one with 100+ PDFs containing earnings data for Meta, Alphabet, and Amazon and a second with PDFs containing research on Cystic Fibrosis. 

  ![Screenshot showing document upload](/docs/images/aira_upload_screenshot.png)


- Enter a report topic and desired report structure

  ![Screenshot showing prompts](/docs/images/aira_prompt_screemshot.png)

  ```
  # Example Prompt
  You are a financial analyst who specializes in financial statement analysis. Write a financial report analyzing the 2023 financial performance of Amazon. Identify trends in revenue growth, net income, and total assets. Discuss how these trends affected Amazon's yearly financial performance for 2023. Your output should be organized into a brief introduction, as many sections as necessary to create a comprehensive report, and a conclusion. Format your answer in paragraphs. Use factual sources such as Amazon's quarterly meeting releases for 2023. Cross analyze the sources to draw original and sound conclusions and explain your reasoning for arriving at conclusions. Do not make any false or unverifiable claims. I want a factual report with cited sources.
  ```

- Review and edit a research plan

  ![Screenshot showing the research plan](/docs/images/aira_plan_screenshot.png)

  ``` 
  # Example Research Plan

  Query: Amazon 2023 quarterly revenue growth trends compared to 2022
  Section: Revenue Growth Analysis
  Rationale: Identify year-over-year revenue patterns and seasonal fluctuations

  Query: Factors affecting Amazon's net income margin in 2023 Q1-Q4
  Section: Net Income Trend Drivers
  Rationale: Analyze expense structures or cost increases impacting profitability
  ```

- Perform deep research to create a report, sourcing data from the on-premise documents and the web

  ![Screenshot showing the report](/docs/images/aira_report_screenshot.png)

  ``` 
  # Example Report 
  
  ## Revenue Growth Analysis
  Amazon's revenue growth accelerated throughout 2023, with a notable increase in the fourth quarter.
  The company's net sales increased 12% to $574.8 billion in 2023, compared with $514.0 billion in 2022 (1).
  A quarterly breakdown of the revenue growth reveals a steady increase in sales throughout the year. In Q1
  2023, net sales increased 9% to $127.4 billion, compared with $116.4 billion in Q1 2022 (1). This growth was
  followed by an 11% increase in Q2 2023, with net sales reaching $134.4 billion, compared with $121.2 billion
  in Q2 2022 (1).
  ...

  ## Sources
  
  **Source** 2 
  
  **Query:** Factors affecting Amazon's net income margin in 2023 Q1-Q4
  
  **Answer:** **Amazon's Net Income Margin Factors (2023 Q1-Q4)**

  1. **Revenue Growth**:
    - **Increase in Net Sales**: Across all segments (North America, International, AWS) contributed to higher revenue.
    - **Segment-wise Growth**:
      - North America: 11% (Q1), 13% (Q4)
      - International: 1% (Q1), 17% (Q4)
      - AWS: 16% (Q1), 13% (Q4)
  ...
  **Citations:** AMZN-Q4-2023-Earnings-Release_chunk_1.pdf,,Q4-2022-Amazon-Earnings-Release_chunk_1.pdf,,,,Q1-2023-Amazon-Earnings-Release_chunk_1.pdf,,,
  ```

- Edit the report or ask follow up questions

During report generation, an example of test time computation is provided, as a reasoning LLM is used to reflect on report drafts, identify gaps, and perform further queries.