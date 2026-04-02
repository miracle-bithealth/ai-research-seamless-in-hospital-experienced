# embedding_evaluator/data_handler.py

import json
import re
from typing import List, Dict, Any, Tuple

class DataHandler:
    """Handles loading, validation, and preparation of the dataset."""

    def load_and_prepare_data(self, json_path: str, page_content_template: str, 
                                target_column: str) -> Tuple[List[Dict], List[Dict]]:
        """Main method to load, validate, and transform the data."""
        dataset = self._load_json_data(json_path)
        self._validate_data_and_template(dataset, page_content_template, target_column)
        
        dataset = self._create_page_content(dataset, page_content_template)
        
        return self._expand_index_column(dataset, target_column), self._expand_experiment_column(dataset, target_column)

    def _load_json_data(self, json_path: str) -> List[Dict]:
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                dataset = json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"The file specified at '{json_path}' was not found.")
        except json.JSONDecodeError:
            raise ValueError(f"Could not parse the JSON file at '{json_path}'.")
        
        if not isinstance(dataset, list) or not dataset:
            raise TypeError("Dataset must be a non-empty list of dictionaries.")
        
        return dataset

    def _validate_data_and_template(self, dataset: List[Dict], page_content_template: str, 
                                      target_column: str):
        # Check target column exists in first row
        if not dataset or target_column not in dataset[0]:
            raise ValueError(f"Target column '{target_column}' not found in the dataset.")
        
        # Validate target column values
        for idx, row in enumerate(dataset):
            if target_column not in row:
                raise ValueError(f"Row {idx}: Missing target column '{target_column}'.")
            
            value = row[target_column]
            if isinstance(value, list):
                if not all(isinstance(item, str) for item in value) or not value:
                    raise ValueError(f"Row {idx}: {target_column} must be a non-empty list of strings.")
            elif not isinstance(value, str):
                raise ValueError(f"Row {idx}: {target_column} must be a string or a list of strings.")

        # Validate template columns
        page_content_cols = re.findall(r'\{(\w+)\}', page_content_template)
        if not page_content_cols:
            raise ValueError("No column placeholders found in the page_content_template.")
        
        for col in page_content_cols:
            if col not in dataset[0]:
                raise ValueError(f"Column '{col}' from template not found in the dataset.")

    def _create_page_content(self, dataset: List[Dict], page_content_template: str) -> List[Dict]:
        try:
            for row in dataset:
                row['page_content'] = page_content_template.format(**row)
            return dataset
        except KeyError as e:
            raise KeyError(f"Failed to format page_content_template. Missing key: {e}")

    def _expand_index_column(self, dataset: List[Dict], target_column: str) -> List[Dict]:
        """Expands rows where the target column is a list."""
        expanded_rows = []
        for idx, row in enumerate(dataset):
            new_row = row.copy()
            new_row['id'] = str(idx)
            expanded_rows.append(new_row)
        
        return expanded_rows
    
    def _expand_experiment_column(self, dataset: List[Dict], target_column: str) -> List[Dict]:
        expanded_rows = []
        for idx, row in enumerate(dataset):
            target_value = row[target_column]
            if isinstance(target_value, list):
                for list_idx, embed_value in enumerate(target_value):
                    new_row = row.copy()
                    new_row[target_column] = embed_value
                    new_row['id'] = str(idx)
                    expanded_rows.append(new_row)
            else:
                new_row = row.copy()
                new_row['id'] = str(idx)
                expanded_rows.append(new_row)
        return expanded_rows
