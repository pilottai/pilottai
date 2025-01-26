import asyncio
from typing import Any, List, Dict
from pydantic import BaseModel, Field

class Tool(BaseModel):
    """Tool that can be used by agents"""
    
    name: str
    description: str
    function: Any
    parameters: Dict[str, Any]
    permissions: List[str] = Field(default=list)
    usage_count: int = 0
    success_count: int = 0
    avg_execution_time: float = 0.0

    async def execute(self, **kwargs) -> Any:
        """Execute the tool"""
        self.usage_count += 1
        try:
            if asyncio.iscoroutinefunction(self.function):
                result = await self.function(**kwargs)
            else:
                result = await asyncio.to_thread(self.function, **kwargs)
            self.success_count += 1
            return result
        except Exception as e:
            raise ToolError(f"Error in {self.name}: {str(e)}")

    @property
    def success_rate(self) -> float:
        return self.success_count / self.usage_count if self.usage_count > 0 else 0.0

class ToolError(Exception):
    """Tool execution error"""
    pass
