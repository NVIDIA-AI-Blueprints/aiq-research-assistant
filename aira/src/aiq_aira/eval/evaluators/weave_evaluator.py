# # SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# # SPDX-License-Identifier: Apache-2.0
# #
# # Licensed under the Apache License, Version 2.0 (the "License");
# # you may not use this file except in compliance with the License.
# # You may obtain a copy of the License at
# #
# # http://www.apache.org/licenses/LICENSE-2.0
# #
# # Unless required by applicable law or agreed to in writing, software
# # distributed under the License is distributed on an "AS IS" BASIS,
# # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# # See the License for the specific language governing permissions and
# # limitations under the License.

# """
# Weave evaluator that integrates with W&B Weave's evaluation framework.
# This evaluator automatically detects which evaluators are configured and
# transforms them into native Weave evaluations that appear on the dashboard.
# """

# import json
# import logging
# import asyncio
# from typing import Any, Dict, List, Optional
# from pathlib import Path

# import weave
# from pydantic import Field
# from langchain_core.language_models.base import BaseLanguageModel

# from aiq.builder.builder import EvalBuilder
# from aiq.builder.evaluator import EvaluatorInfo
# from aiq.cli.register_workflow import register_evaluator
# from aiq.data_models.evaluator import EvaluatorBaseConfig
# from aiq.data_models.component_ref import LLMRef
# from aiq.eval.evaluator.evaluator_model import EvalOutputItem, EvalInput, EvalOutput

# from aiq_aira.eval.schema import AIResearcherEvalOutput

# logger = logging.getLogger(__name__)

# class WeaveEvaluatorConfig(EvaluatorBaseConfig, name="weave_evaluator"):
#     """Configuration for the Weave evaluator."""
#     enabled: bool = Field(default=True, description="Whether to run Weave evaluations")

# class WeaveEvaluator:
#     """
#     Evaluator that integrates with W&B Weave's evaluation framework.
#     Automatically detects which evaluators are configured and creates native Weave evaluations.
#     Uses the existing Weave project from tracing and workflow_alias from eval config.
#     """

#     def __init__(self, config: WeaveEvaluatorConfig, builder: EvalBuilder):
#         self.config = config
#         self.builder = builder
#         self.available_evaluators = self._detect_configured_evaluators()

#         # Get the workflow alias from eval config for evaluation naming
#         self.workflow_alias = getattr(builder.eval_general_config, 'workflow_alias', 'aira_evaluation')

#         logger.info(f"Detected {len(self.available_evaluators)} configured evaluators: {list(self.available_evaluators.keys())}")
#         logger.info(f"Using workflow alias: {self.workflow_alias}")

#     def _detect_configured_evaluators(self) -> Dict[str, Any]:
#         """Dynamically detect which evaluators are configured in the pipeline."""
#         evaluators = {}

#         # Check the eval configuration for configured evaluators
#         eval_config = self.builder.eval_general_config
#         if hasattr(eval_config, 'evaluators') and eval_config.evaluators:
#             for evaluator_name, evaluator_config in eval_config.evaluators.items():
#                 # Skip the weave_evaluator itself to avoid recursion
#                 if evaluator_name == 'weave_dashboard' or evaluator_name == 'weave_evaluator':
#                     continue

#                 # Map evaluator types to metric names
#                 evaluator_type = evaluator_config.get('_type', evaluator_name)
#                 metric_name = self._get_metric_name(evaluator_type, evaluator_config)

#                 evaluators[evaluator_name] = {
#                     'type': evaluator_type,
#                     'config': evaluator_config,
#                     'metric_name': metric_name
#                 }

#         return evaluators

#     def _get_metric_name(self, evaluator_type: str, evaluator_config: Dict[str, Any]) -> str:
#         """Get the metric name for an evaluator type."""
#         if evaluator_type == 'coverage':
#             return 'coverage'
#         elif evaluator_type == 'synthesis':
#             return 'synthesis'
#         elif evaluator_type == 'hallucination':
#             return 'hallucination'
#         elif evaluator_type == 'citation_quality':
#             return 'citation_quality'
#         elif evaluator_type == 'ragas_wrapper':
#             # Use the specific RAGAS metric name
#             metric = evaluator_config.get('metric', 'ragas_metric')
#             return f"ragas_{metric.lower()}"
#         else:
#             return evaluator_type

#     def _create_weave_scorer(self, evaluator_name: str, evaluator_info: Dict[str, Any]):
#         """Create a Weave scorer function for an evaluator."""

#         @weave.op()
#         def scorer(output: dict) -> dict:
#             """Dynamically created Weave scorer."""
#             try:
#                 # Read the evaluation results from the output files
#                 results_dir = Path(self.builder.eval_general_config.output_dir)
#                 output_file = results_dir / f"{evaluator_name}_output.json"

#                 if not output_file.exists():
#                     logger.warning(f"No output file found for {evaluator_name}: {output_file}")
#                     return {evaluator_info['metric_name']: 0.0}

#                 # Load the evaluation results
#                 with open(output_file, 'r') as f:
#                     eval_results = json.load(f)

#                 # Extract the score for this specific output
#                 output_id = output.get('id')
#                 if not output_id:
#                     logger.warning(f"No ID found in output for {evaluator_name}")
#                     return {evaluator_info['metric_name']: 0.0}

#                 # Find the result for this specific item
#                 for item in eval_results.get('eval_output_items', []):
#                     if item.get('id') == output_id:
#                         score = item.get('score', 0.0)
#                         reasoning = item.get('reasoning', {})

#                         return {
#                             evaluator_info['metric_name']: score,
#                             f"{evaluator_info['metric_name']}_reasoning": reasoning
#                         }

