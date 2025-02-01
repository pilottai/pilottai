from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
import asyncio
from collections import deque
import bisect


class MemoryEntry(BaseModel):
    timestamp: datetime
    data: Dict[str, Any]
    tags: List[str] = Field(default_factory=list)
    priority: int = 1


class Memory(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    MAX_HISTORY_SIZE: int = 1000
    MAX_CONTEXT_SIZE: int = 100
    MAX_PATTERNS_SIZE: int = 50

    history: deque = Field(default_factory=lambda: deque(maxlen=1000))
    context: Dict[str, Any] = Field(default_factory=dict)
    patterns: Dict[str, Any] = Field(default_factory=dict)
    tag_index: Dict[str, List[int]] = Field(default_factory=dict)
    timestamp_index: List[datetime] = Field(default_factory=list)
    memory_lock: Optional[asyncio.Lock] = None

    def __init__(self, **data):
        super().__init__(**data)
        self.memory_lock = asyncio.Lock()

    async def store(self, data: Dict[str, Any], tags: List[str] = None, priority: int = 1):
        """Store new information with indexing"""
        async with self.memory_lock:
            entry = MemoryEntry(
                timestamp=datetime.now(),
                data=data,
                tags=tags or [],
                priority=priority
            )

            self.history.append(entry)

            for tag in entry.tags:
                if tag not in self.tag_index:
                    self.tag_index[tag] = []
                self.tag_index[tag].append(len(self.history) - 1)

            bisect.insort(self.timestamp_index, entry.timestamp)

    def retrieve(self,
                 query: Dict[str, Any],
                 tags: List[str] = None,
                 limit: int = 10,
                 min_priority: int = 0) -> List[MemoryEntry]:
        """Retrieve relevant information using indexes"""
        candidate_indices = set()

        if tags:
            for tag in tags:
                if tag in self.tag_index:
                    candidate_indices.update(self.tag_index[tag])
        else:
            candidate_indices = set(range(len(self.history)))

        matches = []
        for idx in candidate_indices:
            entry = self.history[idx]
            if entry.priority >= min_priority and self.matches_query(entry.data, query):
                matches.append(entry)
                if len(matches) >= limit:
                    break

        return sorted(matches, key=lambda x: x.timestamp, reverse=True)

    def retrieve_by_timerange(self,
                              start_time: datetime,
                              end_time: Optional[datetime] = None) -> List[MemoryEntry]:
        """Retrieve entries within a time range using binary search"""
        if end_time is None:
            end_time = datetime.now()

        start_idx = bisect.bisect_left(self.timestamp_index, start_time)
        end_idx = bisect.bisect_right(self.timestamp_index, end_time)

        return [entry for entry in self.history if start_time <= entry.timestamp <= end_time]

    def update_context(self, key: str, value: Any):
        """Update current context with size limit"""
        self.context[key] = value
        if len(self.context) > self.MAX_CONTEXT_SIZE:
            oldest_key = min(self.context.keys(), key=lambda k: self.context[k].get('timestamp', datetime.min))
            del self.context[oldest_key]

    def store_pattern(self, name: str, data: Any):
        """Store a pattern with size limit"""
        if len(self.patterns) >= self.MAX_PATTERNS_SIZE:
            oldest_pattern = min(self.patterns.keys(),
                                 key=lambda k: self.patterns[k].get('timestamp', datetime.min))
            del self.patterns[oldest_pattern]

        self.patterns[name] = {
            "data": data,
            "timestamp": datetime.now()
        }

    def matches_query(self, data: Dict, query: Dict) -> bool:
        """Check if data matches query pattern"""
        return all(
            key in data and
            (isinstance(value, (list, dict)) and data[key] == value
             or data[key] == value)
            for key, value in query.items()
        )

    def cleanup(self, older_than: Optional[datetime] = None):
        """Clean up old entries and rebuild indexes"""
        if older_than:
            self.history = deque(
                [entry for entry in self.history if entry.timestamp > older_than],
                maxlen=self.MAX_HISTORY_SIZE
            )

        self.tag_index.clear()
        self.timestamp_index.clear()

        for i, entry in enumerate(self.history):
            for tag in entry.tags:
                if tag not in self.tag_index:
                    self.tag_index[tag] = []
                self.tag_index[tag].append(i)
            bisect.insort(self.timestamp_index, entry.timestamp)