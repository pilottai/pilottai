from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field
from pilott.core.role import AgentRole


class LLMConfig(BaseModel):
    """Configuration for LLM integration"""
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        use_enum_values=True
    )

    model_name: str
    provider: str
    api_key: str
    temperature: float = 0.7
    max_tokens: int = 2000
    function_calling_model: Optional[str] = None
    system_template: Optional[str] = None
    prompt_template: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a dictionary with only basic Python types"""
        return {
            "model_name": str(self.model_name),
            "provider": str(self.provider),
            "api_key": str(self.api_key),
            "temperature": float(self.temperature),
            "max_tokens": int(self.max_tokens)
        }


class LogConfig(BaseModel):
    """Configuration for logging"""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    verbose: bool = False
    log_to_file: bool = False
    log_dir: str = "logs"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    log_level: str = "INFO"


class AgentConfig(BaseModel):
    """Enhanced configuration for agent initialization"""
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        use_enum_values=True
    )

    # Basic Configuration
    role: str
    role_type: AgentRole = AgentRole.WORKER
    goal: str
    description: str
    backstory: Optional[str] = None

    # Knowledge and Tools
    knowledge_sources: List[str] = Field(default_factory=list)
    tools: List[str] = Field(default_factory=list)

    # Execution Settings
    max_iterations: int = 20
    max_rpm: Optional[int] = None
    max_execution_time: Optional[int] = None
    retry_limit: int = 2
    code_execution_mode: str = "safe"

    # Features
    memory_enabled: bool = True
    verbose: bool = False
    can_delegate: bool = False
    use_cache: bool = True
    can_execute_code: bool = False

    # Orchestration Settings
    max_child_agents: int = 10
    max_queue_size: int = 100
    max_task_complexity: int = 5
    delegation_threshold: float = 0.7

    # WebSocket Configuration
    websocket_enabled: bool = True
    websocket_host: str = "localhost"
    websocket_port: int = 8765

    # Async Settings
    max_concurrent_tasks: int = 5
    task_timeout: int = 300  # seconds

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a dictionary with only basic Python types"""
        return {
            "role": str(self.role),
            "role_type": str(self.role_type),
            "goal": str(self.goal),
            "description": str(self.description),
            "backstory": str(self.backstory) if self.backstory else None,
            "knowledge_sources": list(self.knowledge_sources),
            "tools": list(self.tools),
            "max_iterations": int(self.max_iterations),
            "max_rpm": int(self.max_rpm) if self.max_rpm else None,
            "max_execution_time": int(self.max_execution_time) if self.max_execution_time else None,
            "retry_limit": int(self.retry_limit),
            "code_execution_mode": str(self.code_execution_mode),
            "memory_enabled": bool(self.memory_enabled),
            "verbose": bool(self.verbose),
            "can_delegate": bool(self.can_delegate),
            "use_cache": bool(self.use_cache),
            "can_execute_code": bool(self.can_execute_code),
            "max_child_agents": int(self.max_child_agents),
            "max_queue_size": int(self.max_queue_size),
            "max_task_complexity": int(self.max_task_complexity),
            "delegation_threshold": float(self.delegation_threshold),
            "max_concurrent_tasks": int(self.max_concurrent_tasks),
            "task_timeout": int(self.task_timeout)
        }