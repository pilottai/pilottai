from typing import Any, Optional
from datetime import datetime

from pilott.knowledge.source.base_input import BaseInputSource


class StringInput(BaseInputSource):
    """
    Input source for processing plain text strings.
    Implements base functionality for text content handling.
    """

    def __init__(
        self,
        name: str,
        text: Optional[str] = None,
        **kwargs
    ):
        super().__init__(name=name, **kwargs)
        self.text = text

    async def connect(self) -> bool:
        """Check if the string content is available"""
        try:
            self.is_connected = self.text is not None
            return self.is_connected
        except Exception as e:
            self.logger.error(f"Connection error: {str(e)}")
            self.is_connected = False
            return False

    async def query(self, query: str) -> Any:
        """
        Simple keyword search in the string content.
        For more advanced queries, consider using a vector store.
        """
        if not self.is_connected or not self.text:
            raise ValueError("No content available")

        self.access_count += 1
        self.last_access = datetime.now()

        # Simple search implementation
        if query.lower() in self.text.lower():
            context_size = 200  # Characters before and after match

            # Find all occurrences
            results = []
            start_idx = 0
            query_lower = query.lower()
            text_lower = self.text.lower()

            while True:
                idx = text_lower.find(query_lower, start_idx)
                if idx == -1:
                    break

                # Get context around the match
                context_start = max(0, idx - context_size)
                context_end = min(len(self.text), idx + len(query) + context_size)
                context = self.text[context_start:context_end]

                results.append({
                    "match": self.text[idx:idx + len(query)],
                    "context": context,
                    "position": idx
                })

                start_idx = idx + len(query)

            return results
        return []

    async def validate_content(self) -> bool:
        """Validate that the string content is not empty"""
        if not self.text:
            self.logger.warning(f"No text content for source {self.name}")
            return False
        return True

    async def _process_content(self) -> None:
        """Process and chunk the string content"""
        if not self.text:
            return

        self.chunks = self._chunk_text(self.text)
        self.logger.info(f"Created {len(self.chunks)} chunks from string source {self.name}")

    def set_text(self, text: str) -> None:
        """Update the text content"""
        self.text = text
        self.is_connected = text is not None
