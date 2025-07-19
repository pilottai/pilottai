import asyncio
import bisect
from collections import deque
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Set

from pilottai.config.model import MemoryItem


class DataController:
    def __init__(self, max_size: int = 10000, cleanup_interval: int = 3600):
        self._memory_lock = asyncio.Lock()
        self._semantic_store: deque = deque(maxlen=max_size)
        self._job_history: Dict[str, deque] = {}
        self._agent_interactions: Dict[str, Dict[str, Any]] = {}
        self._pattern_store: Dict[str, Dict[str, Any]] = {}

        # Indexes
        self._tag_index: Dict[str, Set[int]] = {}
        self._timestamp_index: List[datetime] = []
        self._priority_index: Dict[int, Set[int]] = {}

        # Configuration
        self.max_job_history = 1000
        self.cleanup_interval = cleanup_interval
        self.last_cleanup = datetime.now()

        # Locks
        self._semantic_lock = asyncio.Lock()
        self._job_lock = asyncio.Lock()
        self._interaction_lock = asyncio.Lock()
        self._pattern_lock = asyncio.Lock()
        self._cleanup_job = None

    async def start(self):
        self._cleanup_job = asyncio.create_task(self._periodic_cleanup())

    async def stop(self):
        if self._cleanup_job:
            self._cleanup_job.cancel()
            try:
                await self._cleanup_job
            except asyncio.CancelledError:
                pass

    async def store_semantic(
            self,
            text: str,
            metadata: Optional[Dict[str, Any]] = None,
            tags: Optional[Set[str]] = None,
            priority: int = 0,
            ttl: Optional[int] = None
    ) -> None:
        if not text:
            raise ValueError("Text cannot be empty")

        try:
            expires_at = (
                datetime.now() + timedelta(seconds=ttl)
                if ttl is not None else None
            )

            item = MemoryItem(
                text=text,
                metadata=metadata or {},
                tags=tags or set(),
                priority=priority,
                expires_at=expires_at
            )

            async with self._semantic_lock:
                self._semantic_store.append(item)
                index = len(self._semantic_store) - 1
                self._update_indexes(item, index)

        except Exception as e:
            raise ValueError(f"Failed to store content: {str(e)}")

    async def semantic_search(
            self,
            query: str,
            tags: Optional[Set[str]] = None,
            min_priority: int = 0,
            limit: int = 5
    ) -> List[MemoryItem]:
        if not query:
            raise ValueError("Query cannot be empty")
        try:
            async with self._semantic_lock:
                candidate_indexes = self._get_candidate_indexes(tags, min_priority)
                matches = []
                for idx in candidate_indexes:
                    item = self._semantic_store[idx]
                    if item.is_expired():
                        continue
                    if query.lower() in item.text.lower():
                        matches.append(item)
                        if len(matches) >= limit:
                            break
                return sorted(matches, key=lambda x: (-x.priority, x.timestamp))
        except Exception as e:
            raise ValueError(f"Search failed: {str(e)}")

    def _get_candidate_indexes(
            self,
            tags: Optional[Set[str]] = None,
            min_priority: int = 0
    ) -> Set[int]:
        candidates = set()
        for priority in range(min_priority, max(self._priority_index.keys()) + 1):
            candidates.update(self._priority_index.get(priority, set()))
        if tags:
            tag_candidates = set.intersection(
                *(self._tag_index.get(tag, set()) for tag in tags)
            )
            candidates &= tag_candidates
        return candidates

    def _update_indexes(self, item: MemoryItem, index: int):
        # Update tag index
        for tag in item.tags:
            if tag not in self._tag_index:
                self._tag_index[tag] = set()
            self._tag_index[tag].add(index)
        # Update timestamp index
        bisect.insort(self._timestamp_index, item.timestamp)
        # Update priority index
        if item.priority not in self._priority_index:
            self._priority_index[item.priority] = set()
        self._priority_index[item.priority].add(index)

    async def store_job(self, job_id: str, job_data: Dict[str, Any]) -> None:
        if not job_id or not job_data:
            raise ValueError("Job ID and data required")
        try:
            async with self._job_lock:
                if job_id not in self._job_history:
                    self._job_history[job_id] = deque(maxlen=self.max_job_history)
                entry = {
                    "data": dict(job_data),
                    "timestamp": datetime.now(),
                    "version": len(self._job_history[job_id]) + 1
                }
                self._job_history[job_id].append(entry)
        except Exception as e:
            raise ValueError(f"Failed to store job: {str(e)}")

    async def store_interaction(
            self,
            agent_id: str,
            interaction_type: str,
            data: Dict[str, Any]) -> None:
        if not agent_id or not interaction_type or not data:
            raise ValueError("Agent ID, interaction type, and data required")
        try:
            async with self._interaction_lock:
                if agent_id not in self._agent_interactions:
                    self._agent_interactions[agent_id] = {}
                timestamp = datetime.now()
                entry = {
                    "type": interaction_type,
                    "data": dict(data),
                    "timestamp": timestamp,
                    "version": len(self._agent_interactions[agent_id]) + 1
                }
                self._agent_interactions[agent_id][timestamp.isoformat()] = entry
        except Exception as e:
            raise ValueError(f"Failed to store interaction: {str(e)}")

    async def store_pattern(
            self,
            name: str,
            data: Any,
            ttl: Optional[int] = None) -> None:
        if not name:
            raise ValueError("Pattern name required")
        try:
            async with self._pattern_lock:
                expires_at = (
                    datetime.now() + timedelta(seconds=ttl)
                    if ttl is not None else None
                )
                self._pattern_store[name] = {
                    "data": data,
                    "timestamp": datetime.now(),
                    "expires_at": expires_at
                }
        except Exception as e:
            raise ValueError(f"Failed to store pattern: {str(e)}")

    async def get_pattern(self, name: str) -> Optional[Any]:
        if not name:
            raise ValueError("Pattern name required")
        try:
            async with self._pattern_lock:
                if name not in self._pattern_store:
                    return None
                pattern = self._pattern_store[name]
                if pattern["expires_at"] and datetime.now() > pattern["expires_at"]:
                    del self._pattern_store[name]
                    return None
                return pattern["data"]
        except Exception as e:
            raise ValueError(f"Failed to retrieve pattern: {str(e)}")

    async def get_recent_jobs(
            self,
            limit: int = 10,
            job_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        if limit < 1:
            raise ValueError("Limit must be positive")
        try:
            async with self._job_lock:
                all_jobs = []
                for job_list in self._job_history.values():
                    if job_type:
                        filtered_jobs = [
                            job for job in job_list
                            if job["data"].get("type") == job_type
                        ]
                        all_jobs.extend(filtered_jobs)
                    else:
                        all_jobs.extend(list(job_list))

                return sorted(
                    all_jobs,
                    key=lambda x: x["timestamp"],
                    reverse=True
                )[:limit]
        except Exception as e:
            raise ValueError(f"Failed to get recent jobs: {str(e)}")

    async def _periodic_cleanup(self):
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)
                await self.cleanup()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Periodic cleanup error: {str(e)}")

    async def cleanup(self):
        try:
            async with self._semantic_lock, self._pattern_lock:
                # Clean up semantic store
                valid_items = deque(
                    item for item in self._semantic_store
                    if not item.is_expired()
                )
                self._semantic_store = valid_items
                # Rebuild indexes
                self._tag_index.clear()
                self._timestamp_index.clear()
                self._priority_index.clear()
                for idx, item in enumerate(self._semantic_store):
                    self._update_indexes(item, idx)
                # Clean up patterns
                expired_patterns = [
                    name for name, pattern in self._pattern_store.items()
                    if pattern["expires_at"] and datetime.now() > pattern["expires_at"]
                ]
                for name in expired_patterns:
                    del self._pattern_store[name]
            self.last_cleanup = datetime.now()
        except Exception as e:
            raise ValueError(f"Cleanup failed: {str(e)}")

    def clear(self) -> None:
        """Clear all memory stores"""
        self._semantic_store.clear()
        self._job_history.clear()
        self._agent_interactions.clear()
        self._pattern_store.clear()
        self._tag_index.clear()
        self._timestamp_index.clear()
        self._priority_index.clear()
