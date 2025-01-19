from typing import List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

class Memory(BaseModel):
    """Memory management for agents"""
    
    history: List[Dict[str, Any]] = Field(default_factory=list)
    context: Dict[str, Any] = Field(default_factory=dict)
    patterns: Dict[str, Any] = Field(default_factory=dict)

    def store(self, data: Dict[str, Any]):
        """Store new information"""
        self.history.append({
            "timestamp": datetime.now(),
            "data": data
        })

    def retrieve(self, query: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Retrieve relevant information"""
        matches = []
        for entry in reversed(self.history):
            if self._matches_query(entry["data"], query):
                matches.append(entry)
        return matches

    def update_context(self, key: str, value: Any):
        """Update current context"""
        self.context[key] = value

    def store_pattern(self, name: str, data: Any):
        """Store a pattern"""
        self.patterns[name] = {
            "data": data,
            "timestamp": datetime.now()
        }

    def _matches_query(self, data: Dict, query: Dict) -> bool:
        """Check if data matches query"""
        return all(
            key in data and data[key] == value 
            for key, value in query.items()
        )
