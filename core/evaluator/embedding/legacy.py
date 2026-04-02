# import pandas as pd
# import numpy as np
# import re
# import itertools
# import copy 
# import time
# from tqdm import tqdm
# from langchain_huggingface.embeddings import HuggingFaceEmbeddings
# from typing import List, Dict, Any, Optional


# class EmbeddingEvaluator:
#     def __init__(self, model_cache_dir: str, temp_collection_name: str, typesense_client):
#         self.typesense_client = typesense_client
#         self.temp_collection_name = temp_collection_name
#         self.model_cache_dir = model_cache_dir
#         self.models: Dict[str, HuggingFaceEmbeddings] = {}
#         self.embeddings_cache: Dict[str, Dict[str, np.ndarray]] = {}
#         self.latency_cache: Dict[str, Dict[str, List[float]]] = {}  # Track latencies per model per series
        
#         self.dataset: Optional[pd.DataFrame] = None
#         self.target_embeddings: Optional[np.ndarray] = None
#         self.current_model_info: Optional[dict] = None
#         self.current_embedding_latencies: Optional[List[float]] = None  # Per-row latencies

#     def prepare_collection(self, model_info_dict: dict, json_path: str, 
#                           page_content_template: str, target_embed_column: str = 'vector_query'):
#         self.current_model_info = model_info_dict
#         model_name = model_info_dict['name']
#         vec_dim = model_info_dict['dimension']

#         self.dataset = self._load_and_prepare_data(json_path, page_content_template, target_embed_column)
        
#         # Get embeddings with latency tracking
#         content_embeddings, content_latencies = self._get_embeddings_with_latency(model_name, self.dataset['page_content'])
#         self.target_embeddings, target_latencies = self._get_embeddings_with_latency(model_name, self.dataset[target_embed_column])
        
#         # Store the target embedding latencies for per-row tracking
#         self.current_embedding_latencies = target_latencies

#         documents_to_index = self._prepare_documents_for_indexing(content_embeddings)
#         schema_fields = self._create_dynamic_schema(self.dataset, vec_dim)
        
#         self._create_and_index_collection(schema_fields, documents_to_index)

#     def run_search_test(self, search_config_template: Dict[str, Any], 
#                        eval_params: Dict[str, Any], pbar: tqdm) -> Dict[str, Any]:
#         self._validate_collection_prepared()
        
#         total_rows = len(self.dataset)
#         success_count = 0
        
#         # Initialize metrics tracking
#         all_rank_fusion_scores = []
#         success_rank_fusion_scores = []
#         all_text_match_scores = []
#         success_text_match_scores = []
#         all_vector_scores = []
#         success_vector_scores = []
        
#         # Track per-row latencies for successful hits
#         per_row_latencies = []
        
#         model_name = self.current_model_info['name']
#         pbar.set_description(f"Testing {model_name} | {eval_params}")
        
#         for i in range(total_rows):
#             evaluation_result = self._evaluate_single_row_detailed(i, search_config_template, eval_params)
            
#             # Add the embedding latency for this row
#             row_latency = self.current_embedding_latencies[i] if self.current_embedding_latencies else 0.0
#             per_row_latencies.append(row_latency)
            
#             if evaluation_result['is_success']:
#                 success_count += 1
#                 success_rank_fusion_scores.extend(evaluation_result['success_rank_fusion_scores'])
#                 success_text_match_scores.extend(evaluation_result['success_text_match_scores'])
#                 success_vector_scores.extend(evaluation_result['success_vector_scores'])
            
#             # Collect all scores regardless of success
#             all_rank_fusion_scores.extend(evaluation_result['all_rank_fusion_scores'])
#             all_text_match_scores.extend(evaluation_result['all_text_match_scores'])
#             all_vector_scores.extend(evaluation_result['all_vector_scores'])
        
#             pbar.update(1)
            
#         return self._create_detailed_result_row(
#             success_count, total_rows, eval_params, search_config_template,
#             all_rank_fusion_scores, success_rank_fusion_scores,
#             all_text_match_scores, success_text_match_scores,
#             all_vector_scores, success_vector_scores,
#             per_row_latencies
#         )

#     def cleanup_collection(self):
#         self._delete_collection()
#         self._clear_internal_state()

