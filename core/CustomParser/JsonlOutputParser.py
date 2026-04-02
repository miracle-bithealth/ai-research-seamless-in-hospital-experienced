import json
import re
from typing import Any, Dict, Generic, Type, TypeVar

from langchain_core.output_parsers import BaseOutputParser
from langchain_core.exceptions import OutputParserException
from pydantic import BaseModel, ValidationError, create_model

T = TypeVar("T", bound=BaseModel)

class JsonlOutputParser(BaseOutputParser[T], Generic[T]):
    """
    A LangChain output parser that processes a stream of JSON objects,
    one per line, and aggregates them into a single Pydantic model.
    It can handle flattened keys (e.g., "user.name", "tasks[0].description")
    and can also automatically split complex values (dicts/lists) into
    multiple flattened lines for processing.
    """

    pydantic_object: Type[T]

    def _set_nested_value(self, data_dict: Dict[str, Any], path: str, value: Any):
        """
        Sets a value in a nested dictionary/list structure based on a path.
        Handles paths like "user.name" and "tasks[0].description".
        """
        # Split path into parts, e.g., "tasks[0].description" -> ["tasks", "0", "description"]
        keys = re.findall(r'[^.\[\]]+', path)
        
        current_element = data_dict
        for i, key in enumerate(keys[:-1]):
            is_next_key_index = keys[i + 1].isdigit()

            if key.isdigit():
                # Current part is a list index
                index = int(key)
                if not isinstance(current_element, list):
                    # If we find a dict where a list should be, it's an error.
                    raise ValueError(f"Path expects a list at '{key}', but found {type(current_element)}")
                
                # Pad the list if the index is out of bounds
                while len(current_element) <= index:
                    # Append a list or dict based on what the next key is
                    current_element.append([] if is_next_key_index else {})
                current_element = current_element[index]
            else:
                # Current part is a dictionary key
                if not isinstance(current_element, dict):
                     raise ValueError(f"Path expects a dict at '{key}', but found {type(current_element)}")
                
                # Set default value if key doesn't exist
                if key not in current_element:
                    current_element[key] = [] if is_next_key_index else {}
                current_element = current_element[key]

        # Set the value at the final key
        final_key = keys[-1]
        if final_key.isdigit():
            index = int(final_key)
            if not isinstance(current_element, list):
                raise ValueError(f"Final path part expects a list, but found {type(current_element)}")
            while len(current_element) <= index:
                current_element.append(None)
            current_element[index] = value
        else:
            if not isinstance(current_element, dict):
                raise ValueError(f"Final path part expects a dict, but found {type(current_element)}")
            current_element[final_key] = value


    def parse(self, text: str) -> T:
        """
        Parses the LLM's JSON Lines output into a single Pydantic object.
        This method is robust to the LLM occasionally wrapping the output in
        markdown code fences (```json ... ```).
        """
        # Clean the text: remove markdown fences and strip whitespace.
        cleaned_text = text.strip()
        if cleaned_text.startswith("```json"):
            cleaned_text = cleaned_text[7:]
        if cleaned_text.startswith("```"):
            cleaned_text = cleaned_text[3:]
        if cleaned_text.endswith("```"):
            cleaned_text = cleaned_text[:-3]
        cleaned_text = cleaned_text.strip()

        parsed_data: Dict[str, Any] = {}
        # Use a queue-based approach to handle splitting of complex values.
        lines_to_process = [line for line in cleaned_text.split("\n") if line.strip()]
        
        if not lines_to_process:
            raise OutputParserException(
                f"Could not parse output. The text was empty or contained only whitespace: {text}"
            )
        
        line_idx = 0
        while line_idx < len(lines_to_process):
            line = lines_to_process[line_idx]
            line_idx += 1 # Increment early to avoid infinite loops

            try:
                json_obj = json.loads(line)
                
                if "key" not in json_obj or "value" not in json_obj:
                     raise OutputParserException(
                        f"Invalid JSON object on line {line_idx}. Missing 'key' or 'value'.\nLine: {line}"
                    )

                key = json_obj["key"]
                value = json_obj["value"]
                
                # If value is a dict, flatten it and add new lines to the processing queue
                if isinstance(value, dict):
                    for sub_key, sub_value in value.items():
                        new_line_obj = {"key": f"{key}.{sub_key}", "value": sub_value}
                        lines_to_process.append(json.dumps(new_line_obj))
                    continue
                
                # If value is a list, flatten it and add new lines to the processing queue
                if isinstance(value, list):
                    for i, item in enumerate(value):
                        new_line_obj = {"key": f"{key}[{i}]", "value": item}
                        lines_to_process.append(json.dumps(new_line_obj))
                    continue

                # If the value is primitive, set it in the nested structure
                self._set_nested_value(parsed_data, key, value)

            except (json.JSONDecodeError, ValueError, TypeError) as e:
                raise OutputParserException(
                    f"Failed to process line {line_idx}.\nLine: {line}\nError: {e}"
                ) from e

        try:
            # Validate the complete data structure against the Pydantic model
            return self.pydantic_object(**parsed_data)
        except ValidationError as e:
            raise OutputParserException(
                f"Pydantic validation failed for {self.pydantic_object.__name__}.\n{e}\nRaw Aggregated Data: {parsed_data}"
            ) from e

    def get_format_instructions(self) -> str:
        """
        Generates a detailed string of formatting instructions for the LLM.
        """
        # Create a dynamic Pydantic model to generate a schema for a single line
        line_schema_model = create_model(
            'LineSchema',
            key=(str, ...),
            value=(Any, ...),
        )
        line_schema = json.dumps(line_schema_model.model_json_schema(), indent=2)

        # Get the schema for the final desired Pydantic object
        pydantic_schema = json.dumps(self.pydantic_object.model_json_schema(), indent=2)


        return "\n".join(
            [
                "You are a data extraction assistant. Your ONLY job is to extract information and format it exactly as specified below.",
                "",
                "--- OUTPUT FORMAT RULES ---",
                "1. Your response MUST consist of one or more complete JSON objects, with each object on a new line (JSON Lines format).",
                "2. Do NOT wrap the entire output in a list, a single JSON object, or markdown code fences (```).",
                "3. Each line MUST be a valid JSON object structured like this:",
                line_schema,
                "4. The 'key' field must be a string. For nested data, use dot notation (e.g., \"user.name\") and for list items, use bracket notation (e.g., \"tasks[0].description\").",
                "5. The 'value' for a flattened key should be a primitive (string, number, boolean). You may also provide a full JSON object or list as a value, and it will be parsed automatically.",
                "",
                "--- FINAL DESIRED SCHEMA ---",
                "Your output will be aggregated to create a single JSON object that conforms to the following Pydantic schema:",
                pydantic_schema,
                "",
                "--- EXAMPLE ---",
                "If the final schema has fields 'project_name' and a list of 'tasks', your output could look like this:",
                '{"key": "project_name", "value": "New App"}\n{"key": "tasks[0].task_id", "value": "T-01"}\n{"key": "tasks[0].description", "value": "Design the UI"}',
            ]
        )

