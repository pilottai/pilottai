from typing import Dict, List, Optional, Any
from datetime import datetime
from pilott.tools.knowledge import KnowledgeSource


class KnowledgeManager:
    def __init__(self):
        self.sources: Dict[str, KnowledgeSource] = {}
        self.cache = {}
        self.last_updated = {}

    async def add_source(self, source: KnowledgeSource):
        self.sources[source.name] = source
        self.last_updated[source.name] = datetime.now()

    async def query_knowledge(self, query: str, source_types: List[str]):
        results = []
        cache_key = f"{query}_{'-'.join(source_types)}"

        if cache_key in self.cache:
            return self.cache[cache_key]

        for source_type in source_types:
            if source_type in self.sources:
                result = await self.sources[source_type].query(query)
                results.append(result)

        self.cache[cache_key] = results
        return results

    def invalidate_cache(self, source_name: Optional[str] = None):
        if source_name:
            keys_to_remove = [k for k in self.cache if source_name in k]
            for k in keys_to_remove:
                del self.cache[k]
        else:
            self.cache.clear()