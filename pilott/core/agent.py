from typing import Dict, Any
from datetime import datetime
import asyncio
import logging
from abc import ABC, abstractmethod
import uuid
from enum import Enum


class AgentRole(str, Enum):
    ORCHESTRATOR = "orchestrator"
    WORKER = "worker"
    HYBRID = "hybrid"

class AgentStatus(str, Enum):
    IDLE = "idle"
    BUSY = "busy"
    WAITING = "waiting"
    ERROR = "error"
    STOPPED = "stopped"


class BaseAgent(ABC):
    """Base agent class with core functionality"""

    """Base agent class with core functionality"""

    def __init__(self, config: 'AgentConfig'):
        # Basic attributes
        self.config = config
        self.id = str(uuid.uuid4())
        self.role = config.role_type
        self.status = AgentStatus.IDLE
        self.name = config.role

        # Agent relationships
        self.parent_agent = None
        self.child_agents: Dict[str, 'BaseAgent'] = {}

        # Task management
        self.tasks: Dict[str, Dict] = {}
        self.task_queue = asyncio.Queue(maxsize=config.max_queue_size)
        self.task_processor = None

        # Memory management
        self.memory = []
        if config.memory_enabled:
            self.memory = []

        # Tools and capabilities
        self.tools = config.tools
        self.knowledge_sources = config.knowledge_sources

        # Metrics
        self.metrics = {
            'total_tasks': 0,
            'completed_tasks': 0,
            'failed_tasks': 0
        }

        # Setup logging
        self.logger = logging.getLogger(f"Agent_{self.id}")
        self._setup_logging(config.verbose)

    async def add_child_agent(self, agent: 'BaseAgent'):
        """Add a child agent to this agent"""
        try:
            # Set parent reference
            agent.parent_agent = self

            # Add to child agents dictionary
            self.child_agents[agent.id] = agent

            # Start the child agent if not already started
            if agent.status == AgentStatus.IDLE:
                await agent.start()

            self.logger.info(f"Added child agent {agent.id} of type {agent.__class__.__name__}")

            return agent.id
        except Exception as e:
            self.logger.error(f"Failed to add child agent: {str(e)}")
            raise

    async def remove_child_agent(self, agent_id: str):
        """Remove a child agent"""
        if agent_id not in self.child_agents:
            self.logger.warning(f"Agent {agent_id} not found in child agents")
            return

        try:
            agent = self.child_agents[agent_id]

            # Stop the agent
            await agent.stop()

            # Remove parent reference
            agent.parent_agent = None

            # Remove from child agents
            del self.child_agents[agent_id]

            self.logger.info(f"Removed child agent {agent_id}")
        except Exception as e:
            self.logger.error(f"Failed to remove child agent: {str(e)}")
            raise

    def _setup_logging(self, verbose: bool):
        """Setup basic logging configuration"""
        level = logging.DEBUG if verbose else logging.INFO
        self.logger.setLevel(level)

        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    async def start(self):
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

    async def stop(self):
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

            # Stop child agents
            for agent in self.child_agents.values():
                await agent.stop()

            self.logger.info(f"Agent {self.id} stopped successfully")
        except Exception as e:
            self.logger.error(f"Error stopping agent: {str(e)}")
            raise

    async def add_task(self, task: Dict[str, Any]) -> str:
        """Add a task to the queue"""
        if self.status == AgentStatus.STOPPED:
            raise RuntimeError("Agent is stopped and cannot accept tasks")

        task_id = str(uuid.uuid4())
        task['id'] = task_id
        task['status'] = 'queued'
        task['created_at'] = datetime.now().isoformat()

        self.tasks[task_id] = task
        await self.task_queue.put(task)
        self.logger.debug(f"Added task {task_id}")
        return task_id

    async def _process_tasks(self):
        """Process tasks from the queue"""
        while True:
            if self.status == AgentStatus.STOPPED:
                break

            try:
                task = await self.task_queue.get()
                self.status = AgentStatus.BUSY

                try:
                    result = await self.execute_task(task)
                    self.tasks[task['id']].update({
                        'status': 'completed',
                        'result': result,
                        'completed_at': datetime.now().isoformat()
                    })
                    self.metrics['completed_tasks'] += 1
                except Exception as e:
                    self.logger.error(f"Task execution error: {str(e)}")
                    self.tasks[task['id']].update({
                        'status': 'failed',
                        'error': str(e),
                        'failed_at': datetime.now().isoformat()
                    })
                    self.metrics['failed_tasks'] += 1
                finally:
                    self.task_queue.task_done()
                    self.status = AgentStatus.IDLE

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Task processing error: {str(e)}")
                await asyncio.sleep(1)

    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a task using available tools and capabilities"""
        self.metrics['total_tasks'] += 1

        # Check if task should be delegated
        if self._should_delegate(task):
            return await self._delegate_task(task)

        # Execute task based on type
        task_type = task.get('type', 'default')
        handler = getattr(self, f"handle_{task_type}", None)

        if handler:
            return await handler(task)
        else:
            return await self._default_task_handler(task)

    def _should_delegate(self, task: Dict[str, Any]) -> bool:
        """Determine if task should be delegated"""
        if not self.config.can_delegate or not self.child_agents:
            return False

        # Check task complexity
        if task.get('complexity', 0) > self.config.max_task_complexity:
            return True

        # Check queue capacity
        if self.task_queue.qsize() >= self.config.max_queue_size * 0.8:
            return True

        return False

    async def _delegate_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Delegate task to a child agent"""
        best_agent = None
        best_score = -1

        for agent in self.child_agents.values():
            if agent.status != AgentStatus.BUSY:
                score = agent.evaluate_task_suitability(task)
                if score > best_score:
                    best_score = score
                    best_agent = agent

        if best_agent:
            return await best_agent.add_task(task)
        else:
            raise ValueError("No suitable agent found for delegation")

    async def _default_task_handler(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Default task handling implementation"""
        raise NotImplementedError("Subclasses must implement task handling")

    @abstractmethod
    def evaluate_task_suitability(self, task: Dict[str, Any]) -> float:
        """Evaluate how suitable this agent is for a task"""
        pass

    async def get_status(self) -> Dict[str, Any]:
        """Get agent status and metrics"""
        return {
            'id': self.id,
            'name': self.name,
            'role': self.role,
            'status': self.status,
            'metrics': self.metrics,
            'queue_size': self.task_queue.qsize(),
            'child_agents': len(self.child_agents)
        }

    async def get_metrics(self) -> Dict[str, Any]:
        """Get agent metrics"""
        total_tasks = self.metrics['total_tasks']
        if total_tasks == 0:
            success_rate = 0
        else:
            success_rate = self.metrics['completed_tasks'] / total_tasks

        return {
            'total_tasks': total_tasks,
            'completed_tasks': self.metrics['completed_tasks'],
            'failed_tasks': self.metrics['failed_tasks'],
            'success_rate': success_rate,
            'queue_utilization': self.task_queue.qsize() / self.config.max_queue_size
        }