#     def run_experiment(self, json_path: str, page_content_template: str, 
#                       target_embed_column: str, models_to_test: List[dict],
#                       search_configs_to_test: List[dict], iteration_params: Dict[str, List[Any]],
#                       sort_accuracy: bool = True, 
#                       csv_output_path: Optional[str] = None) -> pd.DataFrame:
#         all_results = []
#         all_param_combos = self._generate_param_combinations(iteration_params)
#         base_data_config = self._create_base_data_config(json_path, page_content_template, target_embed_column)

#         temp_dataset = self._load_and_prepare_data(json_path, page_content_template, target_embed_column)
#         num_docs = len(temp_dataset)
#         del temp_dataset
        
#         try:
#             all_results = self._run_experiment_loops(models_to_test, search_configs_to_test, 
#                                                    all_param_combos, base_data_config, num_docs)
#         finally:
#             self.cleanup_collection()

#         return self._process_results(all_results, sort_accuracy, csv_output_path)

#     def _load_and_prepare_data(self, json_path: str, page_content_template: str, 
#                           target_column: str) -> pd.DataFrame:
#         dataset = self._load_json_data(json_path)
#         self._validate_data_and_template(dataset, page_content_template, target_column)
        
#         dataset['page_content'] = self._create_page_content(dataset, page_content_template)
        
#         expanded_rows = []
#         for idx, row in dataset.iterrows():
#             target_value = row[target_column]
            
#             if isinstance(target_value, list):
#                 # If it's a list, create multiple rows with different target_embed values
#                 for list_idx, embed_value in enumerate(target_value):
#                     new_row = row.copy()
#                     new_row[target_column] = embed_value
#                     new_row['id'] = f"{idx}_{list_idx}"  # Unique ID for each expanded row
#                     new_row['original_row_idx'] = idx  # Track original row
#                     expanded_rows.append(new_row)
#             else:
#                 new_row = row.copy()
#                 new_row['id'] = str(idx)
#                 new_row['original_row_idx'] = idx
#                 expanded_rows.append(new_row)
        
#         return pd.DataFrame(expanded_rows).reset_index(drop=True)

#     def _load_json_data(self, json_path: str) -> pd.DataFrame:
#         try:
#             dataset = pd.read_json(json_path, orient='records')
#         except FileNotFoundError:
#             raise FileNotFoundError(f"The file specified at '{json_path}' was not found.")
#         except ValueError:
#             raise ValueError(f"Could not parse the JSON file at '{json_path}'. Ensure it is a valid JSON array of objects.")
        
#         if not isinstance(dataset, pd.DataFrame) or dataset.empty:
#             raise TypeError("Dataset could not be loaded into a non-empty pandas DataFrame.")
        
#         return dataset

#     def _validate_data_and_template(self, dataset: pd.DataFrame, page_content_template: str, 
#                                 target_column: str):
#         if not page_content_template or not isinstance(page_content_template, str):
#             raise ValueError("page_content_template must be a non-empty string.")
        
#         if target_column not in dataset.columns:
#             raise ValueError(f"Target column '{target_column}' not found in the dataset.")
        
#         for idx, value in enumerate(dataset[target_column]):
#             if isinstance(value, list):
#                 if not all(isinstance(item, str) for item in value):
#                     raise ValueError(f"Row {idx}: All items in {target_column} list must be strings.")
#                 if len(value) == 0:
#                     raise ValueError(f"Row {idx}: {target_column} list cannot be empty.")
#             elif not isinstance(value, str):
#                 raise ValueError(f"Row {idx}: {target_column} must be either a string or list of strings.")
        
#         page_content_cols = re.findall(r'\{(\w+)\}', page_content_template)
#         if not page_content_cols:
#             raise ValueError("No column placeholders like {column_name} found in the template.")
        
#         for col in page_content_cols:
#             if col not in dataset.columns:
#                 raise ValueError(f"Column '{col}' from template not found in the dataset.")

#     def _create_page_content(self, dataset: pd.DataFrame, page_content_template: str) -> pd.Series:
#         try:
#             return dataset.apply(lambda row: page_content_template.format(**row.to_dict()), axis=1)
#         except KeyError as e:
#             raise KeyError(f"Failed to format page_content_template. Missing key: {e}")

