import asyncio
import json
from collections import deque
from datetime import datetime
from typing import Dict, List, Optional, Any, Set

from pydantic import BaseModel, Field


class MemoryEntry(BaseModel):
    """Enhanced memory entry with task awareness"""
    text: str
    entry_type: str  # 'task', 'context', 'result', etc.
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)
    tags: Set[str] = Field(default_factory=set)
    priority: int = Field(ge=0, default=1)
    task_id: Optional[str] = None
    agent_id: Optional[str] = None


class Memory:
    """
    Enhanced memory system for PilottAI with improved task integration.
    Maintains context and history for better task execution.
    """

    def __init__(self, max_entries: int = 1000):
        self._memory_lock = asyncio.Lock()
        self._task_index: Dict[str, List[int]] = {}  # Task ID -> Entry indices
        self._agent_index: Dict[str, List[int]] = {}  # Agent ID -> Entry indices
        self._entries: deque = deque(maxlen=max_entries)
        self._tag_index: Dict[str, List[int]] = {}

    async def store_task_start(
            self,
            task_id: str,
            description: str,
            agent_id: Optional[str] = None,
            context: Optional[Dict] = None
    ) -> None:
        """Store task start information"""
        entry = MemoryEntry(
            text=f"Started task: {description}",
            entry_type="task_start",
            metadata={
                "context": context or {},
                "status": "started"
            },
            tags={"task_start", f"task_{task_id}"},
            task_id=task_id,
            agent_id=agent_id
        )
        await self._store_entry(entry)

    async def store_task_result(
            self,
            task_id: str,
            result: Any,
            success: bool,
            execution_time: float,
            agent_id: Optional[str] = None
    ) -> None:
        """Store task execution results"""
        status = "completed" if success else "failed"
        entry = MemoryEntry(
            text=f"Task {status}: {str(result)}",
            entry_type="task_result",
            metadata={
                "success": success,
                "execution_time": execution_time,
                "result": result
            },
            tags={"task_result", f"task_{task_id}", status},
            task_id=task_id,
            agent_id=agent_id
        )
        await self._store_entry(entry)

    async def store_task_context(
            self,
            task_id: str,
            context: Dict[str, Any],
            context_type: str,
            agent_id: Optional[str] = None
    ) -> None:
        """Store additional task context"""
        entry = MemoryEntry(
            text=f"Context for task: {json.dumps(context)}",
            entry_type="task_context",
            metadata={
                "context": context,
                "context_type": context_type
            },
            tags={"task_context", f"task_{task_id}", context_type},
            task_id=task_id,
            agent_id=agent_id
        )
        await self._store_entry(entry)

    async def get_task_history(
            self,
            task_id: str,
            include_context: bool = True
    ) -> List[MemoryEntry]:
        """Get complete history for a task"""
        async with self._memory_lock:
            indices = self._task_index.get(task_id, [])
            entries = []

            for idx in indices:
                entry = self._entries[idx]
                if include_context or entry.entry_type != "task_context":
                    entries.append(entry)

            return sorted(entries, key=lambda x: x.timestamp)

    async def get_similar_tasks(
            self,
            task_description: str,
            limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Find similar past tasks based on description"""
        async with self._memory_lock:
            similar_tasks = []

            # Get all task start entries
            task_starts = [
                entry for entry in self._entries
                if entry.entry_type == "task_start"
            ]

            # Simple similarity based on common words
            task_words = set(task_description.lower().split())

            for entry in task_starts:
                entry_words = set(entry.text.lower().split())
                similarity = len(task_words & entry_words) / len(task_words | entry_words)

                if similarity > 0.3:  # Threshold for similarity
                    # Get task result
                    task_result = await self.get_task_result(entry.task_id)

                    similar_tasks.append({
                        "task_id": entry.task_id,
                        "description": entry.text,
                        "similarity": similarity,
                        "success": task_result.metadata.get("success") if task_result else None,
                        "timestamp": entry.timestamp
                    })

            # Sort by similarity and limit results
            return sorted(
                similar_tasks,
                key=lambda x: x["similarity"],
                reverse=True
            )[:limit]

    async def get_agent_context(
            self,
            agent_id: str,
            context_type: Optional[str] = None,
            limit: int = 10
    ) -> List[MemoryEntry]:
        """Get historical context for an agent"""
        async with self._memory_lock:
            indices = self._agent_index.get(agent_id, [])
            entries = []

            for idx in indices:
                entry = self._entries[idx]
                if context_type and "context_type" in entry.metadata:
                    if entry.metadata["context_type"] == context_type:
                        entries.append(entry)
                else:
                    entries.append(entry)

            return sorted(
                entries,
                key=lambda x: x.timestamp,
                reverse=True
            )[:limit]

    async def get_task_result(self, task_id: str) -> Optional[MemoryEntry]:
        """Get the result of a specific task"""
        async with self._memory_lock:
            indices = self._task_index.get(task_id, [])

            for idx in indices:
                entry = self._entries[idx]
                if entry.entry_type == "task_result":
                    return entry

            return None

    async def get_task_context(
            self,
            task_id: str,
            context_type: Optional[str] = None
    ) -> List[MemoryEntry]:
        """Get context entries for a task"""
        async with self._memory_lock:
            indices = self._task_index.get(task_id, [])
            contexts = []

            for idx in indices:
                entry = self._entries[idx]
                if entry.entry_type == "task_context":
                    if context_type:
                        if entry.metadata.get("context_type") == context_type:
                            contexts.append(entry)
                    else:
                        contexts.append(entry)

            return sorted(contexts, key=lambda x: x.timestamp)

    async def build_task_context(
            self,
            task_description: str,
            agent_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Build comprehensive context for a new task"""
        context = {}

        # Get similar past tasks
        similar_tasks = await self.get_similar_tasks(task_description)
        if similar_tasks:
            context["similar_tasks"] = similar_tasks

        # Get agent context if specified
        if agent_id:
            agent_context = await self.get_agent_context(agent_id)
            if agent_context:
                context["agent_history"] = [
                    {
                        "text": entry.text,
                        "timestamp": entry.timestamp.isoformat(),
                        "metadata": entry.metadata
                    }
                    for entry in agent_context
                ]

        return context

    async def _store_entry(self, entry: MemoryEntry) -> None:
        """Store a memory entry and update indices"""
        async with self._memory_lock:
            # Add entry to deque
            self._entries.append(entry)
            entry_idx = len(self._entries) - 1

            # Update task index
            if entry.task_id:
                if entry.task_id not in self._task_index:
                    self._task_index[entry.task_id] = []
                self._task_index[entry.task_id].append(entry_idx)

            # Update tag index
            for tag in entry.tags:
                if tag not in self._tag_index:
                    self._tag_index[tag] = set()
                self._tag_index[tag].append(entry_idx)

            # Update agent index
            if entry.agent_id:
                if entry.agent_id not in self._agent_index:
                    self._agent_index[entry.agent_id] = []
                self._agent_index[entry.agent_id].append(entry_idx)

    async def cleanup_old_entries(self, max_age_days: int = 30) -> None:
        """Clean up old memory entries"""
        cutoff = datetime.now().timestamp() - (max_age_days * 24 * 3600)

        async with self._memory_lock:
            # Remove old entries
            while self._entries and self._entries[0].timestamp.timestamp() < cutoff:
                self._entries.popleft()

            # Rebuild indices
            self._rebuild_indices()

    def _rebuild_indices(self) -> None:
        """Rebuild all indices"""
        self._task_index.clear()
        self._tag_index.clear()
        self._agent_index.clear()

        for idx, entry in enumerate(self._entries):
            # Update task index
            if entry.task_id:
                if entry.task_id not in self._task_index:
                    self._task_index[entry.task_id] = []
                self._task_index[entry.task_id].append(idx)

            # Update tag index
            for tag in entry.tags:
                if tag not in self._tag_index:
                    self._tag_index[tag] = set()
                self._tag_index[tag].add(idx)

            # Update agent index
            if entry.agent_id:
                if entry.agent_id not in self._agent_index:
                    self._agent_index[entry.agent_id] = []
                self._agent_index[entry.agent_id].append(idx)

    async def store_semantic(
            self,
            text: str,
            metadata: Optional[Dict[str, Any]] = None,
            tags: Optional[Set[str]] = None
    ) -> None:
        """
        Store information with semantic context.

        Args:
            text: The text content to store
            metadata: Optional metadata dictionary
            tags: Optional set of tags for categorization
        """
        async with self._memory_lock:
            entry = MemoryEntry(
                text=text,
                metadata=metadata or {},
                tags=tags or set()
            )

            # Add entry and update index
            self._entries.append(entry)
            entry_idx = len(self._entries) - 1

            # Update tag index
            for tag in entry.tags:
                if tag not in self._tag_index:
                    self._tag_index[tag] = []
                self._tag_index[tag].append(entry_idx)

    async def search(
            self,
            query: str,
            tags: Optional[Set[str]] = None,
            limit: int = 5
    ) -> List[MemoryEntry]:
        """
        Search memory entries.

        Args:
            query: Search query string
            tags: Optional tags to filter by
            limit: Maximum number of results

        Returns:
            List of matching memory entries
        """
        async with self._memory_lock:
            results = []

            # Get candidate indices from tags
            candidate_indices = set(range(len(self._entries)))
            if tags:
                tag_indices = set()
                for tag in tags:
                    if tag in self._tag_index:
                        tag_indices.update(self._tag_index[tag])
                candidate_indices &= tag_indices

            # Simple text matching for now
            query_lower = query.lower()
            for idx in candidate_indices:
                entry = self._entries[idx]
                if query_lower in entry.text.lower():
                    results.append(entry)
                    if len(results) >= limit:
                        break

            return sorted(
                results,
                key=lambda x: x.timestamp,
                reverse=True
            )

    async def get_recent(
            self,
            tags: Optional[Set[str]] = None,
            limit: int = 10
    ) -> List[MemoryEntry]:
        """
        Get recent entries.

        Args:
            tags: Optional tags to filter by
            limit: Maximum number of results

        Returns:
            List of recent memory entries
        """
        async with self._memory_lock:
            entries = list(self._entries)

            if tags:
                entries = [
                    entry for entry in entries
                    if tags & entry.tags
                ]

            return sorted(
                entries,
                key=lambda x: x.timestamp,
                reverse=True
            )[:limit]

    async def clear(self) -> None:
        """Clear all memory entries"""
        async with self._memory_lock:
            self._entries.clear()
            self._tag_index.clear()

    def __len__(self) -> int:
        """Get number of stored entries"""
        return len(self._entries)
