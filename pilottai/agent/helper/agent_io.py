from typing import Optional
from pydantic import BaseModel, model_validator
import json, xml.etree.ElementTree as ET

class AgentIO(BaseModel):
    input_sample: Optional[str] = None
    output_sample: Optional[str] = None
    input_type: Optional[str] = None # auto-detected
    output_type: Optional[str] = None  # auto-detected

    @model_validator(mode="after")
    def validate_samples(self):
        # cross-field validation
        if (self.input_sample and not self.output_sample) or (self.output_sample and not self.input_sample):
            raise ValueError("Both input_sample and output_sample must be provided together.")

        # type detection
        if self.input_sample:
            self.input_type = self._detect_input_type(self.input_sample)

        return self

    @staticmethod
    def _detect_input_type(value: str) -> str:
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return "json"
            elif isinstance(parsed, list):
                return "list"
        except Exception:
            pass

        try:
            ET.fromstring(value)
            return "xml"
        except Exception:
            pass

        try:
            import yaml
            parsed = yaml.safe_load(value)
            if isinstance(parsed, (dict, list)):
                return "yaml"
        except Exception:
            pass

        return "string"

    @staticmethod
    def _detect_output_type(value: str) -> str:
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return "json"
            elif isinstance(parsed, list):
                return "list"
        except Exception:
            pass

        try:
            ET.fromstring(value)
            return "xml"
        except Exception:
            pass

        try:
            import yaml
            parsed = yaml.safe_load(value)
            if isinstance(parsed, (dict, list)):
                return "yaml"
        except Exception:
            pass

        return "string"
