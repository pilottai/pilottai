import json
from typing import Any, Dict, List, Optional, Union
from datetime import datetime

from pilott.knowledge.source.base_input import BaseInputSource


class JSONInput(BaseInputSource):
    """
    Input source for processing JSON data.
    Handles structured JSON content for knowledge extraction.
    """

    def __init__(
        self,
        name: str,
        json_data: Optional[Union[Dict, List, str]] = None,
        json_file_path: Optional[str] = None,
        key_filters: Optional[List[str]] = None,
        flatten: bool = False,
        **kwargs
    ):
        super().__init__(name=name, **kwargs)
        self.json_data = None
        self.json_file_path = json_file_path
        self.key_filters = key_filters or []
        self.flatten = flatten

        # If JSON data is provided directly
        if json_data:
            if isinstance(json_data, str):
                try:
                    self.json_data = json.loads(json_data)
                except json.JSONDecodeError as e:
                    self.logger.error(f"Invalid JSON string: {str(e)}")
            else:
                self.json_data = json_data

    async def connect(self) -> bool:
        """Check if JSON data is available or can be loaded from file"""
        if self.json_data is not None:
            self.is_connected = True
            return True

        if self.json_file_path:
            try:
                with open(self.json_file_path, 'r', encoding='utf-8') as f:
                    self.json_data = json.load(f)
                self.is_connected = True
                return True
            except Exception as e:
                self.logger.error(f"Error loading JSON from file {self.json_file_path}: {str(e)}")

        self.is_connected = False
        return False

    async def query(self, query: str) -> Any:
        """Query JSON data based on key paths or values"""
        if not self.is_connected or self.json_data is None:
            if not await self.connect():
                raise ValueError("No JSON data available")

        self.access_count += 1
        self.last_access = datetime.now()

        # Handle different query formats
        if '.' in query or '[' in query:
            # Assume it's a JSON path query
            return self._query_by_path(query)
        else:
            # Assume it's a value search
            return self._query_by_value(query)

    def _query_by_path(self, path: str) -> Any:
        """Query JSON by path notation (e.g., 'data.items[0].name')"""
        try:
            current = self.json_data
            # Handle simple dot notation
            for part in path.replace('[', '.').replace(']', '').split('.'):
                if not part:
                    continue

                if isinstance(current, dict):
                    current = current.get(part)
                elif isinstance(current, list) and part.isdigit():
                    idx = int(part)
                    if 0 <= idx < len(current):
                        current = current[idx]
                    else:
                        return None
                else:
                    return None

                if current is None:
                    break

            return current
        except Exception as e:
            self.logger.error(f"Error querying JSON by path: {str(e)}")
            return None

    def _query_by_value(self, value: str) -> List[Dict[str, Any]]:
        """Search for value in JSON data"""
        results = []

        def search_in_json(data, path=""):
            if isinstance(data, dict):
                for k, v in data.items():
                    new_path = f"{path}.{k}" if path else k

                    # Check if this value matches
                    if isinstance(v, (str, int, float)) and str(value).lower() in str(v).lower():
                        results.append({
                            "path": new_path,
                            "value": v,
                            "context": data
                        })

                    # Recursive search
                    search_in_json(v, new_path)

            elif isinstance(data, list):
                for i, item in enumerate(data):
                    new_path = f"{path}[{i}]"
                    search_in_json(item, new_path)

        search_in_json(self.json_data)
        return results

    async def validate_content(self) -> bool:
        """Validate that JSON data is available and valid"""
        if self.json_data is None:
            if not await self.connect():
                return False

        return self.json_data is not None

    async def _process_content(self) -> None:
        """Process and chunk the JSON content"""
        if self.json_data is None:
            if not await self.connect():
                return

        # Convert JSON to text representation
        if self.flatten:
            text_content = self._flatten_json(self.json_data)
        else:
            text_content = json.dumps(self.json_data, indent=2)

        self.chunks = self._chunk_text(text_content)
        self.logger.info(f"Created {len(self.chunks)} chunks from JSON source {self.name}")

    def _flatten_json(self, data, parent_key='', sep='.') -> str:
        """Flatten nested JSON into a string representation"""
        items = []

        if isinstance(data, dict):
            for k, v in data.items():
                if self.key_filters and k not in self.key_filters:
                    continue

                new_key = f"{parent_key}{sep}{k}" if parent_key else k

                if isinstance(v, (dict, list)):
                    items.append(f"{new_key}: {self._flatten_json(v, new_key, sep)}")
                else:
                    items.append(f"{new_key}: {v}")

        elif isinstance(data, list):
            for i, item in enumerate(data):
                new_key = f"{parent_key}[{i}]"

                if isinstance(item, (dict, list)):
                    items.append(f"{new_key}: {self._flatten_json(item, new_key, sep)}")
                else:
                    items.append(f"{new_key}: {item}")
        else:
            return str(data)

        return "\n".join(items)