#     def _load_model(self, model_name: str) -> HuggingFaceEmbeddings:
#         if model_name not in self.models:
#             try:
#                 self.models[model_name] = HuggingFaceEmbeddings(
#                     model_name=model_name, 
#                     cache_folder=self.model_cache_dir
#                 )
#             except Exception as e:
#                 raise Exception(f"Error loading model {model_name}: {e}")
#         return self.models[model_name]

#     def _get_embeddings_with_latency(self, model_name: str, text_series: pd.Series) -> tuple[np.ndarray, List[float]]:
#         """Get embeddings and track latency per text item"""
#         series_name = text_series.name
        
#         # Initialize caches if needed
#         if model_name not in self.embeddings_cache:
#             self.embeddings_cache[model_name] = {}
#         if model_name not in self.latency_cache:
#             self.latency_cache[model_name] = {}
        
#         # Check if already cached
#         if series_name in self.embeddings_cache[model_name]:
#             embeddings = self.embeddings_cache[model_name][series_name]
#             latencies = self.latency_cache[model_name][series_name]
#             return embeddings, latencies
        
#         # Generate embeddings with per-item latency tracking
#         model = self._load_model(model_name)
#         text_list = text_series.tolist()
        
#         embeddings = []
#         latencies = []
        
#         for text in text_list:
#             start_time = time.time()
#             embedding = model.embed_documents([text])[0] 
#             end_time = time.time()
            
#             embeddings.append(embedding)
#             latencies.append(end_time - start_time)
        
#         embeddings_array = np.array(embeddings)
        
#         # Cache results
#         self.embeddings_cache[model_name][series_name] = embeddings_array
#         self.latency_cache[model_name][series_name] = latencies
        
#         return embeddings_array, latencies

#     def _get_embeddings(self, model_name: str, text_series: pd.Series) -> np.ndarray:
#         """Legacy method for backward compatibility"""
#         embeddings, _ = self._get_embeddings_with_latency(model_name, text_series)
#         return embeddings

#     def _prepare_documents_for_indexing(self, content_embeddings: np.ndarray) -> List[Dict]:
#         documents_to_index = self.dataset.to_dict('records')
#         for idx, doc in enumerate(documents_to_index):
#             doc['vector'] = content_embeddings[idx].tolist()
#         return documents_to_index

#     def _create_dynamic_schema(self, df: pd.DataFrame, vec_dim: int) -> List[Dict[str, Any]]:
#         schema_fields = [
#             {"name": "id", "type": "string"},
#             {"name": "vector", "type": "float[]", "num_dim": vec_dim, "index": True}
#         ]
        
#         # Always add original_row_idx if it exists (from our list expansion)
#         if 'original_row_idx' in df.columns:
#             schema_fields.append({
#                 "name": "original_row_idx", 
#                 "type": "int64", 
#                 "index": True, 
#                 "facet": False,
#                 "optional": True
#             })
        
#         done_cols = {'id', 'vector', 'original_row_idx'}
        
#         for col, dtype in df.dtypes.items():
#             if col in done_cols: 
#                 continue
            
#             field_config = self._get_field_config(col, dtype)
#             schema_fields.append(field_config)
        
#         return schema_fields

#     def _get_field_config(self, col: str, dtype) -> Dict[str, Any]:
#         base_config = {"name": col, "optional": True}
        
#         if pd.api.types.is_string_dtype(dtype) or dtype == 'object':
#             return {**base_config, "type": "string", "index": True, "facet": False}
#         elif pd.api.types.is_integer_dtype(dtype):
#             return {**base_config, "type": "int64", "index": False, "facet": True}
#         elif pd.api.types.is_float_dtype(dtype):
#             return {**base_config, "type": "float", "index": False, "facet": True}
#         elif pd.api.types.is_bool_dtype(dtype):
#             return {**base_config, "type": "bool", "index": False, "facet": True}
#         else:
#             return {**base_config, "type": "string", "index": True, "facet": False}

