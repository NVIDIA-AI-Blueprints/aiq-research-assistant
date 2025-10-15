# SPDX-FileCopyrightText: Copyright (c) 2025, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import logging
from typing import Any
from typing import Dict
from typing import List

from nat.builder.builder import Builder
from nat.builder.framework_enum import LLMFrameworkEnum
from pydantic import BaseModel
from pydantic import Field

from aiq_aira.eval.config import AIRAEvaluatorWorkflowConfig
from aiq_aira.eval.generator_register import AIRAGeneratorBase
from aiq_aira.eval.generator_register import register_generator
from aiq_aira.eval.schema import AIResearcherEvalInput
from aiq_aira.eval.schema import AIResearcherEvalOutput
from aiq_aira.schema import GenerateQueryStateInput
from aiq_aira.schema import GenerateSummaryStateInput

from .extraction_utils import batch_pair_facts_with_citations
from .extraction_utils import extract_groundness_facts
from .extraction_utils import extract_rag_contexts
from .extraction_utils import extract_reflections_and_queries
from .extraction_utils import extract_relevancy_judgements
from .extraction_utils import extract_web_answers
from .extraction_utils import generate_context_relevance_questions
from .extraction_utils import generate_coverage_facts_claims
from .extraction_utils import split_report_and_citations

logger = logging.getLogger(__name__)


