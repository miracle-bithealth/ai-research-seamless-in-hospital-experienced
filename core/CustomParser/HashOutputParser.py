import inspect
import re
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union, get_args, get_origin
from langchain_core.output_parsers import BaseOutputParser
from langchain_core.exceptions import OutputParserException
from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)

class HashOutputParser(BaseOutputParser[T], Generic[T]):
    """
    A custom LangChain output parser that handles a top-level "##key: value" format
    and a specific non-JSON nested format for objects and lists.
    - Objects: {key: value, key2: value2}
    - Lists of Objects: [{...}, {...}]
    - Lists of Strings: value1, value2
    """

    pydantic_object: Type[T]

    def parse(self, text: str) -> T:
        """
        The primary method to parse the LLM's structured text output.
        """
        parsed_data: Dict[str, Any] = {}
        # Regex to find all "##key: value" pairs, handling multiline values
        pattern = r"##\s*([^:]+):\s*(.*?)(?=\s*##|$)"
        matches = re.findall(pattern, text, re.DOTALL)

        if not matches:
             raise OutputParserException(
                f"Could not parse output. No '##key: value' pairs were found in the text: {text}"
             )

        for key, value_str in matches:
            key = key.strip()
            value_str = value_str.strip()

            if key in self.pydantic_object.model_fields:
                field_info = self.pydantic_object.model_fields[key]
                try:
                    # Recursively parse the value string based on the model's type annotation
                    parsed_value = self._parse_value(value_str, field_info.annotation)
                    parsed_data[key] = parsed_value
                except Exception as e:
                    raise OutputParserException(
                        f"Failed to parse field '{key}' with value '{value_str}'.\nError: {e}"
                    ) from e
        try:
            # Validate the complete data structure against the Pydantic model
            return self.pydantic_object(**parsed_data)
        except ValidationError as e:
            raise OutputParserException(
                f"Pydantic validation failed for {self.pydantic_object.__name__}:\n{e}\nRaw Data: {parsed_data}"
            ) from e

    def get_format_instructions(self) -> str:
        """
        Generates a detailed string of formatting instructions for the LLM.
        """
        field_instructions = []
        for name, info in self.pydantic_object.model_fields.items():
            field_instructions.append(
                self._get_field_instruction(
                    name, info.annotation, info.is_required(), info.description
                )
            )

        return "\n".join(
            [
                "You are a data extraction assistant. Your ONLY job is to extract information and format it exactly as specified below.",
                "",
                "--- OUTPUT FORMAT RULES ---",
                "1. Your response MUST start directly with '##' and contain nothing else before the first '##' tag.",
                "2. Do NOT wrap the entire output in markdown code blocks (e.g., no ```).",
                "3. Each piece of information must be on its own line in the format '##key: value'.",
                "4. For nested objects, use the format {key: value, key2: value2} with NO quotes around keys or string values.",
                "5. For lists of objects, use the format [{...}, {...}].",
                "",
                "--- SCHEMA ---",
                "You must respond using the following structured text format:",
                *field_instructions,
            ]
        )

    def _parse_custom_object_string(self, obj_str: str) -> Dict[str, str]:
        """Parses a string in the format {key: value, key2: value2}."""
        obj_str = obj_str.strip()
        if not obj_str.startswith('{') or not obj_str.endswith('}'):
            raise ValueError(f"Object string must be enclosed in curly braces: {obj_str}")
        
        content = obj_str[1:-1].strip()
        if not content:
            return {}

        pairs = re.split(r',\s*(?=\w+\s*:)', content)
        
        data = {}
        for pair in pairs:
            if ':' in pair:
                key, value = pair.split(':', 1)
                data[key.strip()] = value.strip()
        return data

    def _extract_objects_from_list_string(self, list_str: str) -> List[str]:
        """Extracts each '{...}' object string from a list string '[{...}, {...}]'."""
        list_str = list_str.strip()
        if not list_str.startswith('[') or not list_str.endswith(']'):
            raise ValueError(f"List string must be enclosed in square brackets: {list_str}")
        
        content = list_str[1:-1].strip()
        
        objects = []
        brace_level = 0
        current_obj_start = -1

        for i, char in enumerate(content):
            if char == '{':
                if brace_level == 0:
                    current_obj_start = i
                brace_level += 1
            elif char == '}':
                brace_level -= 1
                if brace_level == 0 and current_obj_start != -1:
                    objects.append(content[current_obj_start : i + 1])
                    current_obj_start = -1
        return objects


    def _parse_value(self, value_str: str, field_type: Any) -> Any:
        """
        Recursively parses a string value into the correct Python data type
        using the custom non-JSON format.
        """
        origin_type = get_origin(field_type)
        type_args = get_args(field_type)

        if origin_type is Union:
            non_none_args = [arg for arg in type_args if arg is not type(None)]
            if len(non_none_args) == 1:
                if value_str.lower() in ("none", "null", ""):
                    return None
                return self._parse_value(value_str, non_none_args[0])

        if inspect.isclass(field_type) and issubclass(field_type, BaseModel):
            raw_data = self._parse_custom_object_string(value_str)
            validated_data = {}
            # Recursively parse the values of the object before validation
            for key, val_str in raw_data.items():
                if key in field_type.model_fields:
                    nested_field_type = field_type.model_fields[key].annotation
                    validated_data[key] = self._parse_value(val_str, nested_field_type)
            return field_type(**validated_data)

        if origin_type in (list, List):
            inner_type = type_args[0] if type_args else Any
            if inspect.isclass(inner_type) and issubclass(inner_type, BaseModel):
                obj_strings = self._extract_objects_from_list_string(value_str)
                return [self._parse_value(s, inner_type) for s in obj_strings]
            elif inner_type is str:
                return [item.strip() for item in value_str.split(",")]

        if field_type is bool:
            return value_str.lower() in ("true", "1", "yes", "completed")
        if field_type is int:
            return int(value_str)
        if field_type is float:
            match = re.search(r'[\d\.,]+', value_str)
            if match:
                return float(match.group().replace(',', ''))
            raise ValueError(f"Could not extract a valid float from '{value_str}'")

        return value_str

    def _get_field_instruction(
        self,
        field_name: str,
        field_type: Any,
        is_required: bool,
        description: Optional[str],
    ) -> str:
        """Generates the instruction string for a single field in the schema."""
        optional_marker = "" if is_required else " (optional)"
        type_desc = self._get_type_description(field_type)
        main_desc = description if description else ""
        
        full_description = f"{main_desc} (Format: {type_desc})".strip()

        return f"##{field_name}: <{full_description}>{optional_marker}"

    def _get_type_description(self, field_type: Any) -> str:
        """
        Generates a human-readable and machine-followable description of the custom format.
        """
        origin = get_origin(field_type)
        args = get_args(field_type)

        if origin is Union:
            non_none_types = [arg for arg in args if arg is not type(None)]
            if len(non_none_types) == 1 and type(None) in args:
                return f"Optional[{self._get_type_description(non_none_types[0])}]"

        if inspect.isclass(field_type) and issubclass(field_type, BaseModel):
            fields = ", ".join(field_type.model_fields.keys())
            return f"a quote-less object: {{{fields}}}"

        if origin in (list, List):
            item_type = args[0] if args else Any
            if inspect.isclass(item_type) and issubclass(item_type, BaseModel):
                 item_desc = self._get_type_description(item_type)
                 return f"a list of objects in the format: [{item_desc}, ...]"
            else:
                 return f"a comma-separated list of {item_type.__name__}s"

        if hasattr(field_type, "__name__"):
            return field_type.__name__

        return str(field_type)
