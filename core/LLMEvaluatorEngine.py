import pandas as pd
from tqdm.asyncio import tqdm
import warnings
from core.BaseAgent import BaseAgent
from pydantic import BaseModel, Field
from typing import Literal

class LLMEvaluatorOutput(BaseModel):
    """
    Schema for the LLM Evaluator output.
    """

    label: Literal["correct", "incorrect"] = Field(
        ...,
        description="'correct' if the AI output is perfect and follows all instructions, otherwise 'incorrect'."
    )
    
    explanation: str = Field(
        ...,
        description="A detailed explanation of why the output is correct or incorrect, referencing specific rules or steps from the AI's original prompt that were violated."
    )
    
    solution: str = Field(
        ...,
        description="A concrete and actionable suggestion for improving the AI's performance, such as a prompt refinement or a logic adjustment."
    )

### Gemini Model
PROMPT_TEMPLATE = """
# Role & Goal
You are an expert AI Evaluator. 
Your goal is to meticulously assess the performance of another AI based on a given set of criteria. 
You must provide a clear judgment (`correct` or `incorrect`), a detailed explanation for your decision, and a constructive solution for improvement.

# Context for Evaluation
Here is the information about the AI task you need to evaluate:

-   **Original Input:**
    ---
    {input}
    ---

-   **AI's Instructions (Prompt):**
    ---
    {prompt}
    ---

-   **Expected Output Structure (Schema):**
    ---
    {output_schema}
    ---

-   **Actual AI Output:**
    ---
    {output}
    ---

# Evaluation Process / Steps
1.  **Analyze the Context**: Carefully review the `Original Input`, the `AI's Instructions`, the `Expected Output Structure`, and the `Actual AI Output`. If an image is part of the input, analyze its content visually.
2.  **Identify Violations**: Compare the `Actual AI Output` against the `AI's Instructions`. Did the AI follow every rule and constraint? Did it correctly interpret the `Original Input`?
3.  **Check Structural Integrity**: Does the `Actual AI Output` conform to the `Expected Output Structure`?
4.  **Formulate Judgment (Label)**: Based on your analysis, label the output as `correct` only if it is absolutely perfect and follows all instructions. Otherwise, label it as `incorrect`.
5.  **Provide Explanation**: Clearly explain *why* the output is correct or incorrect. If incorrect, pinpoint the specific rule(s) or step(s) from the instructions that were violated or how the output deviated from the expected behavior.
6.  **Suggest a Solution**: Offer a concrete and actionable solution to fix the issue for future improvements. This could be a suggestion to refine the AI's prompt, adjust the logic, or handle the data differently.

# Output Format
You MUST provide your response in a JSON format that strictly adheres to the provided schema. Do not add any text or explanations outside of the JSON structure.
"""

class LLMEvaluator(BaseAgent):
    """An agent responsible for evaluating the output of other LLM agents."""
    def __init__(self, llm, **kwargs):
        super().__init__(
            llm=llm,
            prompt_template=PROMPT_TEMPLATE,
            use_structured_output=True,
            output_model=LLMEvaluatorOutput,
            agent_name="LLMEvaluator",
            **kwargs
        )

    def _build_multimodal_chain_input(self, row_input: list) -> list:
        """
        Constructs the multimodal input for the LLM chain from a structured list,
        following LangChain's conventions.
        Reference: https://python.langchain.com/docs/how_to/multimodal_inputs/
        """
        base_text = "Evaluate the given data accurately and informatively, based on the context and the attached data."
        chain_input = [{"type": "text", "text": base_text}]

        for item in row_input:
            item_type = item.get("type")
            source = item.get("source")
            
            if not all([item_type, source]):
                warnings.warn(f"Skipping invalid multimodal item (missing type or source): {item}")
                continue

            content_block = {"type": item_type}
            is_url = isinstance(source, str) and source.startswith("http")

            if is_url:
                content_block.update({"source_type": "url", "url": source})
            else:
                mime_type = item.get("mime_type")
                if not mime_type:
                    warnings.warn(f"Skipping base64 item due to missing mime_type: {item}")
                    continue
                content_block.update({"source_type": "base64", "data": source, "mime_type": mime_type})
            
            if item_type == "pdf":
                content_block["type"] = "file"

            chain_input.append(content_block)
        
        return chain_input

    async def run_evaluation(self, dataset: pd.DataFrame | str, is_multimodal: bool = False) -> pd.DataFrame:
        """
        Runs the evaluation on each row of the provided DataFrame.

        Args:
            dataset (pd.DataFrame or str): DataFrame or path to a file (.csv, .xlsx, .json)
                                         with columns 'input', 'prompt', 'output_schema', 'output'.
            is_multimodal (bool): If True, 'input' column is expected to be a list of structured dicts
                                  for multimodal content (text, image, pdf, audio).

        Returns:
            pd.DataFrame: The original DataFrame with added columns 'label', 'explanation', 'solution'.
        """
        if isinstance(dataset, str):
            if dataset.endswith('.csv'):
                df = pd.read_csv(dataset)
            elif dataset.endswith('.xlsx'):
                df = pd.read_excel(dataset)
            elif dataset.endswith('.json'):
                df = pd.read_json(dataset)
            else:
                raise ValueError("Unsupported file format. Please provide a .csv, .xlsx, or .json file.")
        else:
            df = dataset
        
        df[['label', 'explanation', 'solution']] = None
        
        df[['label', 'explanation', 'solution']] = None

        for index, row in tqdm(df.iterrows(), total=df.shape[0], desc="Evaluating Rows"):
            try:
                self.rebind_prompt_variable(
                    input=str(row['input']), # Pass a string representation for the prompt context
                    output_schema=row['output_schema'],
                    prompt=row['prompt'],
                    output=row['output']
                )

                if is_multimodal:
                    chain_input = self._build_multimodal_chain_input(row['input'])
                else:
                    chain_input = "Evaluate the given data accurately and informatively."

                _, parsed = await self.arun_chain(input=chain_input)

                df.loc[index, 'label'] = parsed.label
                df.loc[index, 'explanation'] = parsed.explanation
                df.loc[index, 'solution'] = parsed.solution

            except Exception as e:
                error_message = f"An error occurred: {e}"
                df.loc[index, 'label'] = "error"
                df.loc[index, 'explanation'] = error_message
                df.loc[index, 'solution'] = "Failed to evaluate this case."

        return df
