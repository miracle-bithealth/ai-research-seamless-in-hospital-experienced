import asyncio
from datetime import datetime
import json
import os
import pandas as pd
from tqdm import tqdm

# Example imports - REPLACE THESE WITH YOUR ACTUAL IMPORTS
# from your_app.services.your_service import YourServiceClass, YOUR_PROMPT_TEMPLATE
# from your_app.schemas.your_schema import YourOutputSchema
# from your_app.evaluator.your_evaluator import YourEvaluatorEngine
# from your_app.generative import manager  # Assuming this manages LLM loading
# from your_app.evaluator.test_cases.your_test_cases import YOUR_TEST_CASES

class SampleLLMEvaluation:
    """
    A reusable template class to orchestrate the end-to-end evaluation process for any LLM-based service/agent.
    
    To use this template:
    1. In __init__, customize:
       - LLM loading (e.g., for agent and evaluator).
       - Service instantiation (e.g., YourService(llm=llm_agent)).
       - Evaluator instantiation (e.g., YourEvaluator(llm=llm_evaluator)).
       - Set self.prompt_template and self.output_schema (if needed for your eval data).
    2. In _process_single_case:
       - Customize the service method call (e.g., await self.service.your_method(test_case)).
       - Adjust evaluation_data dict to match what your evaluator expects (e.g., add/remove keys like 'prompt', 'output_schema').
    3. In run:
       - Set self.test_cases = YOUR_TEST_CASES (list of dicts with at least 'input' key).
       - Customize output filename, eval columns if needed.
       - Ensure your test_cases is a list of dicts, e.g., [{'input': 'sample query'}].
    4. Subclass if you need more customization, or edit inline for simple cases.
    """
    EVALUATION_RESULTS_DIR = "evaluation_results"  # Customize output dir

    def __init__(self):
        """Initializes all necessary services and clients. Customize this section."""
        print("Initializing services...")
        
        # Load LLMs - Customize names, temps, etc.
        llm_evaluator = manager._get_llm(name="your_evaluator_llm", temperature=0)  # e.g., "gemini_regular"
        llm_agent = manager._get_llm(name="your_agent_llm", temperature=0)  # e.g., "gemini_mini"

        # Instantiate your service/agent - Customize class and init args
        self.service = YourServiceClass(llm=llm_agent)  # Replace with your service, e.g., QueryExtractionService
        
        # Instantiate your evaluator - Customize class and init args
        self.evaluator_engine = YourEvaluatorEngine(llm=llm_evaluator)  # Replace with your evaluator
        
        # Set prompt and schema if your evaluator uses them - Customize or set to None
        self.prompt_template = YOUR_PROMPT_TEMPLATE  # e.g., PROMPT_TEMPLATE or None
        self.output_schema = json.dumps(YourOutputSchema.model_json_schema(), indent=2) if 'YourOutputSchema' in locals() else None
        
        # Load your test cases here
        self.test_cases = YOUR_TEST_CASES  # e.g., DIRECT_TEST_CASES

    async def _process_single_case(self, test_case: dict) -> dict:
        """
        Runs the agent/service for a single test case and returns data for evaluation.
        Customize: Service method call and evaluation_data structure.
        """
        # Extract input - assumes test_case has 'input' key; add more if needed (e.g., test_case['context'])
        input_data = test_case["input"]
        
        # Call your service method - Customize method name and args
        result = await self.service.your_method(input_data)  # e.g., self.query_extraction_agent.extract_queries(test_case)
        
        # Prepare data for evaluator
        evaluation_data = {
            "input": input_data,
            "prompt": self.prompt_template, 
            "output_schema": self.output_schema, 
            "output": result,
        }
        return evaluation_data

    async def run(self):
        """Executes the entire evaluation flow. Customize test_cases, filename, etc."""
        if not self.test_cases:
            print("No test cases found. Exiting.")
            return

        evaluation_data = []
        print(f"Found {len(self.test_cases)} test cases to evaluate.")

        try:
            # Process all test cases    
            for test_case in tqdm(self.test_cases, desc="Processing Test Cases"):
                data = await self._process_single_case(test_case)
                evaluation_data.append(data)

            # Run evaluation engine
            print("\nAll test cases processed. Running evaluation engine...")
            eval_df = pd.DataFrame(evaluation_data)
            final_df = await self.evaluator_engine.run_evaluation(eval_df)

            # Save results - Customize filename and path
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f"YourAgentEvaluationResult_{timestamp}.xlsx"  # Customize name
            output_path = os.path.join(self.EVALUATION_RESULTS_DIR, output_filename)
            
            os.makedirs(self.EVALUATION_RESULTS_DIR, exist_ok=True)
            final_df.to_excel(output_path, index=False)
            
            print(f"\nEvaluation complete. Results saved to: {output_path}")

        except Exception as e:
            print(f"Error during evaluation: {e}")
        finally:
            print("\nEvaluation process finished.")


if __name__ == "__main__":
    # Instantiate and run
    evaluator = GenericLLMEvaluation()
    asyncio.run(evaluator.run())