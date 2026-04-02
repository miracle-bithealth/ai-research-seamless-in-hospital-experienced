# embedding_evaluator/embedding_manager.py
import tqdm
import time
from langchain_huggingface.embeddings import HuggingFaceEmbeddings
from typing import List, Dict, Tuple
from app.traits.HttpClientUtils import HttpClient

class EmbeddingManager:
    """Manages embedding model loading, generation, and caching."""

    def __init__(self, model_cache_dir: str):
        self.model_cache_dir = model_cache_dir
        self.models: Dict[str, HuggingFaceEmbeddings] = {}
        self.embeddings_cache: Dict[str, Dict[str, List[List[float]]]] = {}
        self.latency_cache: Dict[str, Dict[str, List[float]]] = {}

    def _load_model(self, model_info: dict) -> HuggingFaceEmbeddings:
        """Load or retrieve cached model."""
        if str(model_info) not in self.models:
            try:
                self.models[str(model_info)] = HuggingFaceEmbeddings(
                    cache_folder=self.model_cache_dir,
                    **{key: value for key, value in model_info.items() if key not in ['dimension', 'split_model_kwargs']}
                )
            except Exception as e:
                raise Exception(f"Error loading model {model_info.get("name")}: {e}")
        return self.models[str(model_info)]

    def get_embeddings_with_latency(
        self, 
        message: str,
        text_list: List[str], 
        cache_key: str = None,
        **model_kwargs
    ) -> Tuple[List[List[float]], List[float]]:
        """
        Get embeddings for a list of texts and track latency for each.
        
        Args:
            text_list: List of text strings to embed
            cache_key: Optional cache key. If None, uses hash of text_list
            
        Returns:
            Tuple of (embeddings, latencies)
            - embeddings: List of embedding vectors (each is a list of floats)
            - latencies: List of latency values in seconds for each embedding
        """
        model_name = str(model_kwargs)
        
        # Generate cache key if not provided
        if cache_key is None:
            cache_key = str(hash(tuple(text_list)))
        
        # Initialize cache for this model if needed
        if model_name not in self.embeddings_cache:
            self.embeddings_cache[model_name] = {}
            self.latency_cache[model_name] = {}
        
        # Return cached results if available
        if cache_key in self.embeddings_cache[model_name]:
            return (
                self.embeddings_cache[model_name][cache_key], 
                self.latency_cache[model_name][cache_key]
            )
        
        # Load model and generate embeddings
        model = self._load_model(model_kwargs) if not model_kwargs.get('url') else None
        
        embeddings = []
        latencies = []
        
        with tqdm.tqdm(total=len(text_list), desc=message, unit="data") as pbar:
            for text in text_list:
                start_time = time.time()
                embedding = model.embed_query(text) if model else HttpClient.get_embedding_from_api(model_kwargs['url'], text)
                end_time = time.time()
                
                embeddings.append(embedding)
                latencies.append(end_time - start_time)
                pbar.update(1)
                
        # Cache results
        self.embeddings_cache[model_name][cache_key] = embeddings
        self.latency_cache[model_name][cache_key] = latencies
        
        return embeddings, latencies

    def clear_cache(self):
        """Clears all cached embeddings and latencies."""
        self.embeddings_cache = {}
        self.latency_cache = {}
        
    def get_cache_stats(self) -> Dict[str, int]:
        """Get statistics about current cache usage."""
        stats = {}
        for model_name, model_cache in self.embeddings_cache.items():
            total_embeddings = sum(len(embs) for embs in model_cache.values())
            stats[model_name] = {
                'cached_sets': len(model_cache),
                'total_embeddings': total_embeddings
            }
        return stats
