# embedding_evaluator/experiment_runner.py

"""
Experiment Runner Module
========================
This module orchestrates the entire embedding evaluation experiment.
It manages data loading, embedding generation, search execution, and result collection.

Key Responsibilities:
- Coordinate between data handler, embedding manager, and collection manager
- Execute search tests across multiple models and configurations
- Track performance metrics (accuracy, latency, rank fusion scores)
- Save detailed results for analysis

No pandas or numpy dependencies - uses native Python data structures.
"""

import copy
import itertools
import csv
from tqdm import tqdm
from typing import List, Dict, Any, Optional
import json
from datetime import datetime

from .data_handler import DataHandler
from .embedding_manager import EmbeddingManager
from .collection_manager import CollectionManager
from .results_processor import ResultsProcessor

BATCH = 40
class EmbeddingEvaluator:
    """
    Main class for running embedding evaluation experiments.
    
    This class orchestrates the entire evaluation pipeline:
    1. Load and prepare data
    2. Generate embeddings for multiple models
    3. Index documents in Typesense
    4. Execute search queries with different configurations
    5. Collect and analyze results
    
    Attributes:
        typesense_client: Client for interacting with Typesense
        model_cache_dir: Directory to cache embedding models
        temp_collection_name: Name of temporary Typesense collection
        data_handler: Handles data loading and preparation
        embedding_manager: Manages embedding generation and caching
        results_processor: Processes and saves results
        detailed_results: List storing detailed results for each query
    """
    
    def __init__(self, typesense_client, model_cache_dir: str):
        """
        Initialize the EmbeddingEvaluator.
        
        Args:
            typesense_client: Initialized Typesense client instance
            model_cache_dir: Path to directory for caching embedding models
            temp_collection_name: Name for temporary collection (will be deleted after)
        """
        self.typesense_client = typesense_client
        self.model_cache_dir = model_cache_dir
        
        # Initialize component managers
        self.data_handler = DataHandler()
        self.embedding_manager = EmbeddingManager(model_cache_dir)
        self.results_processor = ResultsProcessor()
        self.collection_manager = CollectionManager(self.typesense_client)
        
        # Store detailed results for each query execution
        self.detailed_results = []

    def run_experiment(
        self,
        json_path: str,
        page_content_template: str,
        target_embed_column: str,
        models_to_test: List[dict],
        search_configs_to_test: List[dict],
        iteration_params: Dict[str, List[Any]],
        sort_accuracy: bool = True,
        csv_output_path: Optional[str] = None,
        detailed_output_path: Optional[str] = None
    ) -> List[Dict]:
        """
        Run the complete embedding evaluation experiment.
        
        This is the main entry point for running experiments. It:
        1. Loads and prepares the dataset
        2. Generates embeddings for all models
        3. Tests each model with all search configurations
        4. Collects metrics and saves results
        
        Args:
            json_path: Path to JSON file containing dataset
                Example: "data/queries.json"
                
            page_content_template: Template string for creating searchable content
                Example: "Question: {question}\nContext: {context}"
                Placeholders {field_name} are replaced with actual values
                
            target_embed_column: Column name to use for generating query embeddings
                Example: "question" - this column will be embedded and used as query
                
            models_to_test: List of model configurations to evaluate
                Example: [
                    {'name': 'sentence-transformers/all-MiniLM-L6-v2', 'dimension': 384},
                    {'name': 'BAAI/bge-small-en-v1.5', 'dimension': 384}
                ]
                
            search_configs_to_test: List of Typesense search configurations
                Example: [
                    {
                        'q': '*',
                        'vector_query': 'vector:({vector}, k:100)',
                        'exclude_fields': 'vector',
                        'limit': 10
                    }
                ]
                
            iteration_params: Parameters to iterate over in grid search
                Example: {'alpha': [0.1, 0.5, 0.9]} - tests hybrid search weights
                Each combination will be tested
                
            sort_accuracy: If True, sort final results by accuracy (default: True)
            
            csv_output_path: Optional path to save summary results as CSV
                Example: "results/experiment_results.csv"
                
            detailed_output_path: Optional path to save detailed per-query results
                Example: "results/detailed_results.json"
                Supports .json or .csv extension
                
        Returns:
            List[Dict]: List of result dictionaries, one per configuration tested
            Each dict contains metrics like accuracy, latency, RF scores, etc.
            
        Example:
            evaluator = EmbeddingEvaluator(client, "./cache", "temp_collection")
            results = evaluator.run_experiment(
                json_path="queries.json",
                page_content_template="{text}",
                target_embed_column="query",
                models_to_test=[{'name': 'model-name', 'dimension': 384}],
                search_configs_to_test=[{...}],
                iteration_params={'alpha': [0.5]},
                csv_output_path="results.csv"
            )
        """
        print(f"\n{'='*60}")
        print(f"Starting Embedding Evaluation Experiment")
        print(f"{'='*60}")
        
        # STEP 1: Load and prepare data
        print("\n[1/5] Loading and preparing dataset...")
        dataset_index, dataset_experiment = self.data_handler.load_and_prepare_data(
            json_path, page_content_template, target_embed_column
        )
        
        print(f"  ✓ Loaded {len(dataset_index)} documents for indexing")
        print(f"  ✓ Prepared {len(dataset_experiment)} queries for testing")
        
        # Initialize result collection
        all_results = []
        param_combos = self._generate_param_combinations(iteration_params)
        print(f"  ✓ Generated {len(param_combos)} parameter combinations")
        
        try:
            # Calculate total iterations for progress bar
            total_iterations = len(search_configs_to_test) * len(param_combos) * len(models_to_test)
            print(f"\n[2/5] Testing {len(models_to_test)} models with {total_iterations} total configurations...")
            
            with tqdm(total=total_iterations, desc="Running experiments", unit="config") as pbar:
                # STEP 2: Iterate through each model
                for model_idx, model_info in enumerate(models_to_test, 1):
                    model_name = model_info['model_name']
                    model_detailed_info = " ".join(f"{v}" for k, v in model_info.items())
                    model_info_content = model_info.copy()
                    model_info_target = model_info.copy()
                    if model_info.get('split_model_kwargs'):
                        if 'index' in model_info['split_model_kwargs']:
                            model_info_content.update({"encode_kwargs" : model_info['split_model_kwargs']['index']})
                        if 'query' in model_info['split_model_kwargs']:
                            model_info_target.update({"encode_kwargs" : model_info['split_model_kwargs']['query']})
                    self.collection_manager.set_collection_name(model_name, str(json_path).split('/')[-1].split('.')[0])
                    
                    
                    print(f"\n  [{model_idx}/{len(models_to_test)}] Processing model: {model_name}")
                    
                    # STEP 3: Generate embeddings for this model
                    print(f"    → Generating embeddings...")
                    
                    # Extract texts to embed
                    content_texts = [row['page_content'] for row in dataset_index]
                    target_texts = [row[target_embed_column] for row in dataset_experiment]
                    
                    # Generate embeddings with latency tracking
                    content_embeddings, _ = self.embedding_manager.get_embeddings_with_latency(
                        "      ✓ Generating content embeddings",
                        content_texts,
                        cache_key=f"{model_name}_content",
                        **model_info_content
                    )
                    
                    target_embeddings, target_latencies = self.embedding_manager.get_embeddings_with_latency(
                        "      ✓ Generating query embeddings",
                        target_texts, 
                        cache_key=f"{model_name}_target",
                        **model_info_target
                    )
                    
                    # STEP 4: Create collection and index documents
                    print(f"    → Creating Typesense collection and indexing documents...")
                    self.collection_manager.create_and_index(
                        dataset_index, 
                        content_embeddings, 
                        model_info['dimension']
                    )
                    
                    # STEP 5: Test all search configurations and parameter combinations
                    for search_config in search_configs_to_test:
                        for eval_params in param_combos:
                            
                            # Run search test for this configuration
                            result = self._run_single_search_test(
                                dataset_experiment, 
                                target_embeddings, 
                                target_latencies, 
                                search_config, 
                                eval_params, 
                                model_name,
                                model_detailed_info
                            )
                            
                            # Create result row with all metrics
                            all_results.append(
                                self.results_processor.create_result_row(
                                    model_name=model_detailed_info,
                                    **result,
                                    eval_params=eval_params,
                                    search_config=search_config
                                )
                            )
                            pbar.set_description(
                                f"    → {model_name[:5]}..:{eval_params} -> Acc: {result['success_count']}/{result['total_rows']}"
                            )
                            pbar.update(1)
        finally:
            # CLEANUP: Always cleanup resources even if error occurs
            print("\n[3/5] Cleaning up resources...")
            self.embedding_manager.clear_cache()
            print("  ✓ Cleared embedding cache")

        # STEP 6: Save detailed results if requested
        if detailed_output_path:
            print(f"\n[4/5] Saving detailed results...")
            self._save_detailed_results(detailed_output_path)

        # STEP 7: Process and return final results
        print(f"\n[5/5] Processing final results...")
        final_results = self.results_processor.process_and_save_results(
            all_results, dataset_index, sort_accuracy, csv_output_path
        )
        
        print(f"\n{'='*60}")
        print(f"Experiment Complete!")
        print(f"{'='*60}\n")
        
        return final_results

    def _run_single_search_test(
        self, 
        dataset: List[Dict], 
        target_embeddings: List[List[float]], 
        target_latencies: List[float], 
        search_config_template: Dict, 
        eval_params: Dict, 
        model_name: str,
        detailed_model_config: str
    ) -> Dict:
        """
        Run a single search test configuration across all query rows using batched multi-search.
        
        Searches are batched in groups of 10 for better performance.
        """
        success_count = 0
        all_rf_scores = []
        success_rf_scores = []
        
        batch_size = BATCH
        total_rows = len(dataset)
        
        # Process in batches
        for batch_start in range(0, total_rows, batch_size):
            batch_end = min(batch_start + batch_size, total_rows)
            batch_indices = range(batch_start, batch_end)
            
            # Prepare all search requests for this batch
            search_requests = []
            for i in batch_indices:
                row_data = dataset[i]
                query_vec = target_embeddings[i]
                
                final_req = self._prepare_search_request(
                    search_config_template, eval_params, row_data, query_vec
                )
                search_requests.append(final_req)
            
            # Execute multi-search for the batch
            batch_results = self.collection_manager.search_batch(search_requests)
            
            # Process results for each query in the batch
            for idx, (i, hits) in enumerate(zip(batch_indices, batch_results)):
                row_data = dataset[i]
                
                # Extract information from search results
                rf_scores = []
                retrieved_docs = []
                
                for hit_idx, hit in enumerate(hits):
                    doc_info = {
                        'rank': hit_idx + 1,
                        'id': hit['document'].get('id'),
                        'text_match_score': hit.get('text_match', 0),
                        'vector_distance': hit.get('vector_distance'),
                        'hybrid_search_info': hit.get('hybrid_search_info', {}),
                    }
                    if 'hybrid_search_info' in hit:
                        hit_rf_score = float(
                            hit.get('hybrid_search_info', {}).get('rank_fusion_score', 0.0)
                        )
                        rf_scores.append(hit_rf_score)
                    
                    retrieved_docs.append(doc_info)
                
                # Check if correct document was retrieved
                is_success = False
                correct_doc_rank = None
                correct_doc_rf_score = None
                
                for hit in hits:
                    if hit['document']['id'] == row_data['id']:
                        is_success = True
                        correct_doc_rank = next(
                            (doc['rank'] for doc in retrieved_docs if doc['id'] == row_data['id']), 
                            None
                        )
                        correct_doc_rf_score = next(
                            (
                                float(
                                    doc.get('hybrid_search_info', {}).get('rank_fusion_score', 0.0)
                                ) for doc in retrieved_docs if doc['id'] == row_data['id']), 
                            None
                        )
                        break
                
                # Create detailed result entry
                average_rf_score = sum(rf_scores) / len(rf_scores) if rf_scores else None
                detailed_info = {
                    'timestamp': datetime.now().isoformat(),
                    'model': model_name,
                    'detailed_model_config': detailed_model_config,
                    'query_row_idx': i,
                    'query_id': row_data.get('id'),
                    'query_text': row_data.get("query"),
                    'page_content': row_data.get("page_content"),
                    'search_config': search_config_template,
                    'eval_params': eval_params,
                    'success': is_success,
                    'correct_doc_rank': correct_doc_rank,
                    'average_rf_score': average_rf_score,
                    'top_hit_rf_score': correct_doc_rf_score,
                    'num_results_returned': len(hits),
                    'retrieved_documents': retrieved_docs,
                    'search_request': self._sanitize_request_for_logging(search_requests[idx])
                }
                self.detailed_results.append(detailed_info)
                
                # Aggregate metrics
                if average_rf_score is not None:
                    all_rf_scores.append(average_rf_score)
                
                if is_success:
                    success_count += 1
                    if correct_doc_rf_score is not None:
                        success_rf_scores.append(correct_doc_rf_score)
        
        final =  {
            "success_count": success_count,
            "total_rows": total_rows,
            "all_rf_scores": all_rf_scores,
            "success_rf_scores": success_rf_scores,
            "per_row_latencies": target_latencies,
            "alpha": float(eval_params.get('alpha', 0.0))
        }
        return final

    def _sanitize_request_for_logging(self, request: Dict) -> Dict:
        """
        Remove or truncate large vectors from request for logging.
        
        Embedding vectors can be very large (e.g., 384-1536 dimensions).
        This method truncates them to keep logs readable.
        
        Args:
            request: Search request dictionary that may contain large vectors
            
        Returns:
            Dict: Sanitized request with truncated vectors
        """
        sanitized = copy.deepcopy(request)
        
        if 'vector_query' in sanitized and isinstance(sanitized['vector_query'], str):
            vec_str = sanitized['vector_query']
            if len(vec_str) > 200:
                # Keep first 200 chars for reference
                sanitized['vector_query'] = vec_str[:200] + '... [truncated]'
        
        return sanitized

    def _save_detailed_results(self, output_path: str):
        """
        Save detailed results to JSON or CSV file.
        
        Detailed results include:
        - Every query executed
        - Search configuration used
        - Retrieved documents with scores
        - Success/failure status
        - Timing information
        
        Args:
            output_path: Path to save file. Extension determines format:
                - .json: Full nested structure preserved
                - .csv: Flattened structure, easier for spreadsheet analysis
        """
        try:
            if output_path.endswith('.json'):
                # Save as JSON with full nested structure
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(self.detailed_results, f, indent=2)
                print(f"  ✓ Detailed results saved to {output_path}")
                print(f"    Format: JSON (nested structure)")
                print(f"    Total queries: {len(self.detailed_results)}")
                
            elif output_path.endswith('.csv'):
                # Flatten results for CSV format
                flattened = []
                for result in self.detailed_results:
                    flat_result = {
                        'timestamp': result['timestamp'],
                        'model': result['model'],
                        'detailed_model_config': json.dumps(result['detailed_model_config']),
                        'query_row_idx': result['query_row_idx'],
                        'query_id': result['query_id'],
                        'query_text': result['query_text'],
                        'page_content': result['page_content'],
                        'success': result['success'],
                        'correct_doc_rank': result['correct_doc_rank'],
                        'average_rf_score': result['average_rf_score'],
                        'average_hit_rf_score': result['top_hit_rf_score'],
                        'num_results_returned': result['num_results_returned'],
                        'eval_params': json.dumps(result['eval_params']),
                        'search_config': json.dumps(result['search_config']),
                        'retrieved_ids': json.dumps([
                            doc['id'] for doc in result['retrieved_documents']
                        ])
                    }
                    flattened.append(flat_result)
                
                # Write CSV
                if flattened:
                    with open(output_path, 'w', newline='', encoding='utf-8') as f:
                        writer = csv.DictWriter(f, fieldnames=flattened[0].keys())
                        writer.writeheader()
                        writer.writerows(flattened)
                    print(f"  ✓ Detailed results saved to {output_path}")
            else:
                print(f"  ✗ Unsupported file format for detailed results: {output_path}")
                print(f"    Supported formats: .json, .csv")
                
        except Exception as e:
            print(f"  ✗ Failed to save detailed results. Error: {e}")

    def _prepare_search_request(
        self, 
        template: Dict, 
        eval_params: Dict, 
        row_data: Dict, 
        query_vec: List[float]
    ) -> Dict:
        """
        Prepare the final search request with all parameters filled in.
        
        This involves two formatting stages:
        1. Fill in row-specific data (e.g., {title}, {question})
        2. Fill in evaluation parameters (e.g., {alpha}, {vector})
        
        Args:
            template: Search configuration template with placeholders
                Example: {'vector_query': 'vector:({vector}, k:100, alpha:{alpha})'}
            eval_params: Evaluation parameters to test
                Example: {'alpha': 0.5}
            row_data: Data from the current query row
                Example: {'id': '1', 'question': 'What is AI?'}
            query_vec: Embedding vector for the query
                Example: [0.1, 0.2, ..., 0.5] (384 dimensions)
                
        Returns:
            Dict: Complete search request ready for Typesense
        """
        # Stage 1: Format with row data placeholders
        final_req = self._format_config_placeholders(copy.deepcopy(template), row_data)
        
        # Stage 2: Format with eval params and vector
        format_params = {"vector": str(query_vec), **eval_params}
        final_req = self._format_with_eval_params(final_req, format_params)
        
        # Add collection name
        final_req["collection"] = self.collection_manager.collection_name
        
        return final_req
    
    def _format_with_eval_params(self, item: Any, format_params: Dict) -> Any:
        """
        Recursively format all string fields with eval_params.
        Also converts numeric strings to actual numbers.
        
        Example:
            Input: "alpha:{alpha}"
            format_params: {'alpha': 0.5}
            Output: "alpha:0.5" -> 0.5 (converted to float)
        
        Args:
            item: Item to format (can be str, dict, list, or other)
            format_params: Dictionary with values to substitute
            
        Returns:
            Formatted item with placeholders replaced
        """
        if isinstance(item, str):
            try:
                # Apply string formatting
                formatted = item.format(**format_params)
                
                # Try to convert to number
                try:
                    if '.' in formatted:
                        return float(formatted)
                    else:
                        return int(formatted)
                except (ValueError, AttributeError):
                    # Not a number, return as string
                    return formatted
            except (KeyError, ValueError):
                # Placeholder not found, return original
                return item
                
        elif isinstance(item, dict):
            # Recursively format dictionary values
            return {k: self._format_with_eval_params(v, format_params) for k, v in item.items()}
            
        elif isinstance(item, list):
            # Recursively format list items
            return [self._format_with_eval_params(i, format_params) for i in item]
            
        # Return other types as-is
        return item

    def _format_config_placeholders(self, item: Any, row_data: Dict) -> Any:
        """
        Recursively format config template with row data.
        Also converts numeric strings to actual numbers.
        
        Example:
            Input: "Question: {question}"
            row_data: {'question': 'What is AI?'}
            Output: "Question: What is AI?"
        
        Args:
            item: Item to format (can be str, dict, list, or other)
            row_data: Dictionary with row-specific data
            
        Returns:
            Formatted item with placeholders replaced
        """
        if isinstance(item, str):
            try: 
                # Apply string formatting
                formatted = item.format(**row_data)
                
                # Try to convert to number
                try:
                    if '.' in formatted:
                        return float(formatted)
                    else:
                        return int(formatted)
                except (ValueError, AttributeError):
                    # Not a number, return as string
                    return formatted
            except KeyError: 
                # Placeholder not found, return original
                return item
                
        elif isinstance(item, dict):
            # Recursively format dictionary values
            return {k: self._format_config_placeholders(v, row_data) for k, v in item.items()}
            
        elif isinstance(item, list):
            # Recursively format list items
            return [self._format_config_placeholders(i, row_data) for i in item]
            
        # Return other types as-is
        return item
        
    def _generate_param_combinations(self, params: Dict[str, List[Any]]) -> List[Dict]:
        """
        Generate all combinations of parameter values for grid search.
        
        Example:
            Input: {'alpha': [0.1, 0.5, 0.9], 'k': [10, 50]}
            Output: [
                {'alpha': 0.1, 'k': 10},
                {'alpha': 0.1, 'k': 50},
                {'alpha': 0.5, 'k': 10},
                {'alpha': 0.5, 'k': 50},
                {'alpha': 0.9, 'k': 10},
                {'alpha': 0.9, 'k': 50}
            ]
        
        Args:
            params: Dictionary mapping parameter names to lists of values
            
        Returns:
            List of dictionaries, each representing one parameter combination
        """
        if not params:
            return [{}]
            
        keys = list(params.keys())
        values = list(params.values())
        
        combinations = []
        for combo in itertools.product(*values):
            combinations.append(dict(zip(keys, combo)))
            
        return combinations
