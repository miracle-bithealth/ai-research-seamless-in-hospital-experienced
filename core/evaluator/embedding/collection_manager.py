# embedding_evaluator/collection_manager.py

from typing import List, Dict, Any

class CollectionManager:
    """Manages all interactions with the Typesense collection."""
    
    def __init__(self, typesense_client):
        self.client = typesense_client
        self.collection_name = None
        
    def set_collection_name(self, embedding_model: str, dataset_name: str):
        embedding_model_name = embedding_model.replace("/", "_").replace("-", "_")
        self.collection_name = f"temp_{embedding_model_name}_{dataset_name}"

    def cleanup_temp_collections(self):
        try:
            collections = self.client.client.collections.retrieve()
            temp_collections = [col['name'] for col in collections if col['name'].startswith('temp_')]
            
            deleted_count = 0
            for collection_name in temp_collections:
                try:
                    self.client.delete_collection(collection_name)
                    deleted_count += 1
                    print(f"Deleted collection: {collection_name}")
                except Exception as e:
                    print(f"Failed to delete collection '{collection_name}': {e}")
            
            print(f"Successfully deleted {deleted_count} out of {len(temp_collections)} temp collections")
            return deleted_count
            
        except Exception as e:
            print(f"Failed to retrieve collections: {e}")
            return 0

    def create_and_index(self, data: List[Dict], content_embeddings: List[List[float]], vec_dim: int):
        """Creates a new collection and indexes documents."""
        if self.client.check_if_collection_exists(self.collection_name):
            print(f"      ✓ Collection already exists, skipping indexing")
            return

        schema_fields = self._create_dynamic_schema(data, vec_dim)
        documents = self._prepare_documents(data, content_embeddings)
        self.client.create_collection(
            self.collection_name, 
            schema_fields, 
            force_recreate=True
        )
        self.client.index_documents(documents, collection_name=self.collection_name, show_progress=False)
        print(f"      ✓ Indexed {len(data)} documents")

    def search(self, search_request: Dict[str, Any]) -> List[Dict]:
        """Executes a single search query."""
        try:
            return self.client.multi_search(search_request, return_all=True)
        except Exception as e:
            print(f"Search failed for params {str(search_request)}: {e}")
            return []

    def search_batch(self, search_requests: List[Dict[str, Any]]) -> List[List[Dict]]:
        """
        Executes multiple search queries in a single multi-search request.
        
        Args:
            search_requests: List of search request dictionaries
            
        Returns:
            List of search results, one list per query
        """
        try:
            # Execute multi-search with all requests
            results = self.client.multi_search(search_requests, return_all=True)
            
            # Extract hits from each result
            batch_hits = []
            for result in results:
                hits = result.get('hits', [])
                batch_hits.append(hits)
            
            return batch_hits
            
        except Exception as e:
            print(f"Batch search failed: {e}")
            # Return empty results for all queries in batch
            return [[] for _ in search_requests]

    def cleanup(self):
        """Deletes the collection."""
        try:
            self.client.delete_collection(self.collection_name)
        except Exception as e:
            print(f"Warning: Could not delete collection '{self.collection_name}'. Error: {e}")

    def _prepare_documents(self, data: List[Dict], content_embeddings: List[List[float]]) -> List[Dict]:
        documents = []
        for idx, doc in enumerate(data):
            doc_copy = doc.copy()
            doc_copy['vector'] = content_embeddings[idx]
            documents.append(doc_copy)
        return documents

    def _create_dynamic_schema(self, data: List[Dict], vec_dim: int) -> List[Dict[str, Any]]:
        schema_fields = [
            {"name": "id", "type": "string"},
            {"name": "vector", "type": "float[]", "num_dim": vec_dim, "index": True}
        ]
        
        if not data:
            return schema_fields
        
        # Infer types from first non-null value in each column
        done_cols = {'id', 'vector'}
        sample_doc = data[0]
        
        for col in sample_doc.keys():
            if col not in done_cols:
                # Find first non-null value for this column
                col_value = None
                for doc in data:
                    if col in doc and doc[col] is not None:
                        col_value = doc[col]
                        break
                
                if col_value is not None:
                    schema_fields.append(self._get_field_config(col, col_value))
                else:
                    # Default to string if no non-null value found
                    schema_fields.append({"name": col, "type": "string", "optional": True, "index": True, "facet": False})
        
        return schema_fields

    def _get_field_config(self, col: str, sample_value: Any) -> Dict[str, Any]:
        base_config = {"name": col, "optional": True}
        
        if isinstance(sample_value, str):
            return {**base_config, "type": "string", "index": True, "facet": False}
        elif isinstance(sample_value, bool):
            return {**base_config, "type": "bool", "index": False, "facet": True}
        elif isinstance(sample_value, int):
            return {**base_config, "type": "int64", "index": False, "facet": True}
        elif isinstance(sample_value, float):
            return {**base_config, "type": "float", "index": False, "facet": True}
        elif isinstance(sample_value, dict):
            return {**base_config, "type": "object", "index": False, "facet": False}
        elif isinstance(sample_value, list):
            if not sample_value:
                return {**base_config, "type": "string[]", "index": True, "facet": True}
            
            first_elem = sample_value[0]
            if isinstance(first_elem, str):
                return {**base_config, "type": "string[]", "index": True, "facet": True}
            elif isinstance(first_elem, dict):
                return {**base_config, "type": "object[]", "index": False, "facet": False}
            elif isinstance(first_elem, (list, tuple)) and len(first_elem) == 2:
                # Geopoint check
                if all(isinstance(x, (int, float)) for x in first_elem):
                    return {**base_config, "type": "geopoint[]", "index": True, "facet": False}
            
            return {**base_config, "type": "string[]", "index": True, "facet": True}
        
        return {**base_config, "type": "string", "index": True, "facet": False}
