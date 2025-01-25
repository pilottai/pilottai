from typing import Optional, Dict, Any, List
import google.generativeai as genai
from .base import LLMHandler


class GeminiHandler(LLMHandler):
    """Google's Gemini AI-specific implementation"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        genai.configure(api_key=config.get('api_key'))
        self.model = genai.GenerativeModel(
            model_name=config.get("model_name", "gemini-pro")
        )

    async def _generate(self,
                        messages: List[Dict[str, str]],
                        tools: Optional[List[Dict]] = None) -> Dict[str, Any]:
        """Implement Gemini API calls"""
        try:
            # Convert messages to Gemini's chat format
            chat = self.model.start_chat(
                history=[
                    (msg["role"], msg["content"])
                    for msg in messages
                    if msg["role"] != "system"
                ]
            )

            # Add system message as context if present
            system_msg = next(
                (msg["content"] for msg in messages if msg["role"] == "system"),
                None
            )

            kwargs = {
                "temperature": self.config.get("temperature", 0.7),
                "top_p": self.config.get("top_p", 1.0),
                "top_k": self.config.get("top_k", 40),
                "max_output_tokens": self.config.get("max_tokens"),
            }

            if system_msg:
                kwargs["context"] = system_msg

            if tools:
                kwargs["tools"] = tools

            response = await chat.send_message_async(**kwargs)

            return {
                "content": response.text,
                "role": "assistant",
                "tool_calls": response.tool_calls if hasattr(response, 'tool_calls') else None,
                "model": self.config.get("model_name"),
                "candidates": [
                    {
                        "content": candidate.text,
                        "safety_ratings": candidate.safety_ratings
                    }
                    for candidate in response.candidates
                ] if hasattr(response, 'candidates') else None
            }

        except Exception as e:
            self.logger.error(f"Gemini API error: {str(e)}")
            raise