#     def _create_and_index_collection(self, schema_fields: List[Dict], documents_to_index: List[Dict]):
#         self.typesense_client.create_collection(
#             self.temp_collection_name, 
#             schema_fields, 
#             force_recreate=True
#         )
#         self.typesense_client.index_documents(documents_to_index, collection_name=self.temp_collection_name, show_progress=False)

#     def _validate_collection_prepared(self):
#         if self.dataset is None or self.target_embeddings is None or self.current_model_info is None:
#             raise Exception("Collection is not prepared. Please call prepare_collection() before running a test.")

#     def _evaluate_single_row_detailed(self, row_idx: int, search_config_template: Dict[str, Any], 
#                                     eval_params: Dict[str, Any]) -> Dict[str, Any]:
#         row_data = self.dataset.iloc[row_idx].to_dict()
#         ground_truth_id = row_data['id']
#         query_vec = self.target_embeddings[row_idx].tolist()
        
#         final_req = self._prepare_search_request(search_config_template, eval_params, row_data, query_vec)
#         hits = self._execute_search(final_req)
        
#         original_row_idx = row_data['original_row_idx']
        
#         # Initialize result structure
#         result = {
#             'is_success': False,
#             'all_rank_fusion_scores': [],
#             'success_rank_fusion_scores': [],
#             'all_text_match_scores': [],
#             'success_text_match_scores': [],
#             'all_vector_scores': [],
#             'success_vector_scores': []
#         }
        
#         # Process all hits to collect scores
#         for hit in hits:
#             hit_doc = hit['document']
#             hit_id = hit_doc['id']
            
#             # Extract scores from hit
#             alpha = float(eval_params.get('alpha', 0.0)) 
#             rank_fusion_score = float(hit.get('hybrid_search_info', {}).get('rank_fusion_score', 0.0))
#             vector_score = rank_fusion_score * alpha
#             text_match_score = rank_fusion_score * (1.0 - alpha)
            
#             # Add to all scores
#             result['all_rank_fusion_scores'].append(rank_fusion_score)
#             result['all_text_match_scores'].append(text_match_score)
#             result['all_vector_scores'].append(vector_score)
            
#             # Check if this hit belongs to the same original row
#             if '_' in hit_id:
#                 hit_original_idx = int(hit_id.split('_')[0])
#             else:
#                 hit_original_idx = int(hit_id)
            
#             if hit_original_idx == original_row_idx:
#                 result['is_success'] = True
#                 result['success_rank_fusion_scores'].append(rank_fusion_score)
#                 result['success_text_match_scores'].append(text_match_score)
#                 result['success_vector_scores'].append(vector_score)
        
#         return result

#     def _evaluate_single_row(self, row_idx: int, search_config_template: Dict[str, Any], 
#                         eval_params: Dict[str, Any]) -> bool:
#         # Keep the original method for backward compatibility
#         detailed_result = self._evaluate_single_row_detailed(row_idx, search_config_template, eval_params)
#         return detailed_result['is_success']

#     def _extract_vector_score(self, hit: Dict) -> float:
#         """Extract vector similarity score from hit"""
#         # This depends on your Typesense configuration
#         # You may need to adjust this based on how vector scores are returned
        
#         # Check if there's a vector_distance or similar field
#         vector_distance = hit.get('vector_distance', None)
#         if vector_distance is not None:
#             # Convert distance to similarity (assuming cosine distance: similarity = 1 - distance)
#             return 1.0 - float(vector_distance)
        
#         # Check for other possible vector score fields
#         hybrid_info = hit.get('hybrid_search_info', {})
#         vector_score = hybrid_info.get('vector_score', 0)
#         if vector_score:
#             return float(vector_score)
        
#         # If no vector score available, return 0
#         return 0.0

#     def _prepare_search_request(self, search_config_template: Dict[str, Any], 
#                                eval_params: Dict[str, Any], row_data: dict, 
#                                query_vec: List[float]) -> Dict[str, Any]:
#         final_req = copy.deepcopy(search_config_template)
#         final_req = self._format_search_config(final_req, row_data)
        
#         if "vector_query" in final_req:
#             final_req = self._format_vector_query(final_req, eval_params, query_vec)
        
#         final_req["collection"] = self.temp_collection_name
#         return final_req

