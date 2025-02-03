from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
import logging
import os
import asyncio
import litellm
from litellm import ModelResponse
from dotenv import load_dotenv

load_dotenv()

class LLMHandler:
    def __init__(self, config: Dict[str, Any]):
        if not isinstance(config, dict):
            raise ValueError("Config must be a dictionary")

        if not config.get("api_key"):
            raise ValueError("API key is required")

        self.config = {
            "model": config.get("model_name", "gpt-4"),
            "provider": config.get("provider", "openai"),
            "api_key": config["api_key"],
            "temperature": float(config.get("temperature", 0.7)),
            "max_tokens": int(config.get("max_tokens", 2000)),
            "max_rpm": config.get("max_rpm"),
            "retry_attempts": int(config.get("retry_attempts", 3)),
            "retry_delay": float(config.get("retry_delay", 1.0))
        }
        self.logger = logging.getLogger(f"LLMHandler_{id(self)}")
        self.last_call = datetime.min
        self.call_times = []
        self._setup_logging()
        self._setup_litellm()
        self._rate_limit_lock = asyncio.Lock()
        self._api_semaphore = asyncio.Semaphore(5)  # Limit concurrent API calls

    async def generate_response(self, messages: List[Dict[str, str]], tools: Optional[List[Dict]] = None) -> Dict[
        str, Any]:
        if not messages:
            raise ValueError("Messages cannot be empty")

        await self._rate_limit()

        kwargs = {
            "model": self.config["model"],
            "messages": messages,
            "temperature": self.config.get("temperature", 0.7),
            "max_tokens": self.config.get("max_tokens")
        }

        if tools:
            kwargs["tools"] = self._format_tools(tools)
            kwargs["tool_choice"] = "auto"

        async with self._api_semaphore:
            for attempt in range(self.config["retry_attempts"]):
                try:
                    response = await litellm.acompletion(**kwargs)
                    await self._update_rate_limit()
                    return self._process_response(response)
                except Exception as e:
                    if attempt == self.config["retry_attempts"] - 1:
                        raise
                    self.logger.warning(f"Attempt {attempt + 1} failed: {str(e)}")
                    await asyncio.sleep(self.config["retry_delay"] * (attempt + 1))

    async def _rate_limit(self):
        if not self.config.get('max_rpm'):
            return

        async with self._rate_limit_lock:
            current_time = datetime.now()
            window_start = current_time - timedelta(minutes=1)

            # Clean old calls
            self.call_times = [t for t in self.call_times if t > window_start]

            if len(self.call_times) >= self.config['max_rpm']:
                sleep_time = 60 - (current_time - self.call_times[0]).total_seconds()
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)

    async def _update_rate_limit(self):
        async with self._rate_limit_lock:
            self.last_call = datetime.now()
            self.call_times.append(self.last_call)
            if len(self.call_times) > self.config.get('max_rpm', 60):
                self.call_times.pop(0)

    def _format_tools(self, tools: List[Dict]) -> List[Dict]:
        formatted_tools = []
        for tool in tools:
            if not isinstance(tool, dict) or "name" not in tool:
                raise ValueError("Invalid tool format")
            formatted_tools.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get("parameters", {})
                }
            })
        return formatted_tools

    def _process_response(self, response: ModelResponse) -> Dict[str, Any]:
        if not response or not response.choices:
            raise ValueError("Invalid response from LLM")

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

        for key, value in self.config.items():
            if key.endswith("_api_key") and value:
                os.environ[key.upper()] = value

    def _setup_logging(self):
        self.logger.setLevel(logging.DEBUG if self.config.get('verbose') else logging.INFO)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ))
            self.logger.addHandler(handler)

    async def apredict(self, prompt: str) -> str:
        if not prompt:
            raise ValueError("Prompt cannot be empty")

        await self._rate_limit()

        kwargs = {
            "model": self.config["model"],
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.config.get("temperature", 0.7),
            "max_tokens": self.config.get("max_tokens")
        }

        async with self._api_semaphore:
            response = await litellm.acompletion(**kwargs)
            await self._update_rate_limit()
            if not response.choices:
                raise ValueError("Empty response from LLM")
            return response.choices[0].message.content

    async def apredict_messages(self, messages: List[Dict], functions: List[Dict]) -> Dict:
        if not messages:
            raise ValueError("Messages cannot be empty")

        await self._rate_limit()

        kwargs = {
            "model": self.config["model"],
            "messages": messages,
            "temperature": self.config.get("temperature", 0.7),
            "max_tokens": self.config.get("max_tokens"),
            "tools": self._format_tools(functions),
            "tool_choice": "auto"
        }

        async with self._api_semaphore:
            response = await litellm.acompletion(**kwargs)
            await self._update_rate_limit()
            return self._process_response(response)