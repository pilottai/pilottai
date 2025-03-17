import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union

import litellm
from litellm import ModelResponse

from pilott.core.config import LLMConfig


class LLMHandler:
    """Handles LLM interactions with proper error handling"""

    def __init__(self, config: Union[LLMConfig, Dict[str, Any]]):
        if isinstance(config, dict):
            if not config.get("api_key"):
                raise ValueError("API key is required")
            self.config = {
                "model": config.get("model_name", "gpt-4"),
                "provider": config.get("provider", "openai"),
                "api_key": config["api_key"],
                "temperature": float(config.get("temperature", 0.7)),
                "max_tokens": int(config.get("max_tokens", 2000)),
                "max_rpm": config.get("max_rpm", 0),
                "retry_attempts": int(config.get("retry_attempts", 3)),
                "retry_delay": float(config.get("retry_delay", 1.0))
            }
        elif isinstance(config, LLMConfig):
            if not config.api_key:
                raise ValueError("API key is required")
            self.config = {
                "model": config.model_name,
                "provider": config.provider,
                "api_key": config.api_key,
                "temperature": float(config.temperature),
                "max_tokens": int(config.max_tokens),
                "max_rpm": config.max_rpm,  # Default to 0 if not specified
                "retry_attempts": int(config.retry_attempts),
                "retry_delay": float(config.retry_delay)
            }

        self.logger = logging.getLogger(f"LLMHandler_{id(self)}")
        self.last_call = datetime.min
        self.call_times = []
        self._setup_logging()
        self._setup_litellm()
        self._rate_limit_lock = asyncio.Lock()
        self._api_semaphore = asyncio.Semaphore(5)

    async def generate_response(
            self,
            messages: List[Dict[str, str]],
            tools: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """Generate response from LLM"""
        if not messages:
            raise ValueError("Messages cannot be empty")

        await self._rate_limit()

        kwargs = {
            "model": self.config["model"],
            "messages": messages,
            "temperature": self.config["temperature"],
            "max_tokens": self.config["max_tokens"]
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
        """Handle rate limiting"""
        if self.config["max_rpm"] > 0:  # Only rate limit if max_rpm is set
            async with self._rate_limit_lock:
                current_time = datetime.now()
                window_start = current_time - timedelta(minutes=1)

                # Clean old calls
                self.call_times = [t for t in self.call_times if t > window_start]

                if len(self.call_times) >= self.config["max_rpm"]:
                    sleep_time = 60 - (current_time - self.call_times[0]).total_seconds()
                    if sleep_time > 0:
                        await asyncio.sleep(sleep_time)

    async def _update_rate_limit(self):
        """Update rate limit tracking"""
        if self.config["max_rpm"] > 0:
            async with self._rate_limit_lock:
                self.last_call = datetime.now()
                self.call_times.append(self.last_call)
                if len(self.call_times) > self.config["max_rpm"]:
                    self.call_times.pop(0)

    def _format_tools(self, tools: List[Dict]) -> List[Dict]:
        """Format tools for LLM API"""
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
        """Process LLM response"""
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

    def _setup_logging(self):
        """Setup logging"""
        self.logger.setLevel(logging.INFO)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ))
            self.logger.addHandler(handler)

    def _setup_litellm(self):
        """Setup litellm configuration"""
        litellm.drop_params = True
        litellm.set_verbose = False