#                 logger.warning(f"No result found for ID {output_id} in {evaluator_name}")
#                 return {evaluator_info['metric_name']: 0.0}

#             except Exception as e:
#                 logger.error(f"Error in {evaluator_name} scorer: {e}")
#                 return {evaluator_info['metric_name']: 0.0, f"{evaluator_info['metric_name']}_error": str(e)}

#         # Set a meaningful name for the scorer
#         scorer.__name__ = f"{evaluator_name}_scorer"
#         return scorer

#     @weave.op()
#     def evaluation_model(self, input_data: dict) -> dict:
#         """
#         Model function for Weave evaluation.
#         This function will be called by the Weave evaluation framework.
#         """
#         try:
#             # The input_data should already be a dict representation of AIResearcherEvalOutput
#             return input_data
#         except Exception as e:
#             logger.error(f"Error in evaluation model: {e}")
#             return {"error": str(e)}

#     async def evaluate(self, eval_input: EvalInput) -> EvalOutput:
#         """
#         Main evaluation function that runs Weave evaluations.
#         This follows the standard Weave evaluation pattern from the documentation.
#         Uses the existing Weave project and workflow_alias for evaluation naming.
#         """
#         if not self.config.enabled:
#             logger.info("Weave evaluator disabled")
#             return self._create_dummy_output(eval_input)

#         if not self.available_evaluators:
#             logger.info("No evaluators detected - skipping Weave evaluation")
#             return self._create_dummy_output(eval_input)

#         try:
#             # Step 1: Use existing Weave project if available, otherwise log warning
#             current_project = None
#             try:
#                 current_project = weave.get_current_call()
#                 if current_project:
#                     logger.info(f"Using existing Weave project from tracing configuration")
#                 else:
#                     logger.warning("No Weave project found from tracing - evaluation metrics may not appear on dashboard")
#                     logger.warning("Please ensure Weave tracing is configured in your general config")
#             except Exception as e:
#                 logger.warning(f"Could not detect existing Weave project: {e}")
#                 logger.warning("Evaluation will run but metrics may not appear on dashboard")

#             # Step 2: Define a dataset of test examples
#             dataset = []
#             for item in eval_input.eval_input_items:
#                 try:
#                     # Parse the data
#                     if item.output_obj:
#                         data_source = AIResearcherEvalOutput.model_validate_json(item.output_obj)
#                     else:
#                         data_source = AIResearcherEvalOutput.model_validate_json(item.input_obj)

#                     # Convert to dict for Weave
#                     dataset.append(data_source.model_dump())
#                 except Exception as e:
#                     logger.error(f"Error parsing item {item.id}: {e}")
#                     continue

#             if not dataset:
#                 logger.error("No valid data items found for evaluation")
#                 return self._create_error_output(eval_input, "No valid data items found")

#             # Step 3: Define scoring functions - dynamically created from configured evaluators
#             scorers = []
#             for evaluator_name, evaluator_info in self.available_evaluators.items():
#                 scorer = self._create_weave_scorer(evaluator_name, evaluator_info)
#                 scorers.append(scorer)
#                 logger.info(f"Created Weave scorer for {evaluator_name} -> {evaluator_info['metric_name']}")

#             if not scorers:
#                 logger.error("No scorers created from configured evaluators")
#                 return self._create_error_output(eval_input, "No scorers created")

#             # Step 4: Create an Evaluation object using workflow_alias as evaluation name
#             evaluation = weave.Evaluation(
#                 dataset=dataset,
#                 scorers=scorers,
#                 evaluation_name=self.workflow_alias
#             )

#             logger.info(f"Created Weave evaluation with {len(dataset)} examples and {len(scorers)} scorers")
#             logger.info(f"Evaluation name (from workflow_alias): {self.workflow_alias}")
#             logger.info(f"Metrics: {[info['metric_name'] for info in self.available_evaluators.values()]}")

#             # Step 5: Run the evaluation
#             result = await evaluation.evaluate(self.evaluation_model)

#             logger.info(f"Weave evaluation completed successfully")
#             logger.info(f"Results: {result}")

#             # Create output items for compatibility with the evaluation framework
#             output_items = []
#             for item in eval_input.eval_input_items:
#                 output_items.append(EvalOutputItem(
#                     id=item.id,
#                     score=1.0,  # Weave evaluation completed successfully
#                     reasoning={
#                         "message": "Weave evaluation completed successfully",
#                         "metrics": list(self.available_evaluators.keys()),
#                         "workflow_alias": self.workflow_alias,
#                         "evaluation_name": self.workflow_alias
#                     }
#                 ))

#             return EvalOutput(
#                 average_score=1.0,
#                 eval_output_items=output_items
#             )

#         except Exception as e:
#             logger.error(f"Error in Weave evaluation: {e}")
#             logger.exception("Full traceback:")
#             return self._create_error_output(eval_input, str(e))

#     def _create_dummy_output(self, eval_input: EvalInput) -> EvalOutput:
#         """Create a dummy output when Weave evaluator is disabled."""
#         items = [
#             EvalOutputItem(
#                 id=item.id,
#                 score=None,
#                 reasoning={"message": "Weave evaluator disabled or no evaluators detected"}
#             )
#             for item in eval_input.eval_input_items
#         ]

#         return EvalOutput(
#             average_score=0.0,
#             eval_output_items=items
#         )

#     def _create_error_output(self, eval_input: EvalInput, error_message: str) -> EvalOutput:
#         """Create an error output when Weave evaluation fails."""
#         items = [
#             EvalOutputItem(
#                 id=item.id,
#                 score=0.0,
#                 reasoning={"message": f"Weave evaluation failed: {error_message}"}
#             )
#             for item in eval_input.eval_input_items
#         ]

#         return EvalOutput(
#             average_score=0.0,
#             eval_output_items=items
#         )
