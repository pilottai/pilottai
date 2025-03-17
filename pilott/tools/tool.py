import asyncio
import logging
import traceback
from datetime import datetime
from typing import Any, List, Dict, Optional, Set

from pydantic import BaseModel, Field

from pilott.enums.tool_e import ToolStatus


class ToolMetrics(BaseModel):
    usage_count: int = 0
    success_count: int = 0
    error_count: int = 0
    total_execution_time: float = 0
    avg_execution_time: float = 0
    last_execution: Optional[datetime] = None
    last_error: Optional[str] = None
    error_types: Dict[str, int] = Field(default_factory=dict)


class Tool:
    """Tool class separated from Pydantic model for Lock handling"""

    def __init__(
            self,
            name: str,
            description: str,
            function: Any,
            parameters: Dict[str, Any],
            permissions: List[str] = None,
            required_capabilities: List[str] = None,
            timeout: float = 30.0,
            max_retries: int = 3,
            retry_delay: float = 1.0,
            cooldown_period: float = 0.0,
            max_concurrent: int = 1,
            enabled: bool = True
    ):
        self.name = name
        self.description = description
        self.function = function
        self.parameters = parameters
        self.permissions = permissions or []
        self.required_capabilities = required_capabilities or []
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.cooldown_period = cooldown_period
        self.max_concurrent = max_concurrent
        self.enabled = enabled

        # Runtime attributes
        self.status = ToolStatus.READY
        self.metrics = ToolMetrics()
        self.execution_lock = asyncio.Lock()
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self.active_executions: Set[str] = set()
        self.last_execution = datetime.now()
        self.logger = self._setup_logger()

    def _setup_logger(self) -> logging.Logger:
        """Setup logging"""
        logger = logging.getLogger(f"Tool_{self.name}")
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger

    async def execute(self, execution_id: Optional[str] = None, **kwargs) -> Any:
        """Execute the tool with proper error handling"""
        if not self.enabled:
            raise ToolError(f"Tool {self.name} is disabled")

        execution_id = execution_id or f"{self.name}_{datetime.now().timestamp()}"
        if execution_id in self.active_executions:
            raise ToolError(f"Duplicate execution ID: {execution_id}")

        start_time = datetime.now()
        try:
            if not await self._can_execute():
                raise ToolError(f"Tool {self.name} not ready")

            async with self.execution_lock:
                self.active_executions.add(execution_id)
                self.status = ToolStatus.BUSY

                try:
                    result = await self._execute_with_retry(execution_id, **kwargs)
                    await self._update_metrics(True, start_time)
                    return result
                finally:
                    self.active_executions.discard(execution_id)
                    if not self.active_executions:
                        self.status = ToolStatus.READY

        except Exception as e:
            await self._update_metrics(False, start_time, str(e))
            raise

    async def _execute_with_retry(self, execution_id: str, **kwargs) -> Any:
        """Execute with retry logic"""
        last_error = None
        for attempt in range(self.max_retries):
            try:
                async with asyncio.timeout(self.timeout):
                    if asyncio.iscoroutinefunction(self.function):
                        result = await self.function(**kwargs)
                    else:
                        result = await asyncio.to_thread(self.function, **kwargs)
                    return result
            except asyncio.TimeoutError:
                last_error = ToolTimeoutError(f"Timeout on attempt {attempt + 1}")
                self.logger.warning(f"Execution timeout, attempt {attempt + 1}")
            except Exception as e:
                last_error = e
                self.logger.error(
                    f"Execution failed, attempt {attempt + 1}: {str(e)}\n"
                    f"{traceback.format_exc()}")

            if attempt < self.max_retries - 1:
                await asyncio.sleep(self.retry_delay * (attempt + 1))

        raise last_error or ToolError("Execution failed after all retries")

    async def _can_execute(self) -> bool:
        """Check if tool can execute"""
        if not self.enabled:
            return False
        if self.cooldown_period > 0:
            time_since_last = (datetime.now() - self.last_execution).total_seconds()
            if time_since_last < self.cooldown_period:
                return False
        return True

    async def _update_metrics(self, success: bool, start_time: datetime, error: Optional[str] = None):
        """Update tool metrics"""
        execution_time = (datetime.now() - start_time).total_seconds()
        self.metrics.usage_count += 1
        self.metrics.total_execution_time += execution_time
        self.metrics.avg_execution_time = (
                self.metrics.total_execution_time / self.metrics.usage_count
        )
        self.metrics.last_execution = datetime.now()

        if success:
            self.metrics.success_count += 1
        else:
            self.metrics.error_count += 1
            self.metrics.last_error = error
            error_type = error.split(':')[0] if error else 'unknown'
            self.metrics.error_types[error_type] = (
                    self.metrics.error_types.get(error_type, 0) + 1
            )

    def get_metrics(self) -> Dict[str, Any]:
        """Get tool metrics"""
        return {
            "status": self.status,
            "metrics": self.metrics.model_dump(),
            "active_executions": len(self.active_executions),
            "enabled": self.enabled
        }


class ToolError(Exception):
    """Base class for tool errors"""
    pass


class ToolTimeoutError(ToolError):
    """Tool execution timeout error"""
    pass


class ToolPermissionError(ToolError):
    """Tool permission error"""
    pass


class ToolValidationError(ToolError):
    """Tool input validation error"""
    pass
