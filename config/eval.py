from app.utils.CommonUtils import create_increment_list

CODE = "akmal-experiment-002"

class EvalEmbedConfig:
    """
    Configuration class for the embedding evaluator experiment.
    Holds all static settings and parameters.
    """
    @staticmethod
    def get_typesense_client():
        from config.typesenseDb import db
        return db
    
    # --- Core Paths & Names ---
    MODEL_CACHE_DIR = "E:/embeddings_cache"
    CSV_OUTPUT_PATH = f"assets/results/results_{CODE}.csv"
    DETAILED_OUTPUT_PATH = f"assets/results/detailed_results_{CODE}.csv"

    # --- Data & Embedding Setup ---
    PAGE_CONTENT_TEMPLATE = "{page_content}"
    TARGET_EMBED_COLUMN = 'query'

    # --- Iteration Lists ---
    MODELS_TO_TEST = [
        # {'model_name' : 'thenlper/gte-large', 'dimension' : 1024},
        # {'model_name' : 'Qwen/Qwen3-Embedding-0.6B', 'dimension' : 1024},
        # {'model_name' : 'paraphrase-multilingual-MiniLM-L12-v2', 'dimension' : 384},
        # {'model_name' : 'google/embeddinggemma-300m', 'dimension' : 768},
        # {'model_name' : 'intfloat/multilingual-e5-large', 'dimension' : 1024},
        
        # {
        #     'model_name' : 'Qwen/Qwen3-Embedding-0.6B', 
        #     'dimension' : 1024,
        #     'split_model_kwargs' : {
        #         "index" : {
        #             "prompt" : "Generate a concise and relevant embedding for the following text for use in vector search indexing.",
        #         },
        #         "query" : {
        #             "prompt" : "Generate a concise and relevant embedding for the following text for use in vector search query.",
        #         }
        #     }
        # }
        {'model_name' : 'google/embeddinggemma-300m', 'dimension' : 768, 'url': 'http://localhost:8002/api/embed/gemma'},
        {'model_name' : 'Qwen/Qwen3-Embedding-0.6B', 'dimension' : 1024, 'url': 'http://localhost:8002/api/embed/qwen3'},
    ]

    SEARCH_CONFIGS_TO_TEST = [
        {
            'q': "{query}",  
            'query_by': 'report_name, report_desc, report_type',
            'query_by_weights': '10,5,2',
            'vector_query': 'vector:({vector}, k:10, alpha:0.3)',
            'prefix': 'true,true,false',
            'num_typos': '2,1,0',
            'text_match_type': 'max_weight',
            'prioritize_exact_match': True,
            'prioritize_token_position': True,
            'drop_tokens_threshold': 1,
            'infix': 'fallback',
            'exclude_fields': 'vector',
            'rerank_hybrid_matches': True,
            'per_page': 10,
        },
        {
            'q': "{query}",
            'query_by': 'report_name, report_desc, report_type',
            'query_by_weights': '6,8,3',
            'vector_query': 'vector:({vector}, k:10, alpha:0.6)',
            'prefix': 'false,false,false',
            'num_typos': '2,2,1',
            'text_match_type': 'sum_score',
            'prioritize_exact_match': False,
            'prioritize_token_position': False,
            'drop_tokens_threshold': 2,
            'infix': 'fallback',
            'exclude_fields': 'vector',
            'rerank_hybrid_matches': True,
            'per_page': 10,
        },
        {
            'q': "{query}",
            'query_by': 'report_name, report_desc, report_type, related_table',
            'query_by_weights': '7,8,3,4',
            'vector_query': 'vector:({vector}, k:10, alpha:0.45)',
            'prefix': 'true,false,false,true',
            'num_typos': '1,2,1,1',
            'text_match_type': 'max_weight',
            'drop_tokens_threshold': 1,
            'infix': 'fallback',
            'rerank_hybrid_matches': True,
            'highlight_full_fields': 'report_name,report_desc',
            'highlight_affix_num_tokens': 4,
            'exclude_fields': 'vector',
            'per_page': 10,
        }
    ]

    ITERATION_PARAMS = {
        # "per_page"  : [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        # "alpha"     : [0.4, 0.5, 0.6],
    }

# class EvalEmbedConfig:
#     """
#     Configuration class for the embedding evaluator experiment.
#     Holds all static settings and parameters.
#     """
#     @staticmethod
#     def get_typesense_client():
#         from config.typesenseDb import db
#         return db
    