#     def _format_vector_query(self, final_req: Dict[str, Any], eval_params: Dict[str, Any], 
#                             query_vec: List[float]) -> Dict[str, Any]:
#         default_format = {"vector": str(query_vec)}
#         vq_template_string = final_req["vector_query"]
        
#         for param_name, param_val in eval_params.items():
#             placeholder = "{" + param_name.lower() + "}"
#             if placeholder in vq_template_string:
#                 default_format[param_name] = param_val

#         final_req["vector_query"] = final_req["vector_query"].format(**default_format)
#         return final_req

#     def _execute_search(self, final_req: Dict[str, Any]) -> List:
#         try:
#             return self.typesense_client.multi_search(final_req)
#         except Exception as search_e:
#             print(f"Search failed for params {str(final_req)}: {search_e}")
#             return []

#     def _create_detailed_result_row(self, success_count: int, total_rows: int, 
#                                   eval_params: Dict[str, Any], search_config_template: Dict[str, Any],
#                                   all_rank_fusion_scores: List[float], success_rank_fusion_scores: List[float],
#                                   all_text_match_scores: List[float], success_text_match_scores: List[float],
#                                   all_vector_scores: List[float], success_vector_scores: List[float],
#                                   per_row_latencies: List[float]) -> Dict[str, Any]:
#         accuracy = (success_count / total_rows) * 100 if total_rows > 0 else 0
        
#         def safe_mean(scores_list):
#             return np.mean(scores_list) if scores_list else 0.0
        
#         # Calculate average latency
#         avg_latency = safe_mean(per_row_latencies) if per_row_latencies else 0.0
        
#         # Calculate composite metrics
#         avg_rf_score = safe_mean(all_rank_fusion_scores)
#         hit_rf_score = safe_mean(success_rank_fusion_scores)
        
#         # Use small epsilon to avoid division by zero
#         latency_for_scaling = max(avg_latency, 1e-9) 
#         latency_safe = np.sqrt(latency_for_scaling)
        
#         acc_avg_rf_per_latency = (accuracy * avg_rf_score) / latency_safe if avg_rf_score > 0 else 0
#         acc_hit_rf_per_latency = (accuracy * hit_rf_score) / latency_safe if hit_rf_score > 0 else 0
#         spi = (accuracy / latency_safe) if latency_safe > 0 else 0 
        
#         return {
#             'model': self.current_model_info['name'],
#             **eval_params,
#             'search_cfg': str(search_config_template),
#             'hits': success_count,
#             'total': total_rows,
#             'Accuracy Percentage': f"{accuracy:.2f}",
            
#             # Rank fusion scores
#             'Average Total RF Score': f"{avg_rf_score:.4f}",
#             'Average Hit RF Score': f"{hit_rf_score:.4f}",
            
#             # Latency metrics
#             'Average Latency (s)': f"{avg_latency:.6f}",
            
#             # Composite efficiency metrics
#             'Overall Performance Index (OPI)': f"{acc_avg_rf_per_latency:.2f}",
#             'Precision Efficiency Index (PEI)': f"{acc_hit_rf_per_latency:.2f}",
#             'Search Performance Index (SPI)': f"{spi:.2f}"
#         }

#     def _create_result_row(self, success_count: int, total_rows: int, 
#                           eval_params: Dict[str, Any], search_config_template: Dict[str, Any]) -> Dict[str, Any]:
#         # Keep the original method for backward compatibility
#         accuracy = (success_count / total_rows) * 100 if total_rows > 0 else 0
#         return {
#             'model_name': self.current_model_info['name'],
#             **eval_params,
#             'search_params': str(search_config_template),
#             'hits': success_count,
#             'total': total_rows,
#             'Accuracy Percentage': f"{accuracy:.2f}"
#         }

#     def _format_search_config(self, config_item: Any, row_data: dict) -> Any:
#         try:
#             if isinstance(config_item, str):
#                 return config_item.format(**row_data)
#             elif isinstance(config_item, dict):
#                 return {k: self._format_search_config(v, row_data) for k, v in config_item.items()}
#             elif isinstance(config_item, list):
#                 return [self._format_search_config(i, row_data) for i in config_item]
#         except Exception:
#             return config_item
#         return config_item

