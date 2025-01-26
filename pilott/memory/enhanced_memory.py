from typing import Dict, List, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class MemoryItem(BaseModel):
    """Memory item model"""
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra='allow'
    )

    text: str
    metadata: Dict[str, Any] = Field(default=dict)
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "text": self.text,
            "metadata": dict(self.metadata),
            "timestamp": self.timestamp
        }


class EnhancedMemory:
    """Enhanced memory system"""

    def __init__(self):
        self._semantic_store: Dict[str, Dict[str, Any]] = {}
        self._task_history: Dict[str, List[Dict[str, Any]]] = {}
        self._agent_interactions: Dict[str, Dict[str, Any]] = {}

    async def store_semantic(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Store content with proper dictionary handling"""
        try:
            if not isinstance(text, str):
                raise ValueError("Text must be a string")

            key = f"{datetime.now().isoformat()}_{hash(text)}"

            # Create memory item and convert to dict
            item = MemoryItem(
                text=text,
                metadata=metadata or {},
                timestamp=datetime.now().isoformat()
            )

            # Store as dictionary
            self._semantic_store[key] = item.to_dict()

        except Exception as e:
            raise ValueError(f"Failed to store content: {str(e)}")

    async def semantic_search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search content with proper dictionary handling"""
        try:
            if not isinstance(query, str):
                raise ValueError("Query must be a string")

            matches = []
            for item in self._semantic_store.values():
                if query.lower() in item["text"].lower():
                    matches.append(dict(item))
                if len(matches) >= limit:
                    break

            return matches

        except Exception as e:
            raise ValueError(f"Search failed: {str(e)}")

    def store_task(self, task_id: str, task_data: Dict[str, Any]) -> None:
        """Store task with proper dictionary handling"""
        try:
            if task_id not in self._task_history:
                self._task_history[task_id] = []

            entry = {
                "data": dict(task_data),
                "timestamp": datetime.now().isoformat()
            }

            self._task_history[task_id].append(entry)

        except Exception as e:
            raise ValueError(f"Failed to store task: {str(e)}")

    def store_interaction(self, agent_id: str, interaction_type: str, data: Dict[str, Any]) -> None:
        """Store interaction with proper dictionary handling"""
        try:
            if agent_id not in self._agent_interactions:
                self._agent_interactions[agent_id] = {}

            entry = {
                "type": interaction_type,
                "data": dict(data),
                "timestamp": datetime.now().isoformat()
            }

            self._agent_interactions[agent_id][datetime.now().isoformat()] = entry

        except Exception as e:
            raise ValueError(f"Failed to store interaction: {str(e)}")

    def get_recent_tasks(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent tasks with proper dictionary handling"""
        try:
            all_tasks = []
            for task_list in self._task_history.values():
                all_tasks.extend(list(task_list))

            # Sort by timestamp and return most recent
            return sorted(
                all_tasks,
                key=lambda x: x["timestamp"],
                reverse=True
            )[:limit]

        except Exception as e:
            raise ValueError(f"Failed to get recent tasks: {str(e)}")

    def clear(self) -> None:
        """Clear all memory stores"""
        self._semantic_store.clear()
        self._task_history.clear()
        self._agent_interactions.clear()