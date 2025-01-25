from typing import Any, List
from pydantic import BaseModel, Field

class Tool(BaseModel):
    """Tool that can be used by agents"""
    
    name: str
    description: str
    function: Any
    permissions: List[str] = Field(default_factory=list)
    usage_count: int = 0
    success_count: int = 0
    avg_execution_time: float = 0.0

    def execute(self, **kwargs) -> Any:
        """Execute the tool"""
        self.usage_count += 1
        try:
            result = self.function(**kwargs)
            self.success_count += 1
            return result
        except Exception as e:
            raise ToolError(f"Error in {self.name}: {str(e)}")

    @property
    def success_rate(self) -> float:
        """Calculate success rate"""
        if self.usage_count == 0:
            return 0.0
        return self.success_count / self.usage_count

class ToolError(Exception):
    """Tool execution error"""
    pass