#     def _delete_collection(self):
#         try:
#             self.typesense_client.delete_collection(self.temp_collection_name)
#         except Exception as e:
#             print(f"Warning: Could not delete collection '{self.temp_collection_name}'. Error: {e}")

#     def _clear_internal_state(self):
#         self.dataset = None
#         self.target_embeddings = None
#         self.current_model_info = None
#         self.embeddings_cache = {}
#         self.latency_cache = {}
#         self.current_embedding_latencies = None

#     def _generate_param_combinations(self, iteration_params: Dict[str, List[Any]]) -> List[Dict]:
#         try:
#             param_names = list(iteration_params.keys())
#             param_value_lists = iteration_params.values()
#             all_param_combos = [
#                 dict(zip(param_names, combo)) 
#                 for combo in itertools.product(*param_value_lists)
#             ]
#         except Exception as e:
#             print(f"Error generating parameter combinations: {e}")
#             return [{}]

#         if not all_param_combos:
#             print("Warning: No parameter combinations generated. Check iteration_params.")
#             return [{}]
        
#         return all_param_combos

#     def _create_base_data_config(self, json_path: str, page_content_template: str, 
#                                 target_embed_column: str) -> Dict[str, str]:
#         return {
#             "json_path": json_path,
#             "page_content_template": page_content_template,
#             "target_embed_column": target_embed_column,
#         }

#     def _run_experiment_loops(self, models_to_test: List[dict], search_configs_to_test: List[dict],
#                              all_param_combos: List[Dict], base_data_config: Dict[str, str], num_docs: int) -> List[Dict]:
#         all_results = []
#         total_experiments = len(models_to_test) * len(search_configs_to_test) * len(all_param_combos) * num_docs
#         total_iterations = total_experiments 

#         with tqdm(total=total_iterations, desc="Overall Progress") as pbar:
#             for model_dict in models_to_test:
#                 self.prepare_collection(model_info_dict=model_dict, **base_data_config)
#                 for search_template in search_configs_to_test:
#                     for eval_params in all_param_combos:
#                         pbar.set_description(f"Testing {model_dict['name']} | {eval_params}")
#                         result = self._run_single_test(model_dict, search_template, eval_params, pbar)
#                         all_results.append(result)
        
#         return all_results

#     def _run_single_test(self, model_dict: dict, search_template: dict, eval_params: Dict, pbar: tqdm) -> Dict:
#         try:
#             return self.run_search_test(
#                 search_config_template=search_template,
#                 eval_params=eval_params,
#                 pbar=pbar
#             )
#         except Exception as test_e:
#             print(f"Error during search test: {test_e}. Params: {eval_params}")
#             return {
#                 'model': model_dict['name'],
#                 **eval_params,
#                 'search_cfg': str(search_template),
#                 'hits': "Error",
#                 'total': "N/A",
#                 'Accuracy Percentage': "Error",
#                 # Add error values for new metrics
#                 'Average Total RF Score': "Error",
#                 'Average Hit RF Score': "Error",
#                 'Average Latency (s)': "Error",
#                 'Overall Performance Index (OPI)': "Error",
#                 'Precision Efficiency Index (PEI)': "Error",
#                 'Search Performance Index (SPI)': "Error"
#             }

#     def _process_results(self, all_results: List[Dict], sort_accuracy: bool, csv_output_path: Optional[str] = None) -> pd.DataFrame:
#         if not all_results:
#             return pd.DataFrame()

#         results_df = pd.DataFrame(all_results)
        
#         if sort_accuracy:
#             results_df = self._sort_by_accuracy(results_df)
        
#         print("\n--- FINAL EVALUATION RESULTS ---")
#         print(results_df)
#         if csv_output_path:
#             try:
#                 results_df.to_csv(csv_output_path, index=False)
#             except Exception as e:
#                 print(f"\n--- Warning: Failed to save results to {csv_output_path}. Error: {e} ---")
#         return results_df

#     def _sort_by_accuracy(self, results_df: pd.DataFrame) -> pd.DataFrame:
#         results_df['accuracy_num'] = pd.to_numeric(results_df['Accuracy Percentage'], errors='coerce').fillna(-1)
#         results_df = results_df.sort_values(by='accuracy_num', ascending=False).drop(columns=['accuracy_num'])
#         return results_df
