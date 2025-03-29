import asyncio
import time
from typing import Any, Dict, List, Optional, Union, Callable, Awaitable
from datetime import datetime
import json
import threading
from collections import deque

from pilott.knowledge.source.base_input import BaseInputSource


class StreamInput(BaseInputSource):
    """
    Input source for processing streaming data.
    Handles continuous data streams and real-time processing.
    """

    def __init__(
        self,
        name: str,
        stream_callback: Optional[Callable[[], Union[str, bytes, Dict, None]]] = None,
        async_callback: Optional[Callable[[], Awaitable[Union[str, bytes, Dict, None]]]] = None,
        stream_type: str = "text",  # text, json, binary
        buffer_size: int = 1000,
        processing_interval: float = 1.0,  # seconds
        batch_size: int = 10,
        auto_start: bool = False,
        custom_processor: Optional[Callable[[Any], str]] = None,
        **kwargs
    ):
        super().__init__(name=name, **kwargs)
        self.stream_callback = stream_callback
        self.async_callback = async_callback
        self.stream_type = stream_type.lower()
        self.buffer_size = max(10, buffer_size)
        self.processing_interval = processing_interval
        self.batch_size = batch_size
        self.custom_processor = custom_processor

        # Storage
        self.buffer = deque(maxlen=buffer_size)
        self.processed_data = deque(maxlen=buffer_size)
        self.text_content = ""

        # Streaming state
        self.running = False
        self.worker_thread = None
        self.worker_task = None
        self.last_processed = 0
        self.total_items_processed = 0
        self.stats = {
            "start_time": None,
            "items_processed": 0,
            "batches_processed": 0,
            "errors": 0,
            "last_error": None,
            "average_processing_time": 0
        }

        # Start worker if requested
        if auto_start:
            self.start()

    async def connect(self) -> bool:
        """Check if the streaming source is accessible"""
        try:
            # For streaming sources, connection is established by starting the worker
            if self.running:
                self.is_connected = True
                return True

            # Test if callback works
            if self.stream_callback:
                test_result = self.stream_callback()
                self.is_connected = test_result is not None
            elif self.async_callback:
                test_result = await self.async_callback()
                self.is_connected = test_result is not None
            else:
                self.logger.error("No stream callback provided")
                self.is_connected = False

            return self.is_connected

        except Exception as e:
            self.logger.error(f"Connection error: {str(e)}")
            self.is_connected = False
            return False

    def start(self) -> bool:
        """Start the streaming worker"""
        if self.running:
            self.logger.warning("Stream worker already running")
            return True

        try:
            self.stats["start_time"] = datetime.now()

            if self.async_callback:
                # Use asyncio worker for async callbacks
                self.worker_task = asyncio.create_task(self._async_worker())
            else:
                # Use threading for sync callbacks
                self.worker_thread = threading.Thread(
                    target=self._worker,
                    daemon=True
                )
                self.worker_thread.start()

            self.running = True
            self.is_connected = True
            self.logger.info(f"Stream worker started for {self.name}")
            return True

        except Exception as e:
            self.logger.error(f"Error starting stream worker: {str(e)}")
            return False

    def stop(self) -> bool:
        """Stop the streaming worker"""
        if not self.running:
            return True

        try:
            self.running = False

            # Wait for thread/task to terminate
            if self.worker_thread and self.worker_thread.is_alive():
                self.worker_thread.join(timeout=5.0)

            if self.worker_task and not self.worker_task.done():
                self.worker_task.cancel()

            self.logger.info(f"Stream worker stopped for {self.name}")
            return True

        except Exception as e:
            self.logger.error(f"Error stopping stream worker: {str(e)}")
            return False

    def _worker(self) -> None:
        """Synchronous worker thread for processing stream data"""
        while self.running:
            try:
                # Call the stream callback
                if self.stream_callback:
                    data = self.stream_callback()
                    if data is not None:
                        self._process_item(data)

                # Process batches at regular intervals
                current_time = time.time()
                if current_time - self.last_processed >= self.processing_interval:
                    self._process_batch()
                    self.last_processed = current_time

                # Avoid CPU spinning
                time.sleep(min(0.1, self.processing_interval / 10))

            except Exception as e:
                self.stats["errors"] += 1
                self.stats["last_error"] = str(e)
                self.logger.error(f"Stream worker error: {str(e)}")
                time.sleep(1.0)  # Sleep longer on error

    async def _async_worker(self) -> None:
        """Asynchronous worker for processing stream data"""
        while self.running:
            try:
                # Call the async callback
                if self.async_callback:
                    data = await self.async_callback()
                    if data is not None:
                        self._process_item(data)

                # Process batches at regular intervals
                current_time = time.time()
                if current_time - self.last_processed >= self.processing_interval:
                    self._process_batch()
                    self.last_processed = current_time

                # Yield control to other tasks
                await asyncio.sleep(min(0.1, self.processing_interval / 10))

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.stats["errors"] += 1
                self.stats["last_error"] = str(e)
                self.logger.error(f"Async stream worker error: {str(e)}")
                await asyncio.sleep(1.0)  # Sleep longer on error

    def _process_item(self, data: Any) -> None:
        """Process a single item from the stream"""
        try:
            # Add to buffer
            self.buffer.append(data)

            # Convert data to text representation
            if self.custom_processor:
                # Use custom processor if provided
                text = self.custom_processor(data)
            else:
                # Use default processor based on stream type
                if self.stream_type == "text":
                    text = str(data)
                elif self.stream_type == "json":
                    if isinstance(data, (dict, list)):
                        text = json.dumps(data)
                    elif isinstance(data, str):
                        # Assume it's already JSON
                        text = data
                    elif isinstance(data, bytes):
                        # Assume JSON bytes
                        text = data.decode("utf-8")
                    else:
                        text = str(data)
                elif self.stream_type == "binary":
                    if isinstance(data, bytes):
                        # Just indicate that binary data was received
                        text = f"[Binary data received: {len(data)} bytes]"
                    else:
                        text = str(data)
                else:
                    text = str(data)

            # Add processed text
            self.processed_data.append(text)

        except Exception as e:
            self.logger.error(f"Error processing stream item: {str(e)}")

    def _process_batch(self) -> None:
        """Process a batch of items from the buffer"""
        if not self.processed_data:
            return

        try:
            start_time = time.time()

            # Get batch of items to process
            batch_size = min(self.batch_size, len(self.processed_data))
            if batch_size <= 0:
                return

            batch = list(self.processed_data)[-batch_size:]

            # Update text content with latest batch
            if self.text_content:
                self.text_content = f"{self.text_content}\n\n" + "\n".join(batch)
            else:
                self.text_content = "\n".join(batch)

            # Update chunks if content has changed
            self.chunks = self._chunk_text(self.text_content)

            # Update stats
            processing_time = time.time() - start_time
            self.stats["items_processed"] += batch_size
            self.stats["batches_processed"] += 1
            self.total_items_processed += batch_size

            # Update average processing time
            if self.stats["batches_processed"] == 1:
                self.stats["average_processing_time"] = processing_time
            else:
                self.stats["average_processing_time"] = (self.stats["average_processing_time"] *
                                                         (self.stats["batches_processed"] - 1) + processing_time
                                                         ) / self.stats["batches_processed"]

        except Exception as e:
            self.stats["errors"] += 1
            self.stats["last_error"] = str(e)
            self.logger.error(f"Error processing batch: {str(e)}")

    async def query(self, query: str) -> Any:
        """Search for query in the processed content"""
        if not self.is_connected and not self.running:
            if not await self.connect():
                await self.start()

        self.access_count += 1
        self.last_access = datetime.now()

        # Handle special commands
        if query.lower() == "stats":
            return self.get_stats()

        if query.lower() == "latest":
            return self.get_latest()

        if query.lower().startswith("batch:"):
            try:
                batch_size = int(query.split(":", 1)[1])
                return self.get_latest(batch_size)
            except ValueError:
                return {"error": "Invalid batch size"}

        # Simple search implementation
        results = []
        if self.text_content and query.lower() in self.text_content.lower():
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
                    "position": idx
                })

                start_idx = idx + len(query)

        return results

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the stream processing"""
        uptime = None
        if self.stats["start_time"]:
            uptime = (datetime.now() - self.stats["start_time"]).total_seconds()

        return {
            "running": self.running,
            "connected": self.is_connected,
            "buffer_size": len(self.buffer),
            "buffer_capacity": self.buffer_size,
            "processed_data_count": len(self.processed_data),
            "total_items_processed": self.total_items_processed,
            "uptime_seconds": uptime,
            "processing_stats": {
                "items_processed": self.stats["items_processed"],
                "batches_processed": self.stats["batches_processed"],
                "errors": self.stats["errors"],
                "last_error": self.stats["last_error"],
                "average_processing_time": self.stats["average_processing_time"]
            }
        }

    def get_latest(self, count: int = 10) -> List[str]:
        """Get the latest items from the processed data"""
        count = min(count, len(self.processed_data))
        if count <= 0:
            return []

        return list(self.processed_data)[-count:]

    async def validate_content(self) -> bool:
        """Validate that streaming content is accessible"""
        # For streaming sources, validation is checking if we can connect
        if not self.is_connected:
            if not await self.connect():
                return False

        return True

    async def _process_content(self) -> None:
        """Process streaming content and chunk it"""
        # Ensure we've processed any pending items
        self._process_batch()

        # For streaming sources, we've already been continuously updating chunks
        if not self.chunks and self.text_content:
            self.chunks = self._chunk_text(self.text_content)

        self.logger.info(f"Created {len(self.chunks)} chunks from stream {self.name}")

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.stop()
