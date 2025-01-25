from typing import Optional, Dict, Any, List
import openai
from .base import LLMHandler


class OpenAIHandler(LLMHandler):
    """OpenAI-specific implementation"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.client = openai.AsyncOpenAI(
            api_key=config.get('api_key'),
            organization=config.get('organization')
        )

    async def _generate(self,
                        messages: List[Dict[str, str]],
                        tools: Optional[List[Dict]] = None) -> Dict[str, Any]:
        """Implement OpenAI API calls"""
        try:
            kwargs = {
                "model": self.config.get("model_name", "gpt-4"),
                "messages": messages,
                "temperature": self.config.get("temperature", 0.7),
                "max_tokens": self.config.get("max_tokens"),
                "top_p": self.config.get("top_p", 1.0),
                "frequency_penalty": self.config.get("frequency_penalty", 0.0),
                "presence_penalty": self.config.get("presence_penalty", 0.0),
            }

            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = self.config.get("tool_choice", "auto")

            response = await self.client.chat.completions.create(**kwargs)

            return {
                "content": response.choices[0].message.content,
                "role": response.choices[0].message.role,
                "tool_calls": response.choices[0].message.tool_calls if hasattr(response.choices[0].message,
                                                                                'tool_calls') else None,
                "finish_reason": response.choices[0].finish_reason,
                "model": response.model,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                }
            }

        except Exception as e:
            self.logger.error(f"OpenAI API error: {str(e)}")
            raise