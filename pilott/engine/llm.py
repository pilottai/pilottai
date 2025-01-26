from typing import Any, Dict, List, Optional
from datetime import datetime
import logging
import os
import asyncio
import litellm
from litellm import ModelResponse
from dotenv import load_dotenv

load_dotenv()

class LLMHandler:
    def __init__(self, config: Dict[str, Any]):
        self.config = {
            "model": config.get("model_name", "gpt-4"),
            "provider": config.get("provider", "openai"),
            "api_key": config.get("api_key", ""),
            "temperature": float(config.get("temperature", 0.7)),
            "max_tokens": int(config.get("max_tokens", 2000)),
            "max_rpm": config.get("max_rpm"),
        }
        self.logger = logging.getLogger(f"LLMHandler_{id(self)}")
        self.last_call = datetime.min
        self._setup_logging()
        self._setup_litellm()

    async def generate_response(self,
                                messages: List[Dict[str, str]],
                                tools: Optional[List[Dict]] = None) -> Dict[str, Any]:
        if self.config.get('max_rpm'):
            await self._handle_rate_limit()

        try:
            kwargs = {
                "model": self.config["model"],
                "messages": messages,
                "temperature": self.config.get("temperature", 0.7),
                "max_tokens": self.config.get("max_tokens"),
            }

            if tools:
                kwargs["tools"] = self._format_tools(tools)
                kwargs["tool_choice"] = "auto"

            response = await litellm.acompletion(**kwargs)
            self.last_call = datetime.now()

            return self._process_response(response)

        except Exception as e:
            self.logger.error(f"LLM generation error: {str(e)}")
            raise

    def _format_tools(self, tools: List[Dict]) -> List[Dict]:
        return [{
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool.get("parameters", {})
            }
        } for tool in tools]

    def _process_response(self, response: ModelResponse) -> Dict[str, Any]:
        return {
            "content": response.choices[0].message.content,
            "role": response.choices[0].message.role,
            "tool_calls": getattr(response.choices[0].message, "tool_calls", None),
            "model": response.model,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }
        }

    async def _handle_rate_limit(self):
        if self.config.get('max_rpm'):
            time_since_last = (datetime.now() - self.last_call).total_seconds()
            min_interval = 60.0 / self.config['max_rpm']
            if time_since_last < min_interval:
                await asyncio.sleep(min_interval - time_since_last)

    def _setup_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Setup provider-specific configurations"""
        provider_configs = {
            "azure": {
                "api_version": "2024-02-15-preview",
                "base_url": config.get("azure_endpoint"),
                "api_key": config.get("azure_api_key"),
            },
            "aws": {
                "aws_access_key_id": config.get("aws_access_key_id"),
                "aws_secret_access_key": config.get("aws_secret_access_key"),
                "aws_region_name": config.get("aws_region", "us-east-1"),
            },
            "mistral": {
                "api_key": config.get("mistral_api_key"),
            },
            "groq": {
                "api_key": config.get("groq_api_key"),
            },
            "ollama": {
                "base_url": config.get("ollama_base_url", "http://localhost:11434"),
            }
        }

        provider = config.get("provider", "openai")
        provider_config = provider_configs.get(provider, {})

        return {
            **config,
            **provider_config,
            "model": config.get("model_name", "gpt-4"),
            "temperature": config.get("temperature", 0.7),
            "max_tokens": config.get("max_tokens", 4096)
        }

    def _setup_litellm(self):
        litellm.drop_params = True
        litellm.set_verbose = False

        if self.config.get("api_key"):
            os.environ["OPENAI_API_KEY"] = self.config["api_key"]

        # Set API keys from environment
        os.environ["OPENAI_API_KEY"] = self.config.get("api_key", "")
        for key, value in self.config.items():
            if key.endswith("_api_key") and value:
                os.environ[key.upper()] = value

    def _setup_logging(self):
        self.logger.setLevel(logging.DEBUG if self.config.get('verbose') else logging.INFO)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(
                logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            )
            self.logger.addHandler(handler)