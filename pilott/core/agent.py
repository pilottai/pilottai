from typing import Dict, List, Optional, Any, Union
from datetime import datetime
import uuid
import logging
import asyncio

from pilott.core.config import AgentConfig, LLMConfig
from pilott.core.status import AgentStatus
from pilott.memory import EnhancedMemory


class Agent:
    """Base Agent class"""

    def __init__(
            self,
            role: str,
            goal: str,
            backstory: Optional[str] = None,
            tools: Optional[List[Any]] = None,
            agent_config: Optional[Union[Dict, AgentConfig]] = None,
            llm_config: Optional[Union[Dict, LLMConfig]] = None,
            verbose: bool = False
    ):
        # Store basic attributes
        self.role = role
        self.goal = goal
        self.backstory = backstory
        self.tools = tools or []
        self.verbose = verbose
        self.id = str(uuid.uuid4())

        # Convert configs if needed
        if isinstance(agent_config, dict):
            agent_config = AgentConfig(**agent_config)
        if isinstance(llm_config, dict):
            llm_config = LLMConfig(**llm_config)

        # Create default configs if not provided
        if not agent_config:
            agent_config = AgentConfig(
                role=role,
                goal=goal,
                description=backstory or f"Agent with role {role}",
                backstory=backstory
            )

        if not llm_config:
            llm_config = LLMConfig(
                model_name="gpt-4",
                provider="openai",
                api_key="",  # Should be set through environment
                temperature=0.7
            )

        # Store configs
        self.agent_config = agent_config
        self.llm_config = llm_config

        # Initialize components
        self._setup_components()

        self.task_processor: Optional[asyncio.Task] = None

    def _setup_components(self):
        """Setup agent components"""
        # Setup logger
        self.logger = logging.getLogger(f"Agent_{self.id}")
        self._setup_logging()

        # Initialize memory
        self.memory = EnhancedMemory()

        # Initialize task queue
        self.task_queue = asyncio.Queue(
            maxsize=self.agent_config.max_queue_size if self.agent_config else 100
        )

        # Initialize state
        self.status = AgentStatus.IDLE
        self._task_history = []

    def _setup_logging(self):
        """Setup logging configuration"""
        level = logging.DEBUG if self.verbose else logging.INFO
        self.logger.setLevel(level)

        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    async def execute_task(self, task: Union[str, Dict], context: Optional[Dict] = None) -> Dict[str, Any]:
        """Execute a task with enhanced context handling"""
        try:
            # Convert string task to dict if needed
            if isinstance(task, str):
                task = {
                    "id": str(uuid.uuid4()),
                    "description": task,
                    "type": "default",
                    "created_at": datetime.now().isoformat()
                }

            # Update status
            self.status = AgentStatus.BUSY

            try:
                # Process task
                result = await self._process_task(task, context)

                # Store in history
                self._task_history.append({
                    "task": task,
                    "result": result,
                    "timestamp": datetime.now().isoformat()
                })

                return result
            finally:
                # Reset status
                self.status = AgentStatus.IDLE

        except Exception as e:
            self.logger.error(f"Task execution failed: {str(e)}")
            return {
                "status": "error",
                "error": str(e)
            }

    async def add_task(self, task: Dict[str, Any]) -> str:
        """Add a task to the queue"""
        if self.status == AgentStatus.STOPPED:
            raise RuntimeError("Agent is stopped and cannot accept tasks")

        task_id = str(uuid.uuid4())
        await self.task_queue.put({
            "id": task_id,
            "data": task,
            "created_at": datetime.now().isoformat()
        })

        self.logger.debug(f"Added task {task_id}")
        return task_id

    async def _process_tasks(self) -> None:
        """Process tasks from the queue"""
        while True:
            if self.status == AgentStatus.STOPPED:
                break

            try:
                # Get task from queue
                task = await self.task_queue.get()
                self.status = AgentStatus.BUSY

                try:
                    # Process task
                    result = await self.execute_task(task)

                    # Store result
                    self._task_history.append({
                        "task": task,
                        "result": result,
                        "timestamp": datetime.now().isoformat()
                    })
                finally:
                    self.task_queue.task_done()
                    self.status = AgentStatus.IDLE

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Task processing error: {str(e)}")
                await asyncio.sleep(1)

    def evaluate_task_suitability(self, task: Dict[str, Any]) -> float:
        """Evaluate task suitability - to be implemented by specific agent types"""
        return 0.5

    async def start(self) -> None:
        """Start the agent and its task processor"""
        try:
            self.logger.info(f"Starting agent {self.id}")
            self.task_processor = asyncio.create_task(self._process_tasks())
            self.status = AgentStatus.IDLE
            self.logger.info(f"Agent {self.id} started successfully")
        except Exception as e:
            self.logger.error(f"Failed to start agent: {str(e)}")
            self.status = AgentStatus.ERROR
            raise

    async def stop(self) -> None:
        """Stop the agent and cleanup"""
        try:
            self.logger.info(f"Stopping agent {self.id}")
            self.status = AgentStatus.STOPPED

            if self.task_processor:
                self.task_processor.cancel()
                try:
                    await self.task_processor
                except asyncio.CancelledError:
                    pass

            # Close any resources
            await self._cleanup()

            self.logger.info(f"Agent {self.id} stopped successfully")
        except Exception as e:
            self.logger.error(f"Error stopping agent: {str(e)}")
            raise

    async def _cleanup(self) -> None:
        """Cleanup resources - can be overridden by specific agents"""
        pass
