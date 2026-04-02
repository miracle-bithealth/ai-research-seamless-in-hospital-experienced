# embedding_evaluator/results_processor.py

import statistics
import math
import csv
from typing import List, Dict, Any, Optional
import json
from .agent import Analyst
from app.generative import manager

class ResultsProcessor:
    """Handles the processing, formatting, and saving of evaluation results."""

    def create_result_row(self, model_name: str, success_count: int, total_rows: int,
                          eval_params: Dict[str, Any], search_config: Dict,
                          all_rf_scores: List[float], success_rf_scores: List[float],
                          per_row_latencies: List[float], alpha: float) -> Dict[str, Any]:
        """Creates a single detailed row for the results DataFrame."""
        accuracy = (success_count / total_rows) * 100 if total_rows > 0 else 0
        
        def safe_mean(scores: List[float]) -> float:
            return statistics.mean(scores) if scores else 0.0

        avg_latency = safe_mean(per_row_latencies)
        avg_rf_score = safe_mean(all_rf_scores)
        hit_rf_score = safe_mean(success_rf_scores)
        
        latency_safe = math.sqrt(max(avg_latency, 1e-9))
        
        return {
            'model': model_name,
            **eval_params,
            'search_cfg': str(search_config),
            'hits': success_count,
            'total': total_rows,
            'Accuracy Percentage': f"{accuracy:.2f}",
            'Average Total RF Score': f"{avg_rf_score:.4f}",
            'Average Hit RF Score': f"{hit_rf_score:.4f}",
            'Average Latency (s)': f"{avg_latency:.6f}",
            'Overall Performance Index (OPI)': f"{(accuracy * avg_rf_score) / latency_safe:.2f}",
            'Precision Efficiency Index (PEI)': f"{(accuracy * hit_rf_score) / latency_safe:.2f}",
            'Search Performance Index (SPI)': f"{accuracy / latency_safe:.2f}"
        }

    def process_and_save_results(self, all_results: List[Dict], dataset: List[Dict], 
                                 sort_by_accuracy: bool, csv_output_path: Optional[str] = None) -> List[Dict]:
        """Converts results to a list, sorts, prints, and saves them."""
        if not all_results:
            return []

        results = all_results.copy()
        if sort_by_accuracy:
            try:
                results = sorted(results, 
                               key=lambda x: float(x.get('Accuracy Percentage', '0')), 
                               reverse=True)
            except (ValueError, TypeError):
                pass
        
        print("\n--- FINAL EVALUATION RESULTS ---")
        self._print_table(results)
        
        if csv_output_path:
            try:
                self._save_to_csv(results, csv_output_path)
                print(f"\nResults saved to {csv_output_path}")
            except Exception as e:
                print(f"\n--- Warning: Failed to save results. Error: {e} ---")

        print("\n--- METRICS ---")
        print("SPI (Search Performance Index) \nThe pure trade-off between accuracy and speed. It answers: 'How much accuracy do I get for the time spent?' It doesn't care about the quality or relevance of the results, only whether the search was a success ('hit').\n\n OPI (Overall Performance Index) \nThe best all-around performance. It balances accuracy, speed, and the overall relevance of the search results (both hits and misses). This is a great general-purpose metric to find a model that is fast, accurate, and provides good quality results on average.\n\nPEI (Precision Efficiency Index) \n The efficiency of delivering high-quality 'hits'. It focuses on accuracy, speed, and the relevance of only the successful results. This index answers: 'When the model is correct, how good and fast are its answers?'")
        
        agent = Analyst(llm=manager.gemini_regular())
        print("\n--- ANALYSIS OF RESULTS ---")
        agent(results, dataset).pretty_print()
                
        return results
    
    def _print_table(self, results: List[Dict]):
        """Print results in a formatted table."""
        if not results:
            return
        
        # Get all unique keys
        all_keys = []
        for row in results:
            for key in row.keys():
                if key not in all_keys:
                    all_keys.append(key)
        
        # Print header
        header = " | ".join(all_keys)
        print(header)
        print("-" * len(header))
        
        # Print rows
        for row in results:
            values = [str(row.get(key, '')) for key in all_keys]
            print(" | ".join(values))
    
    def _save_to_csv(self, results: List[Dict], output_path: str):
        """Save results to CSV file."""
        if not results:
            return
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            # Get all unique keys
            all_keys = []
            for row in results:
                for key in row.keys():
                    if key not in all_keys:
                        all_keys.append(key)
            
            writer = csv.DictWriter(f, fieldnames=all_keys)
            writer.writeheader()
            writer.writerows(results)
    
    def analyze_failures(self, detailed_results_path: str, output_path: Optional[str] = None):
        """Analyze failed queries from detailed results."""
        with open(detailed_results_path, 'r') as f:
            detailed_results = json.load(f)
        
        failures = [r for r in detailed_results if not r['success']]
        
        if not failures:
            print("No failures to analyze!")
            return
        
        print(f"\n--- FAILURE ANALYSIS ---")
        print(f"Total failures: {len(failures)} out of {len(detailed_results)} queries")
        
        # Group failures by configuration
        failure_by_config = {}
        for failure in failures:
            config_key = (
                failure['model'],
                json.dumps(failure['eval_params'], sort_keys=True),
                json.dumps(failure['search_config'], sort_keys=True)
            )
            if config_key not in failure_by_config:
                failure_by_config[config_key] = []
            failure_by_config[config_key].append(failure)
        
        print(f"\nFailures grouped by {len(failure_by_config)} unique configurations")
        
        # Analyze each configuration
        for idx, (config_key, config_failures) in enumerate(failure_by_config.items(), 1):
            model, params, search_cfg = config_key
            print(f"\n--- Configuration {idx} ---")
            print(f"Model: {model}")
            print(f"Params: {params}")
            print(f"Failures: {len(config_failures)}")
            
            # Show sample failures
            print("\nSample failed queries:")
            for failure in config_failures[:3]:
                print(f"  - Query ID: {failure['query_id']}")
                print(f"    Query: {failure['query_text'][:100]}...")
                print(f"    Top retrieved: {[doc['id'] for doc in failure['retrieved_documents'][:3]]}")
                print(f"    Correct doc rank: {failure['correct_doc_rank']}")
        
        if output_path:
            failure_summary = {
                'total_failures': len(failures),
                'failure_rate': len(failures) / len(detailed_results),
                'failures_by_config': [
                    {
                        'model': config_key[0],
                        'params': json.loads(config_key[1]),
                        'search_config': json.loads(config_key[2]),
                        'failure_count': len(config_failures),
                        'sample_failures': config_failures[:5]
                    }
                    for config_key, config_failures in failure_by_config.items()
                ]
            }
            
            with open(output_path, 'w') as f:
                json.dump(failure_summary, f, indent=2)
            print(f"\nFailure analysis saved to {output_path}")
