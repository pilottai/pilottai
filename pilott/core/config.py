from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict

from pilott.core import AgentRole


class LLMConfig(BaseModel):
    """Configuration for LLM integration"""
    model_name: str = "gpt-4"
    function_calling_model: Optional[str] = None
    system_template: Optional[str] = None
    prompt_template: Optional[str] = None
    response_template: Optional[str] = None
    respect_context_window: bool = True
    embedder_config: Optional[Dict[str, Any]] = None

class LogConfig(BaseModel):
    """Configuration for logging"""
    verbose: bool = False
    log_to_file: bool = False
    log_dir: str = "logs"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    log_level: str = "INFO"


class AgentConfig(BaseModel):
    """Enhanced configuration for agent initialization"""

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra='allow'
    )

    # Basic Configuration
    role: str
    role_type: AgentRole = AgentRole.WORKER
    goal: str
    description: str
    backstory: Optional[str] = None

    # Logging Configuration
    logging: LogConfig = Field(default_factory=LogConfig)

    # LLM Configuration
    llm_config: Optional[Dict[str, Any]] = None

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