import typesense
import json
from tqdm import tqdm
from .setting import env
from typing import List, Union
from app.traits.HttpClientUtils import HttpClient

class TypesenseDB:
    """
    A class for interacting with Typesense database.

    This class provides functionality to create, delete, and manage collections in Typesense,
    as well as index documents with vector embeddings.

    Attributes:
        client: Typesense client instance for connecting to the database
        collection: Current active collection being operated on
        embed_model: Model name to use for generating embeddings

    Methods:
        multi_search: Property that returns the multi_search client
        validate_collection_exists: Validates if a collection exists
        check_if_collection_exists: Checks if a named collection exists
        create_collection: Creates a new collection with specified schema
        delete_collection: Deletes an existing collection
        index_documents: Indexes documents into a collection with optional embeddings
    """    
    def __init__(self, existing_collection = None, embed_model = None, config=None) -> None:
        config = config or {
            "nodes": [{
                "host": env.TYPESENSE_HOST,
                "port": env.TYPESENSE_PORT,
                "protocol": env.TYPESENSE_PROTOCOL,
                **({"path": env.TYPESENSE_PATH} if env.TYPESENSE_PATH else {})
            }],
            "api_key": env.TYPESENSE_API_KEY,
            "connection_timeout_seconds": 60,
        }
        self.client = typesense.Client(config)

        try:
            self.client.collections.retrieve()
        except Exception as e:
            raise Exception(f"Failed to connect to Typesense: {str(e)}")
            
        self.collection = None
        self.embed_model = embed_model
        if existing_collection:
            if not self.check_if_collection_exists(existing_collection):
                raise Exception(f"Collection {existing_collection} does not exist")
            self.collection = self.client.collections[existing_collection]
        
    def multi_search(
        self, 
        search_parameters: Union[List[dict], dict], 
        return_raw: bool = False,
        return_all: bool = False
        ) -> Union[List[dict], dict]:
        searches_list = [search_parameters] if isinstance(search_parameters, dict) else search_parameters
        results = self.client.multi_search.perform({"searches": searches_list}, {})
        if return_raw or not results:
            return results
        return results["results"][0].get("hits", []) if not return_all else results["results"]
      
    def validate_collection_exists(
        self, 
        collection_name: str = None
        ):
        """
        Validate if a collection exists in the Typesense database.

        Args:
            collection_name (str, optional): Name of the collection to validate.
                If not provided, uses the collection set during initialization.

        Returns:
            Collection: The validated collection object

        Raises:
            Exception: If no collection name is provided and no collection is set during initialization
        """
        if not collection_name and not self.collection:
            raise Exception("Collection name is required Either in initialization or function")
        return self.client.collections[collection_name] if collection_name else self.collection
    
    def check_if_collection_exists(
        self, 
        collection_name: str
        ) -> bool:
        """
        Check if a collection exists in the Typesense database.

        Args:
            collection_name (str): Name of the collection to check

        Returns:
            bool: True if collection exists, False otherwise

        Raises:
            typesense.exceptions.ObjectNotFound: If collection is not found
        """        
        try:
            self.client.collections[collection_name].retrieve()
            return True
        except typesense.exceptions.ObjectNotFound:
            return False
        
    def create_collection(
        self, 
        collection_name: str, 
        fields: List[dict], 
        force_recreate:bool, 
        **kwargs
        ) -> None:
        """
        Create a new collection in Typesense with the specified schema.

        Args:
            collection_name (str): Name of the collection to create
            fields (List[dict]): List of field definitions for the collection schema
            force_recreate (bool): If True, delete and recreate collection if it exists
            **kwargs: Additional keyword arguments for the collection schema

        Raises:
            Exception: If an error occurs during collection creation
        """
        if self.check_if_collection_exists(collection_name) and not force_recreate:
            raise Exception(f"Collection {collection_name} already exists")
        self.delete_collection(collection_name)

        try:
            schema = {
                "name": collection_name,
                "fields": fields,
                **kwargs
            }
            self.client.collections.create(schema)
        except Exception as e:
            raise e
        
    def delete_collection(
        self, 
        collection_name: str = None
        ) -> None:
        """
        Delete a collection from the Typesense database.

        Args:
            collection_name (str, optional): Name of the collection to delete. 
                If not provided, uses the collection set during initialization.

        Returns:
            str: Error message if deletion fails, None if successful

        Raises:
            Exception: If collection validation fails or deleting process fails
        """        
        try:
            collection = self.validate_collection_exists(collection_name)
            collection.delete()
        except typesense.exceptions.ObjectNotFound:
            pass
        except Exception as e:
            return str(e)
        
    def index_documents(
        self, 
        docs: List[dict], 
        embed_column: Union[list[str], str] = None, 
        embed_model: str = None, 
        collection_name: str = None,
        batch_size: int = 40,
        show_progress: bool = True
        ) -> None:
        """
        Index documents into a collection with optional embeddings.

        Args:
            docs (List[dict]): List of documents to index
            embed_column (Union[list[str], str], optional): Column(s) to embed.
                Can be a list of keys ['col1', 'col2'], 
                a comma-separated string of keys "col1, col2",
                or a format template string "Title: {col1}. Body: {col2}".
            embed_model (str, optional): Model name to use for generating embeddings
            collection_name (str, optional): Name of the collection to index documents into.
                If not provided, uses the collection set during initialization.

        Raises:
            Exception: If embed column is not found in the document or if an error occurs during indexing
        """
        collection = self.validate_collection_exists(collection_name)
        current_embed_model = embed_model or self.embed_model
        
        cols_to_embed = []
        template_string = None 
        
        if current_embed_model:
            if not embed_column:
                raise Exception("Embed column is required for embedding")
            
            if isinstance(embed_column, str):
                if '{' in embed_column and '}' in embed_column:
                    template_string = embed_column
                else:
                    cols_to_embed = [col.strip() for col in embed_column.split(',')]
            else:
                cols_to_embed = embed_column

        batch_docs = []
        
        doc_iterator = tqdm(docs, desc=f"Indexing to '{collection_name}'") if show_progress else docs
        for doc in doc_iterator:
            if current_embed_model:
                embed_text = None # Initialize embed_text

                if template_string:
                    try:
                        embed_text = template_string.format(**doc).strip()
                    except KeyError as e:
                        print(f"Warning: Template key {e} not found in doc ID {doc.get('id')}. Skipping embedding for this doc.")
                        continue # Skip to the next document
                
                elif cols_to_embed:
                    embed_text = " ".join(
                        [
                            str(doc.get(col, '')).lower() for col in cols_to_embed
                            if col in doc # Only join if the column actually exists
                        ]
                    ).strip()
                    
                if embed_text:
                    emb = HttpClient.get_embedding_from_api(f"{env.BASE_URL_EMBED}{current_embed_model}", embed_text)
                    doc['vector'] = emb
            
            batch_docs.append(json.dumps(doc, ensure_ascii=False))
            if len(batch_docs) >= batch_size:
                payload = '\n'.join(batch_docs).encode('utf-8')
                collection.documents.import_(payload, {'action': 'upsert'})
                batch_docs = []

        if batch_docs:
            payload = '\n'.join(batch_docs).encode('utf-8')
            collection.documents.import_(payload, {'action': 'upsert'})
            
db = TypesenseDB()