@register_generator("full")
class AIRAFullGenerator(AIRAGeneratorBase):
    """
    Full implementation of the AI-Q Research Assistant generator that uses the complete AI-Q Research Assistant workflow.
    This integrates with the actual AI-Q Research Assistant pipeline including query generation, research, and report generation.
    """

    def __init__(self, config: AIRAEvaluatorWorkflowConfig, builder: Builder):
        super().__init__(config, builder)
        self.generate_queries_fn = None
        self.generate_summary_fn = None
        self.fact_extraction_llm = self.config.generator.fact_extraction_llm
        self.citation_pairing_llm = self.config.generator.citation_pairing_llm
        self.setup_generator()

    def setup_generator(self):
        '''Setup the full generator with AI-Q Research Assistant workflow functions.'''
        logger.info("Setting up full AI-Q Research Assistant generation mechanism.")

        # Get the AI-Q Research Assistant workflow functions from the builder
        self.generate_queries_fn = self.builder.get_function(name="generate_query")
        self.generate_summary_fn = self.builder.get_function(name="generate_summary")
        logger.info("Successfully loaded AI-Q Research Assistant workflow functions")

    async def pre_process(self, eval_input: AIResearcherEvalInput) -> AIResearcherEvalInput:
        """Pre-process evaluation input, generating missing questions and facts if needed"""
        verbose = getattr(self.config.generator, 'verbose', False)

        # Check if we need to generate context relevance questions
        if not eval_input.context_relevance_questions or len(eval_input.context_relevance_questions) == 0:
            if verbose:
                logger.info("No context_relevance_questions found in input, generating them...")

            # Generate the questions using the extraction utils function
            questions = await generate_context_relevance_questions(eval_input.topic,
                                                                   eval_input.ground_truth,
                                                                   llm=self.fact_extraction_llm,
                                                                   verbose=verbose)

            eval_input.context_relevance_questions = questions

            if verbose:
                logger.info("Generated %d context relevance questions", len(questions))

        # Check if we need to generate coverage facts/claims
        if not eval_input.coverage_facts_claims or len(eval_input.coverage_facts_claims) == 0:
            if verbose:
                logger.info("No coverage_facts_claims found in input, generating them...")

            # Extract the facts using the extraction utils function
            facts = await generate_coverage_facts_claims(eval_input.ground_truth,
                                                         llm=self.fact_extraction_llm,
                                                         verbose=verbose)

            eval_input.coverage_facts_claims = facts

            if verbose:
                logger.info("Extracted %d coverage facts/claims", len(facts))

        return eval_input

    async def generate_queries_with_logging(self, input_data: GenerateQueryStateInput) -> Dict[str, Any]:
        """Generate queries with intermediate step logging"""
        verbose = getattr(self.config.generator, 'verbose', False)

        # Collect all intermediate steps and final output
        intermediate_steps = []
        intermediate_data = {}  # Accumulate data by key
        final_output = None

        if verbose:
            logger.info("Starting query generation stream...")

        # Stream the function execution
        async for output in self.generate_queries_fn.astream(input_data):
            if hasattr(output, 'intermediate_step') and output.intermediate_step:
                # Parse the intermediate step
                step_data = json.loads(output.intermediate_step)

                # Accumulate data by key
                for key, value in step_data.items():
                    if key not in intermediate_data:
                        intermediate_data[key] = ""
                    intermediate_data[key] += str(value)

                if verbose:
                    logger.debug("Query Intermediate Step: %s", output.intermediate_step)
            else:
                final_output = output
                if verbose:
                    logger.info("Final Queries received: %d queries", len(output.queries) if output.queries else 0)

        # Convert accumulated data to list format
        for key, value in intermediate_data.items():
            intermediate_steps.append({key: value})

        if verbose:
            logger.info("Query generation stream complete. Intermediate steps: %d", len(intermediate_steps))

        return {"queries": final_output.queries if final_output else [], "intermediate_steps": intermediate_steps}

    async def generate_summary_with_logging(self, input_data: GenerateSummaryStateInput) -> Dict[str, Any]:
        """Generate summary with intermediate step logging"""
        verbose = getattr(self.config.generator, 'verbose', False)

        # Collect all intermediate steps and final output
        intermediate_steps = []
        intermediate_data = {}  # Accumulate data by key
        final_output = None

        if verbose:
            logger.info("Starting summary generation stream...")
            logger.info("Processing %d queries through research pipeline", len(input_data.queries))

        # Stream the function execution
        async for output in self.generate_summary_fn.astream(input_data):
            if hasattr(output, 'intermediate_step') and output.intermediate_step:
                # Parse the intermediate step
                step_data = json.loads(output.intermediate_step)

                # Accumulate data by key
                for key, value in step_data.items():
                    if key not in intermediate_data:
                        intermediate_data[key] = ""
                    intermediate_data[key] += str(value)

                if verbose:
                    # Log specific steps with more detail
                    if "web_research" in step_data:
                        logger.info("Web research step completed")
                    elif "rag_answer" in step_data:
                        logger.info("RAG search step completed")
                    elif "finalize_summary" in step_data:
                        logger.info("Finalizing summary...")

                    logger.debug(
                        "Summary Intermediate Step: %s",
                        output.intermediate_step[:200] +
                        "..." if len(output.intermediate_step) > 200 else output.intermediate_step)
            else:
                final_output = output
                if verbose:
                    logger.info("Final Report Generated!")
                    logger.info("  - Report length: %d characters",
                                len(output.final_report) if output.final_report else 0)
                    logger.info("  - Has citations: %s", "Yes" if output.citations else "No")

        # Convert accumulated data to list format
        for key, value in intermediate_data.items():
            intermediate_steps.append({key: value})

        if verbose:
            logger.info("Summary generation stream complete. Intermediate steps: %d", len(intermediate_steps))

        return {
            "final_report": final_output.final_report if final_output else "",
            "citations": final_output.citations if final_output else "",
            "intermediate_steps": intermediate_steps
        }

    async def extract_evaluation_outputs(self,
                                         eval_input: AIResearcherEvalInput,
                                         query_result: Dict[str, Any],
                                         summary_result: Dict[str, Any]) -> AIResearcherEvalOutput:
        """Extract all evaluation outputs from the generated results"""
        verbose = getattr(self.config.generator, 'verbose', False)

        if verbose:
            logger.info("Starting extraction of evaluation outputs...")

        # Extract RAG contexts
        if verbose:
            logger.info("Extracting RAG contexts...")
        rag_contexts = extract_rag_contexts(summary_result["intermediate_steps"])
        if verbose:
            logger.info("  - Extracted %d RAG contexts", len(rag_contexts))

        # Extract relevancy judgements
        if verbose:
            logger.info("Extracting relevancy judgements...")
        relevancy_judgements = extract_relevancy_judgements(summary_result["intermediate_steps"])
        if verbose:
            logger.info("  - Extracted %d relevancy judgements", len(relevancy_judgements))

        # Extract web answers
        if verbose:
            logger.info("Extracting web answers...")
        web_answers = extract_web_answers(summary_result["intermediate_steps"])
        if verbose:
            logger.info("  - Extracted %d web answers", len(web_answers))

        # Extract reflections and queries from reflections
        if verbose:
            logger.info("Extracting reflections and queries from reflections...")
        reflections, queries_from_reflections = extract_reflections_and_queries(summary_result["intermediate_steps"])
        if verbose:
            logger.info("  - Extracted %d reflections", len(reflections))
            logger.info("  - Extracted %d queries from reflections", len(queries_from_reflections))

        # Split report and citations
        if verbose:
            logger.info("Splitting report and citations...")
        finalized_summary, citation_section = split_report_and_citations(summary_result["final_report"])
        if verbose:
            logger.info("  - Summary length: %d characters", len(finalized_summary))
            logger.info("  - Citation section length: %d characters", len(citation_section))

        # Extract groundness facts (now passing LLM)
        if verbose:
            logger.info("Extracting groundness facts using LLM...")
        groundness_facts_claims = await extract_groundness_facts(finalized_summary,
                                                                 llm=self.fact_extraction_llm,
                                                                 verbose=verbose)
        if verbose:
            logger.info("  - Extracted %d facts/claims", len(groundness_facts_claims))
            if len(groundness_facts_claims) > 0 and len(groundness_facts_claims) <= 5:
                for i, fact in enumerate(groundness_facts_claims, 1):
                    logger.info("    Fact %d: %s", i, fact[:100] + "..." if len(fact) > 100 else fact)

        # Pair facts with citations (now passing LLM)
        if verbose:
            logger.info("Pairing facts with citations using LLM...")

        # Create the complete report by combining finalized_summary and citation_section
        # This ensures the LLM can find actual citations in the text
        complete_report = f"{finalized_summary}\n\n{citation_section}"

        # Debug: Analyze report structure to understand citation patterns
        if verbose:
            # from aiq_aira.eval.generators.extraction_utils import debug_report_structure
            # debug_report_structure(complete_report, finalized_summary, citation_section)
            logger.info("Debug: Analyzing report structure...")
            logger.info(f"Complete report length: {len(complete_report)} characters")
            logger.info(f"Finalized summary length: {len(finalized_summary)} characters")
            logger.info(f"Citation section length: {len(citation_section)} characters")

        fact_citation_pairs = await batch_pair_facts_with_citations(
            complete_report,  # Use complete report instead of just finalized_summary
            groundness_facts_claims,
            llm=self.citation_pairing_llm,
            verbose=verbose)
        if verbose:
            logger.info("  - Paired %d facts with citations", len(fact_citation_pairs))
            facts_with_citations = sum(1 for _, citations in fact_citation_pairs if citations)
            logger.info("  - Facts with citations: %d", facts_with_citations)
            logger.info("  - Facts without citations: %d", len(fact_citation_pairs) - facts_with_citations)

        # Create output object
        output = AIResearcherEvalOutput(
            # Input fields
            id=eval_input.id,
            topic=eval_input.topic,
            report_organization=eval_input.report_organization,
            search_web=eval_input.search_web,
            rag_collection=eval_input.rag_collection,
            num_queries=eval_input.num_queries,
            llm_name=eval_input.llm_name,
            reflection_count=eval_input.reflection_count,
            ground_truth=eval_input.ground_truth,
            context_relevance_questions=eval_input.context_relevance_questions,
            coverage_facts_claims=eval_input.coverage_facts_claims,
            # Convert GeneratedQuery Pydantic models to dicts for eval schema compatibility and JSON serialization
            queries=[q.model_dump() if hasattr(q, 'model_dump') else q for q in query_result["queries"]],
            rag_contexts=rag_contexts,
            relevancy_judgements=relevancy_judgements,
            web_answers=web_answers,
            queries_from_reflections=queries_from_reflections,
            reflections=reflections,
            finalized_summary=finalized_summary,
            citation_section=citation_section,
            groundness_facts_claims=groundness_facts_claims,
            fact_citation_pairs=fact_citation_pairs,
        )

        # Add detailed logging for schema validation
        logger.info(f"=== SCHEMA VALIDATION LOGGING ===")
        logger.info(f"Generated output fields:")
        output_dict = output.model_dump()
        for field_name, field_value in output_dict.items():
            if isinstance(field_value, (list, dict)):
                logger.info(f"  {field_name}: {type(field_value).__name__} (length: {len(field_value)})")
            else:
                logger.info(f"  {field_name}: {type(field_value).__name__} ({field_value is not None})")

        # Log any fields that might be empty or None
        empty_fields = [k for k, v in output_dict.items() if not v]
        if empty_fields:
            logger.warning(f"Empty or None fields: {empty_fields}")

        # Validate the output can be serialized
        try:
            output_json = output.model_dump_json()
            logger.info(f"Output serialization successful (length: {len(output_json)})")
        except Exception as e:
            logger.error(f"Output serialization failed: {e}")

        logger.info(f"=== END SCHEMA VALIDATION ===")

        return output

    async def generate_fn(self, aira_input: AIResearcherEvalInput) -> AIResearcherEvalOutput:
        '''Full generate function that runs the complete AIRA research pipeline.'''

        # Determine if verbose logging is enabled
        verbose = getattr(self.config.generator, 'verbose', False)

        if verbose:
            logger.info("=" * 80)
            logger.info("Starting AIRA generation for instance: %s", aira_input.id)
            logger.info("  topic: %s", aira_input.topic)
            logger.info("  report_organization: %s", aira_input.report_organization)
            logger.info("  rag_collection: %s", aira_input.rag_collection)
            logger.info("  search_web: %s", aira_input.search_web)
            logger.info("  num_queries: %s", aira_input.num_queries)
            logger.info("  reflection_count: %s", aira_input.reflection_count)
        else:
            logger.info("Processing instance: %s", aira_input.id)

        # Pre-process the input
        aira_input = await self.pre_process(aira_input)

        # Handle LLM name - use from input if provided, otherwise use from config
        llm_name = aira_input.llm_name
        if not llm_name:
            llm_name = getattr(self.config.generator, 'llm_name', 'nemotron')
            if verbose:
                logger.info("No llm_name in input, using from config: %s", llm_name)
        elif verbose:
            logger.info("Using llm_name from input: %s", llm_name)

        # Stage 1: Generate queries
        query_input = GenerateQueryStateInput(
            topic=aira_input.topic,
            report_organization=aira_input.report_organization,
            num_queries=aira_input.num_queries,
            llm_name=llm_name  # Use the determined llm_name
        )

        if verbose:
            logger.info("=" * 40)
            logger.info("=== Stage 1: Generating Queries ===")
            logger.info("Query generation input:")
            logger.info("  - Topic: %s", query_input.topic)
            logger.info("  - Report Organization: %s...", query_input.report_organization[:100])
            logger.info("  - Number of queries: %d", query_input.num_queries)
            logger.info("  - LLM: %s", query_input.llm_name)

        query_result = await self.generate_queries_with_logging(query_input)

        if verbose:
            logger.info("Query generation complete. Generated %d queries:", len(query_result["queries"]))

        # Stage 2: Generate summary
        summary_input = GenerateSummaryStateInput(
            topic=aira_input.topic,
            report_organization=aira_input.report_organization,
            queries=query_result["queries"],
            search_web=aira_input.search_web,
            rag_collection=aira_input.rag_collection,
            llm_name=llm_name,  # Use the determined llm_name
            reflection_count=aira_input.reflection_count)

        if verbose:
            logger.info("=" * 40)
            logger.info("=== Stage 2: Generating Summary ===")
            logger.info("Summary generation input:")
            logger.info("  - Search web: %s", summary_input.search_web)
            logger.info("  - RAG collection: %s", summary_input.rag_collection)
            logger.info("  - Reflection count: %d", summary_input.reflection_count)
            logger.info("  - Using %d queries for research", len(summary_input.queries))

        summary_result = await self.generate_summary_with_logging(summary_input)

        if verbose:
            logger.info("Summary generation complete.")
            logger.info("  - Final report length: %d characters", len(summary_result["final_report"]))
            logger.info("  - Citations section length: %d characters", len(summary_result.get("citations", "")))
            logger.info("  - Number of intermediate steps: %d", len(summary_result["intermediate_steps"]))

        # Stage 3: Extract all evaluation outputs
        if verbose:
            logger.info("=" * 40)
            logger.info("=== Stage 3: Extracting Evaluation Outputs ===")

        output = await self.extract_evaluation_outputs(aira_input, query_result, summary_result)

        if verbose:
            logger.info("Extraction complete:")
            logger.info("  - RAG contexts extracted: %d", len(output.rag_contexts))
            logger.info("  - Relevancy judgements: %d", len(output.relevancy_judgements))
            logger.info("  - Web answers: %d", len(output.web_answers))
            logger.info("  - Reflections: %d", len(output.reflections))
            logger.info("  - Queries from reflections: %d", len(output.queries_from_reflections))
            logger.info("  - Groundness facts/claims: %d", len(output.groundness_facts_claims))
            logger.info("  - Fact-citation pairs: %d", len(output.fact_citation_pairs))
            logger.info("=" * 80)
            logger.info("Completed processing instance: %s", aira_input.id)
        else:
            logger.info("Completed instance: %s", aira_input.id)

        return output
