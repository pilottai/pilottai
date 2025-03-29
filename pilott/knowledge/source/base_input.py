from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from datetime import datetime
import logging
from pydantic import BaseModel, Field, ConfigDict

from pilott.knowledge.storage.base_storage import DataStorage


class SourceMetadata(BaseModel):
    """Metadata for an input source"""
    source_type: str
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    tags: List[str] = Field(default_factory=list)
    description: Optional[str] = None
    properties: Dict[str, Any] = Field(default_factory=dict)


class BaseInputSource(ABC):
    """
    Abstract base class for all knowledge input sources.
    Provides common functionality for processing and storing content.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    def __init__(
        self,
        name: str,
        storage: Optional[DataStorage] = None,
        collection_name: Optional[str] = None,
        chunk_size: int = 2000,
        chunk_overlap: int = 200,
        max_retries: int = 2,
        retry_delay: int = 5,
        timeout: int = 30,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.name = name
        self.storage = storage
        self.collection_name = collection_name or name
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.timeout = timeout

        # Runtime properties
        self.chunks: List[str] = []
        self.is_connected: bool = False
        self.access_count: int = 0
        self.error_count: int = 0
        self.last_access: datetime = datetime.now()

        # Setup metadata
        self.metadata = SourceMetadata(
            source_type=self.__class__.__name__,
            **(metadata or {})
        )

        # Setup logging
        self.logger = self._setup_logger()

    def _setup_logger(self) -> logging.Logger:
        """Setup a logger for this input source"""
        logger = logging.getLogger(f"InputSource_{self.name}")
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger

    @abstractmethod
    async def connect(self) -> bool:
        """
        Establish a connection to the source.
        Returns True if successful, False otherwise.
        """
        pass

    @abstractmethod
    async def query(self, query: str) -> Any:
        """
        Query the source with the given query.
        This method should be implemented by subclasses.
        """
        pass

    @abstractmethod
    async def validate_content(self) -> bool:
        """
        Validate that the content from the source is accessible and processable.
        Returns True if valid, False otherwise.
        """
        pass

    async def add(self) -> bool:
        """
        Process content from the source, chunk it, and save it to storage.
        Returns True if successful, False otherwise.
        """
        try:
            # Validate content
            if not await self.validate_content():
                self.logger.error(f"Content validation failed for source {self.name}")
                return False

            # Process and chunk content
            await self._process_content()

            # Save to storage if available
            if self.storage and self.chunks:
                return await self._save_to_storage()

            return len(self.chunks) > 0

        except Exception as e:
            self.logger.error(f"Error adding content from source {self.name}: {str(e)}")
            self.error_count += 1
            return False

    @abstractmethod
    async def _process_content(self) -> None:
        """
        Process the content from the source and populate the chunks.
        This method should be implemented by subclasses.
        """
        pass

    async def _save_to_storage(self) -> bool:
        """Save chunks to the configured storage"""
        try:
            if not self.storage:
                raise ValueError("No storage configured")

            # Create metadata for each chunk
            chunk_metadata = [{
                "source": self.name,
                "collection": self.collection_name,
                "chunk_index": i,
                "total_chunks": len(self.chunks),
                "timestamp": datetime.now().isoformat(),
                **self.metadata.model_dump()
            } for i in range(len(self.chunks))]

            # Save to storage
            self.storage.save(self.chunks, chunk_metadata)
            return True

        except Exception as e:
            self.logger.error(f"Error saving to storage: {str(e)}")
            return False

    def _chunk_text(self, text: str) -> List[str]:
        """Split text into chunks with specified size and overlap"""
        chunks = []
        if not text:
            return chunks

        for i in range(0, len(text), self.chunk_size - self.chunk_overlap):
            chunk = text[i:i + self.chunk_size]
            if chunk:  # Skip empty chunks
                chunks.append(chunk)

        return chunks

    async def refresh(self) -> bool:
        """Refresh content from the source"""
        self.chunks = []
        return await self.add()

    def get_info(self) -> Dict[str, Any]:
        """Get information about this input source"""
        return {
            "name": self.name,
            "type": self.__class__.__name__,
            "is_connected": self.is_connected,
            "access_count": self.access_count,
            "error_count": self.error_count,
            "last_access": self.last_access.isoformat(),
            "chunk_count": len(self.chunks),
            "metadata": self.metadata.model_dump()
        }
