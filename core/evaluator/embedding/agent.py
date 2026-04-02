from core.BaseAgent import BaseAgent
from pydantic import BaseModel

class OutputSchema(BaseModel):
    analysis: dict
    
PROMPT = """You are a Senior Machine Learning Engineer specializing in information retrieval and vector search optimization. Your task is to analyze the following embedding model evaluation results and provide a detailed improvement plan.

Context:
The results come from an evaluation script that measures the performance of different embedding models on a retrieval task. The key performance metrics are defined as follows:
- Accuracy Percentage: The percentage of successful retrievals (hits / total * 100).
- Average Total RF Score: The average relevance/ranking score across all searches. A higher score is better.
- Average Hit RF Score: The average relevance/ranking score for only the successful searches (hits). This indicates the quality of the successful results.
- Average Latency (s): The average time in seconds to perform one search. Lower is better.
- Overall Performance Index (OPI): Calculated as (Accuracy * Average_Total_RF_Score) / sqrt(Latency). This metric provides a balanced view of accuracy, relevance, and speed.
- Precision Efficiency Index (PEI): Calculated as (Accuracy * Average_Hit_RF_Score) / sqrt(Latency). This focuses on how efficiently the model retrieves high-quality results.
- Search Performance Index (SPI): Calculated as Accuracy / sqrt(Latency). This measures the trade-off between pure accuracy and speed.

Your Tasks:

Please provide a structured analysis covering the following points:

1. Executive Summary:
    - Briefly summarize the performance of the models.
    - Which model would you recommend as the best "overall" performer and why?
    - Which model is best for a use case that prioritizes speed above all else? Which is best for maximum accuracy?

2. Detailed Performance Analysis:
    - Model Comparison: Compare the models based on their Accuracy, Latency, and custom indices (OPI, PEI, SPI).
    - Trade-offs: Discuss the trade-offs observed between accuracy and latency. For example, compare text-embedding-3-large with all-MiniLM-L6-v2.
    - Parameter Impact: Analyze the effect of changing top_k from 5 to 10 for the bge-small-en-v1.5 model. Was the accuracy gain worth the latency increase?

3. Actionable Recommendations for Improvement:
    Provide specific, concrete suggestions to improve the evaluation scores (higher accuracy and indices). Organize your recommendations into the following categories:
    Model & Search Configuration:
        - How can the search_cfg parameters (e.g., HNSW's m and ef_construction/ef_search) be tuned to improve the balance between speed and accuracy?
        - Suggest other distance metrics to experiment with (e.g., dotproduct, L2).

4. Data Preprocessing & Chunking:
    - What data cleaning or preprocessing steps could improve retrieval accuracy?
    - How could different document chunking strategies (e.g., sentence splitting, recursive splitting, fixed size) impact the results?

5. Embedding & Indexing Strategy:
    - Suggest advanced retrieval techniques beyond simple vector search (e.g., hybrid search, reranking with a cross-encoder).
    - Discuss the potential benefits of using product quantization (PQ) or other indexing optimizations to reduce memory usage and latency, and what the expected impact on accuracy would be.

6. Future Experiments:
    - What other models would you suggest evaluating?
    - Propose a plan for a next round of experiments to validate your recommendations.
    - Please structure your response clearly. Your analysis should be insightful and your recommendations practical and easy to implement.
"""

class Analyst(BaseAgent):
    def __init__(self, llm, **kwargs):
        super().__init__(
            llm=llm,
            prompt_template=PROMPT,
            output_model=OutputSchema,
            **kwargs
        )

    def __call__(self, evaluation_result: str, sample_dataset: str) -> str:
        try:
            raw, parsed = self.run_chain(input=f"Evaluation Results : {evaluation_result} \nSample Dataset : {sample_dataset}")
            return raw
        except Exception as e:
            return f"Error analyzing evaluation results: {str(e)}"            
