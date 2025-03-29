import aiohttp
from typing import Any, Dict, Optional
from datetime import datetime
import re
from bs4 import BeautifulSoup

from pilott.knowledge.source.base_input import BaseInputSource


class URLInput(BaseInputSource):
    """
    Input source for processing content from URLs.
    Fetches and processes web content.
    """

    def __init__(
        self,
        name: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        extract_text_only: bool = True,
        **kwargs
    ):
        super().__init__(name=name, **kwargs)
        self.url = url
        self.headers = headers or {
            "User-Agent": "Mozilla/5.0 (compatible; PilottAI/1.0; Knowledge Fetcher)"
        }
        self.extract_text_only = extract_text_only
        self.html_content = None
        self.text_content = None

    async def connect(self) -> bool:
        """Check if the URL is accessible"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.head(
                    self.url,
                    headers=self.headers,
                    timeout=self.timeout
                ) as response:
                    self.is_connected = 200 <= response.status < 400
                    return self.is_connected
        except Exception as e:
            self.logger.error(f"Connection error for URL {self.url}: {str(e)}")
            self.is_connected = False
            return False

    async def query(self, query: str) -> Any:
        """Search for query in the processed content"""
        if not self.is_connected or not self.text_content:
            if not await self.fetch_content():
                raise ValueError(f"Could not fetch content from {self.url}")

        self.access_count += 1
        self.last_access = datetime.now()

        # Simple search implementation
        results = []
        if query.lower() in self.text_content.lower():
            context_size = 200  # Characters before and after match

            # Find all occurrences
            start_idx = 0
            query_lower = query.lower()
            text_lower = self.text_content.lower()

            while True:
                idx = text_lower.find(query_lower, start_idx)
                if idx == -1:
                    break

                # Get context around the match
                context_start = max(0, idx - context_size)
                context_end = min(len(self.text_content), idx + len(query) + context_size)
                context = self.text_content[context_start:context_end]

                results.append({
                    "match": self.text_content[idx:idx + len(query)],
                    "context": context,
                    "position": idx,
                    "url": self.url
                })

                start_idx = idx + len(query)

        return results

    async def validate_content(self) -> bool:
        """Validate that content can be fetched from the URL"""
        if not self.url:
            self.logger.warning(f"No URL specified for source {self.name}")
            return False

        return await self.fetch_content()

    async def fetch_content(self) -> bool:
        """Fetch content from the URL"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.url,
                    headers=self.headers,
                    timeout=self.timeout
                ) as response:
                    if not 200 <= response.status < 400:
                        self.logger.error(f"HTTP error {response.status} for URL {self.url}")
                        return False

                    self.html_content = await response.text()

                    if self.extract_text_only and self.html_content:
                        # Extract text from HTML
                        soup = BeautifulSoup(self.html_content, 'html.parser')

                        # Remove script and style elements
                        for script in soup(["script", "style"]):
                            script.extract()

                        # Get text and clean it up
                        self.text_content = soup.get_text(separator=' ', strip=True)

                        # Clean up whitespace
                        self.text_content = re.sub(r'\s+', ' ', self.text_content).strip()
                    else:
                        self.text_content = self.html_content

                    return bool(self.text_content)

        except Exception as e:
            self.logger.error(f"Error fetching content from URL {self.url}: {str(e)}")
            return False

    async def _process_content(self) -> None:
        """Process and chunk the content from the URL"""
        if not self.text_content:
            if not await self.fetch_content():
                return

        self.chunks = self._chunk_text(self.text_content)
        self.logger.info(f"Created {len(self.chunks)} chunks from URL {self.url}")
