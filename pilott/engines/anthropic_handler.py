from typing import Optional, Dict, Any, List
import anthropic
from .base import LLMHandler


class AnthropicHandler(LLMHandler):
    """Anthropic-specific implementation"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.client = anthropic.AsyncAnthropic(
            api_key=config.get('api_key')
        )

    async def _generate(self,
                       messages: List[Dict[str, str]],
                       tools: Optional[List[Dict]] = None) -> Dict[str, Any]:
        """Implement Anthropic API calls"""
        try:
            # Convert chat messages to Anthropic format
            formatted_messages = []
            for msg in messages:
                if msg["role"] == "system":
                    # Handle system messages according to Anthropic's recommendations
                    formatted_messages.append({
                        "role": "assistant",
                        "content": f"System instruction: {msg['content']}"
                    })
                else:
                    formatted_messages.append(msg)

            kwargs = {
                "model": self.config.get("model_name", "claude-3-opus-20240229"),
                "messages": formatted_messages,
                "max_tokens": self.config.get("max_tokens", 1024),
                "temperature": self.config.get("temperature", 0.7),
                "top_p": self.config.get("top_p", 1.0),
            }

            if tools:
                kwargs["tools"] = tools

            response = await self.client.messages.create(**kwargs)

            return {
                "content": response.content[0].text,
                "role": "assistant",
                "tool_calls": response.tool_calls if hasattr(response, 'tool_calls') else None,
                "model": response.model,
                "usage": response.usage if hasattr(response, 'usage') else None
            }

        except Exception as e:
            self.logger.error(f"Anthropic API error: {str(e)}")
            raise