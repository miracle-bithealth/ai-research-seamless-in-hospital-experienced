
class MedicalSearch:
    def __init__(self, typesense_client):
        self.typesense_client = typesense_client
        
    def __call__(self, state):
        query = state.get("product_query", None)
        search_parameters = {
            'q': query,
            'query_by': 'product_name',
            'collection': "evaluator_modular_test",
            "exclude_fields" : "vector"
        }
        result_typesense = self.typesense_client.multi_search(search_parameters)
        input_item = "\n\n".join([item['document']['page_content'] for item in result_typesense])
        return {"product_info" : input_item}
