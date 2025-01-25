from typing import Optional, Dict, Any, List
import asyncio
from abc import ABC, abstractmethod
import logging
from datetime import datetime


class LLMHandler(ABC):
    """Abstract base class for LLM interactions"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger(f"LLMHandler_{id(self)}")
        self.last_call = datetime.min
        self._setup_logging()

    def _setup_logging(self):
        """Setup logging for LLM handler"""
        self.logger.setLevel(logging.DEBUG if self.config.get('verbose') else logging.INFO)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(
                logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            )
            self.logger.addHandler(handler)

    async def generate_response(self,
                              messages: List[Dict[str, str]],
                              tools: Optional[List[Dict]] = None) -> Dict[str, Any]:
        """Generate response from LLM with rate limiting"""
        # Implement rate limiting
        if self.config.get('max_rpm'):
            await self._handle_rate_limit()

        try:
            response = await self._generate(messages, tools)
            self.last_call = datetime.now()
            return response
        except Exception as e:
            self.logger.error(f"Error generating response: {str(e)}")
            raise

    async def _handle_rate_limit(self):
        """Handle rate limiting"""
        if self.config.get('max_rpm'):
            time_since_last = (datetime.now() - self.last_call).total_seconds()
            min_interval = 60.0 / self.config['max_rpm']
            if time_since_last < min_interval:
                await asyncio.sleep(min_interval - time_since_last)

    @abstractmethod
    async def _generate(self,
                       messages: List[Dict[str, str]],
                       tools: Optional[List[Dict]] = None) -> Dict[str, Any]:
        """Abstract method for actual LLM generation"""
        pass