from config.typesenseDb import db
from typing import List
import json

def load_data() -> List[dict]:
    with open('assets/sample.json', 'r') as f:
        data = json.load(f)
    return data

def run():
    docs = load_data()
    db.create_collection(
        "products", 
        force_recreate=True,
        fields=[
            {"name": "product_id","type": "string", "facet": True},
            {"name": "product_name","type": "string",  "facet": True},
            {"name": "category","type": "string", "facet": True},
            {"name": "short_description", "type": "string"},
            {"name": "query_term","type": "string", "facet": True}]
        )
        
    db.index_documents(
        docs=docs,
        collection_name="products"
    )
    
if __name__ == "__main__":
    run()