#     # --- Core Paths & Names ---
#     MODEL_CACHE_DIR = "E:/embeddings_cache"
#     CSV_OUTPUT_PATH = f"assets/results/results_{CODE}.csv"
#     DETAILED_OUTPUT_PATH = f"assets/results/detailed_results_{CODE}.csv"

#     # --- Data & Embedding Setup ---
#     PAGE_CONTENT_TEMPLATE = "{page_content} {keyword}"
#     TARGET_EMBED_COLUMN = 'query'

#     # --- Iteration Lists ---
#     MODELS_TO_TEST = [
#         # {'model_name' : 'thenlper/gte-large', 'dimension' : 1024},
#         # {'model_name' : 'Qwen/Qwen3-Embedding-0.6B', 'dimension' : 1024},
#         # {'model_name' : 'paraphrase-multilingual-MiniLM-L12-v2', 'dimension' : 384},
#         # {'model_name' : 'google/embeddinggemma-300m', 'dimension' : 768},
#         # {'model_name' : 'intfloat/multilingual-e5-large', 'dimension' : 1024},
        
#         # {
#         #     'model_name' : 'Qwen/Qwen3-Embedding-0.6B', 
#         #     'dimension' : 1024,
#         #     'split_model_kwargs' : {
#         #         "index" : {
#         #             "prompt" : "Generate a concise and relevant embedding for the following text for use in vector search indexing.",
#         #         },
#         #         "query" : {
#         #             "prompt" : "Generate a concise and relevant embedding for the following text for use in vector search query.",
#         #         }
#         #     }
#         # }
#         {'model_name' : 'google/embeddinggemma-300m', 'dimension' : 768, 'url': 'http://localhost:8002/api/embed/gemma'},
#         # {'model_name' : 'Qwen/Qwen3-Embedding-0.6B', 'dimension' : 1024, 'url': 'http://localhost:8002/api/embed/qwen3'},
#     ]

#     SEARCH_CONFIGS_TO_TEST = [
#         {
#             "q": "{query}",
#             "query_by": "report_name,report_desc",
#             "query_by_weights": "5,2",
#             "vector_query": "vector:({vector}, alpha: {alpha})",
#             "per_page": "{per_page}",
#             "exclude_fields": "vector",
#         },
#         {
#             "q": "{query}",
#             "query_by": "page_content,keyword",
#             "query_by_weights": "5,2",
#             "vector_query": "vector:({vector}, alpha: {alpha})",
#             "per_page": "{per_page}",
#             "exclude_fields": "vector",
#         },
#     ]

#     ITERATION_PARAMS = {
#         "per_page"  : [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
#         "alpha"     : [0.4, 0.5, 0.6],
#     }






# class EvalEmbedConfig:
#     """
#     Configuration class for the embedding evaluator experiment.
#     Holds all static settings and parameters.
#     """
#     @staticmethod
#     def get_typesense_client():
#         """Lazily imports and returns the Typesense client instance."""
#         from config.typesenseDb import db
#         return db
    
#     # --- Core Paths & Names ---
#     MODEL_CACHE_DIR = "E:/embeddings_cache"
#     CSV_OUTPUT_PATH = f"assets/results/results_{CODE}.csv"
#     DETAILED_OUTPUT_PATH = f"assets/results/detailed_results_{CODE}.csv"

#     # --- Data & Embedding Setup ---
#     PAGE_CONTENT_TEMPLATE = "Product: {product_name}. Details: {short_description}"
#     TARGET_EMBED_COLUMN = 'query'

#     # --- Iteration Lists ---
#     MODELS_TO_TEST = [
#         {'model_name' : 'google/embeddinggemma-300m', 'dimension' : 768, 'url': 'http://localhost:8002/api/embed/gemma'},
#     ]

#     SEARCH_CONFIGS_TO_TEST = [
#         {
#             "q": "{query}",
#             "query_by": "page_content",
#             "vector_query": "vector:({vector}, alpha: {alpha}, k: {k_vector}, distance_threshold: {threshold})",
#             "per_page": "{k}",
#             "exclude_fields": "vector",
#             "sort_by": "_vector_distance:asc"
#         },
#     ]

#     ITERATION_PARAMS = {
#         "k_vector" : [2],
#         "k": [1],
#         "threshold": [0.15],
#         "alpha": [0.3, 0.4],
#     }

