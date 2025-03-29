from typing import Dict, List, Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field
import asyncio
import json
from collections import OrderedDict
import logging

class CacheEntry(BaseModel):
    value: Any
    timestamp: datetime
    ttl: int
    access_count: int = 0
    last_access: datetime = Field(default_factory=datetime.now)

class KnowledgeSource(BaseModel):
    name: str
    type: str
    connection: Dict[str, Any]
    last_access: datetime = Field(default_factory=datetime.now)
    access_count: int = 0
    error_count: int = 0
    is_connected: bool = False
    max_retries: int = 3
    retry_delay: int = 5
    timeout: int = 30

class DataManager:
    def __init__(self, cache_size: int = 1000, cache_ttl: int = 3600):
        self.sources: Dict[str, KnowledgeSource] = {}
        self.cache: OrderedDict = OrderedDict()
        self.last_updated: Dict[str, datetime] = {}
        self.source_locks: Dict[str, asyncio.Lock] = {}
        self.cache_lock = asyncio.Lock()
        self.MAX_CACHE_SIZE = max(100, cache_size)
        self.DEFAULT_CACHE_TTL = max(60, cache_ttl)
        self.logger = logging.getLogger("KnowledgeManager")
        self._setup_logging()
        self._cleanup_task = None

    async def start(self):
        self._cleanup_task = asyncio.create_task(self._periodic_cleanup())

    async def stop(self):
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

    def _setup_logging(self):
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    async def add_source(self, source: KnowledgeSource) -> bool:
        try:
            if source.name in self.sources:
                raise ValueError(f"Source {source.name} already exists")

            self.source_locks[source.name] = asyncio.Lock()
            self.sources[source.name] = source
            self.last_updated[source.name] = datetime.now()

            connected = await self._test_connection(source)
            source.is_connected = connected
            return connected

        except Exception as e:
            self.logger.error(f"Error adding source {source.name}: {str(e)}")
            return False

    async def query_knowledge(
            self,
            query: str,
            source_types: List[str],
            ttl: Optional[int] = None,
            force_refresh: bool = False
    ) -> List[Any]:
        if not query:
            raise ValueError("Query cannot be empty")
        if not source_types:
            raise ValueError("Source types cannot be empty")
        cache_key = self._generate_cache_key(query, source_types)
        results = []
        try:
            if not force_refresh:
                cached_result = await self._get_from_cache(cache_key)
                if cached_result is not None:
                    return cached_result
            async with asyncio.timeout(30):  # 30 second timeout
                for source_type in source_types:
                    if source_type in self.sources:
                        source = self.sources[source_type]
                        try:
                            async with self.source_locks[source_type]:
                                result = await self._query_source_with_retry(source, query)
                                if result is not None:
                                    results.append(result)
                        except Exception as e:
                            self.logger.error(f"Error querying source {source_type}: {str(e)}")
                            source.error_count += 1
                            continue
                if results:
                    await self._add_to_cache(cache_key, results, ttl)
                return results
        except asyncio.TimeoutError:
            self.logger.error("Query timed out")
            return []
        except Exception as e:
            self.logger.error(f"Error during knowledge query: {str(e)}")
            return []

    async def _query_source_with_retry(
            self,
            source: KnowledgeSource,
            query: str
    ) -> Optional[Any]:
        for attempt in range(source.max_retries):
            try:
                if not source.is_connected:
                    if not await self._test_connection(source):
                        raise ConnectionError(f"Source {source.name} is not connected")
                async with asyncio.timeout(source.timeout):
                    result = await source.query(query)
                    source.access_count += 1
                    source.last_access = datetime.now()
                    return result
            except asyncio.TimeoutError:
                self.logger.warning(
                    f"Query timeout for source {source.name}, attempt {attempt + 1}"
                )
                source.error_count += 1
            except Exception as e:
                self.logger.error(
                    f"Query failed for source {source.name}, attempt {attempt + 1}: {str(e)}"
                )
                source.error_count += 1
                if attempt < source.max_retries - 1:
                    await asyncio.sleep(source.retry_delay)
        return None

    async def _test_connection(self, source: KnowledgeSource) -> bool:
        try:
            async with asyncio.timeout(source.timeout):
                return await source.connect()
        except Exception as e:
            self.logger.error(f"Connection test failed for {source.name}: {str(e)}")
            return False

    async def _get_from_cache(self, key: str) -> Optional[Any]:
        try:
            async with self.cache_lock:
                if key not in self.cache:
                    return None
                entry = self.cache[key]
                if self._is_cache_entry_valid(entry):
                    self.cache.move_to_end(key)
                    entry.access_count += 1
                    entry.last_access = datetime.now()
                    return entry.value
                else:
                    del self.cache[key]
                    return None
        except Exception as e:
            self.logger.error(f"Cache retrieval error: {str(e)}")
            return None

    async def _add_to_cache(self, key: str, value: Any, ttl: Optional[int] = None):
        try:
            async with self.cache_lock:
                while len(self.cache) >= self.MAX_CACHE_SIZE:
                    self.cache.popitem(last=False)
                self.cache[key] = CacheEntry(
                    value=value,
                    timestamp=datetime.now(),
                    ttl=ttl or self.DEFAULT_CACHE_TTL
                )
                self.cache.move_to_end(key)
        except Exception as e:
            self.logger.error(f"Cache addition error: {str(e)}")

    def _is_cache_entry_valid(self, entry: CacheEntry) -> bool:
        return (datetime.now() - entry.timestamp).total_seconds() < entry.ttl

    def _generate_cache_key(self, query: str, source_types: List[str]) -> str:
        key_data = {
            "query": query,
            "sources": sorted(source_types)
        }
        return json.dumps(key_data, sort_keys=True)

    async def invalidate_cache(
            self,
            source_name: Optional[str] = None,
            pattern: Optional[str] = None):
        try:
            async with self.cache_lock:
                if source_name:
                    keys_to_remove = [
                        k for k in self.cache
                        if source_name in json.loads(k)["sources"]]
                elif pattern:
                    keys_to_remove = [
                        k for k in self.cache
                        if pattern in k]
                else:
                    self.cache.clear()
                    return
                for k in keys_to_remove:
                    del self.cache[k]
        except Exception as e:
            self.logger.error(f"Cache invalidation error: {str(e)}")

    async def _periodic_cleanup(self):
        while True:
            try:
                await asyncio.sleep(3600)  # Cleanup every hour
                await self.cleanup()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Periodic cleanup error: {str(e)}")

    async def cleanup(self):
        try:
            async with self.cache_lock:
                current_time = datetime.now()
                expired_keys = [
                    k for k, v in self.cache.items()
                    if not self._is_cache_entry_valid(v)
                ]
                for k in expired_keys:
                    del self.cache[k]
                # Check source health
                for source_name, source in self.sources.items():
                    if source.error_count > source.max_retries:
                        source.is_connected = False
                        if await self._test_connection(source):
                            source.error_count = 0
                            source.is_connected = True
        except Exception as e:
            self.logger.error(f"Cleanup error: {str(e)}")

    def get_source_stats(self) -> Dict[str, Dict[str, Any]]:
        return {
            name: {
                "access_count": source.access_count,
                "error_count": source.error_count,
                "last_access": source.last_access.isoformat(),
                "is_connected": source.is_connected
            }
            for name, source in self.sources.items()
        }

    def get_cache_stats(self) -> Dict[str, Any]:
        return {
            "size": len(self.cache),
            "max_size": self.MAX_CACHE_SIZE,
            "hit_ratio": sum(e.access_count for e in self.cache.values()) / max(1, len(self.cache))
        }
