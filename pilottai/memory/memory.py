import asyncio
import json
from collections import deque
from datetime import datetime
from typing import Dict, List, Optional, Any, Set

from pilottai.config.model import MemoryEntry

class Memory:
    """
    Enhanced memory system for PilottAI with improved job integration.
    Maintains context and history for better job execution.
    """

    def __init__(self, max_entries: int = 1000):
        self._memory_lock = asyncio.Lock()
        self._job_index: Dict[str, List[int]] = {}  # Job ID -> Entry indices
        self._agent_index: Dict[str, List[int]] = {}  # Agent ID -> Entry indices
        self._entries: deque = deque(maxlen=max_entries)
        self._tag_index: Dict[str, List[int]] = {}

    async def store_job_start(
            self,
            job_id: str,
            description: str,
            agent_id: Optional[str] = None,
            context: Optional[Dict] = None
    ) -> None:
        """Store job start information"""
        entry = MemoryEntry(
            text=f"Started job: {description}",
            entry_type="job_start",
            metadata={
                "context": context or {},
                "status": "started"
            },
            tags={"job_start", f"job_{job_id}"},
            job_id=job_id,
            agent_id=agent_id
        )
        await self._store_entry(entry)

    async def store_job_result(
            self,
            job_id: str,
            result: Any,
            success: bool,
            execution_time: float,
            agent_id: Optional[str] = None
    ) -> None:
        """Store job execution results"""
        status = "completed" if success else "failed"
        entry = MemoryEntry(
            text=f"Job {status}: {str(result)}",
            entry_type="job_result",
            metadata={
                "success": success,
                "execution_time": execution_time,
                "result": result
            },
            tags={"job_result", f"job_{job_id}", status},
            job_id=job_id,
            agent_id=agent_id
        )
        await self._store_entry(entry)

    async def store_job_context(
            self,
            job_id: str,
            context: Dict[str, Any],
            context_type: str,
            agent_id: Optional[str] = None
    ) -> None:
        """Store additional job context"""
        entry = MemoryEntry(
            text=f"Context for job: {json.dumps(context)}",
            entry_type="job_context",
            metadata={
                "context": context,
                "context_type": context_type
            },
            tags={"job_context", f"job_{job_id}", context_type},
            job_id=job_id,
            agent_id=agent_id
        )
        await self._store_entry(entry)

    async def get_job_history(
            self,
            job_id: str,
            include_context: bool = True
    ) -> List[MemoryEntry]:
        """Get complete history for a job"""
        async with self._memory_lock:
            indices = self._job_index.get(job_id, [])
            entries = []

            for idx in indices:
                entry = self._entries[idx]
                if include_context or entry.entry_type != "job_context":
                    entries.append(entry)

            return sorted(entries, key=lambda x: x.timestamp)

    async def get_similar_jobs(
            self,
            job_description: str,
            limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Find similar past job based on description"""
        async with self._memory_lock:
            similar_jobs = []

            # Get all job start entries
            job_starts = [
                entry for entry in self._entries
                if entry.entry_type == "job_start"
            ]

            # Simple similarity based on common words
            job_words = set(job_description.lower().split())

            for entry in job_starts:
                entry_words = set(entry.text.lower().split())
                similarity = len(job_words & entry_words) / len(job_words | entry_words)

                if similarity > 0.3:  # Threshold for similarity
                    # Get job result
                    job_result = await self.get_job_result(entry.job_id)

                    similar_jobs.append({
                        "job_id": entry.job_id,
                        "description": entry.text,
                        "similarity": similarity,
                        "success": job_result.metadata.get("success") if job_result else None,
                        "timestamp": entry.timestamp
                    })

            # Sort by similarity and limit results
            return sorted(
                similar_jobs,
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

    async def get_job_result(self, job_id: str) -> Optional[MemoryEntry]:
        """Get the result of a specific job"""
        async with self._memory_lock:
            indices = self._job_index.get(job_id, [])

            for idx in indices:
                entry = self._entries[idx]
                if entry.entry_type == "job_result":
                    return entry

            return None

    async def get_job_context(
            self,
            job_id: str,
            context_type: Optional[str] = None
    ) -> List[MemoryEntry]:
        """Get context entries for a job"""
        async with self._memory_lock:
            indices = self._job_index.get(job_id, [])
            contexts = []

            for idx in indices:
                entry = self._entries[idx]
                if entry.entry_type == "job_context":
                    if context_type:
                        if entry.metadata.get("context_type") == context_type:
                            contexts.append(entry)
                    else:
                        contexts.append(entry)

            return sorted(contexts, key=lambda x: x.timestamp)

    async def build_job_context(
            self,
            job_description: str,
            agent_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Build comprehensive context for a new job"""
        context = {}

        # Get similar past job
        similar_jobs = await self.get_similar_jobs(job_description)
        if similar_jobs:
            context["similar_jobs"] = similar_jobs

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

            # Update job index
            if entry.job_id:
                if entry.job_id not in self._job_index:
                    self._job_index[entry.job_id] = []
                self._job_index[entry.job_id].append(entry_idx)

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
            await self._rebuild_indices()

    async def _rebuild_indices(self) -> None:
        """Rebuild all indices"""
        self._job_index.clear()
        self._tag_index.clear()
        self._agent_index.clear()

        for idx, entry in enumerate(self._entries):
            # Update job index
            if entry.job_id:
                if entry.job_id not in self._job_index:
                    self._job_index[entry.job_id] = []
                self._job_index[entry.job_id].append(idx)

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
