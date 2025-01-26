from typing import Dict, Any, Optional, List
from datetime import datetime
import asyncio
import logging
from abc import ABC, abstractmethod
import uuid
import json
import base64
import hashlib
from functools import wraps

from pilott.core.config import AgentConfig, LLMConfig, LogConfig
from pilott.core.status import AgentStatus
from pilott.delegation.task_delegator import TaskDelegator
from pilott.engine.llm import LLMHandler
from pilott.knowledge.knowledge_manager import KnowledgeManager
from pilott.memory.enhanced_memory import EnhancedMemory


def _secure_agent_state(func):
    """Decorator to verify agent state integrity"""
    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        if not hasattr(self, '_state_hash') or not self._verify_state():
            raise RuntimeError("Agent state verification failed")
        result = await func(self, *args, **kwargs)
        self._update_state_hash()
        return result
    return wrapper


class BaseAgent(ABC):
    """Base agent class for LLM-powered decision making"""

    def __init__(self,
                 agent_config: AgentConfig,
                 llm_config: LLMConfig,
                 log_config: Optional[LogConfig] = None,
                 verbose: bool = False):

        if not llm_config:
            raise ValueError("LLMConfig is required")

        # Core components
        self.agent_config = agent_config.model_dump()
        self.id = str(uuid.uuid4())
        self.role = str(agent_config.role_type)
        self.status = AgentStatus.IDLE
        self.name = str(agent_config.role)
        self.last_heartbeat = datetime.now()

        # Initialize LLM handler
        llm_dict = llm_config.model_dump()
        self.llm_handler = LLMHandler(llm_dict)

        # Enhanced components
        self.enhanced_memory = EnhancedMemory()
        self.knowledge_manager = KnowledgeManager()
        self.task_delegator = TaskDelegator(self)

        # Task management with proper initialization
        self.tasks: Dict[str, Dict[str, Any]] = {}
        self.max_queue_size = int(agent_config.max_queue_size)
        self.task_queue = asyncio.Queue(maxsize=self.max_queue_size)
        self.task_processor = None

        # Relationships
        self.parent_agent = None
        self.child_agents = {}

        # Tools and relationships
        self.tools = []  # Initialize as empty list
        self.knowledge_sources = agent_config.knowledge_sources
        self.parent_agent = None
        self.child_agents: Dict[str, 'BaseAgent'] = {}

        # Metrics
        self.metrics = {
            'total_tasks': 0,
            'completed_tasks': 0,
            'failed_tasks': 0,
            'queue_utilization': 0.0,
            'success_rate': 1.0,
            'resource_usage': 0.0
        }

        # Logging setup
        self.logger = logging.getLogger(f"Agent_{self.id}")
        self._setup_logging(verbose or agent_config.verbose)

        # Security
        self._encoded_config = self._encode_config(agent_config.model_dump(mode='json'))
        self._encoded_llm = self._encode_config(llm_config.to_dict())
        self._update_state_hash()

    def _encode_config(self, config: Any) -> str:
        """Encode configuration ensuring primitive types"""
        if isinstance(config, dict):
            # Convert all values to strings to ensure serializability
            serializable_config = {
                str(k): str(v) if not isinstance(v, (int, float, bool)) else v
                for k, v in config.items()
            }
            return base64.b85encode(json.dumps(serializable_config).encode()).decode()
        else:
            return base64.b85encode(str(config).encode()).decode()

    def _decode_config(self, encoded: str) -> Any:
        config_str = base64.b85decode(encoded.encode()).decode()
        try:
            return json.loads(config_str)
        except:
            return config_str

    async def reset(self) -> None:
        """Reset agent state"""
        self.tasks.clear()
        self.task_queue = asyncio.Queue(maxsize=self.max_queue_size)
        self.metrics = {
            'total_tasks': 0,
            'completed_tasks': 0,
            'failed_tasks': 0,
            'queue_utilization': 0.0,
            'success_rate': 1.0,
            'resource_usage': 0.0
        }
        self.status = AgentStatus.IDLE
        self.last_heartbeat = datetime.now()

    async def send_heartbeat(self) -> datetime:
        """Send heartbeat signal"""
        self.last_heartbeat = datetime.now()
        return self.last_heartbeat

    def _update_state_hash(self):
        state = f"{self._encoded_config}{self._encoded_llm}{self.id}{self.status}"
        self._state_hash = hashlib.sha256(state.encode()).hexdigest()

    def _verify_state(self) -> bool:
        current = f"{self._encoded_config}{self._encoded_llm}{self.id}{self.status}"
        return self._state_hash == hashlib.sha256(current.encode()).hexdigest()

    @_secure_agent_state
    async def _process_context(self) -> Dict[str, Any]:
        """Internal context processing"""
        config = self._decode_config(self._encoded_config)
        return {
            'goal': config.goal,
            'description': config.description,
            'backstory': config.backstory,
            'role': self.role,
            'status': self.status.value,
            'tools': self.tools,
            'knowledge': self.knowledge_sources,
            'metrics': await self.get_metrics()
        }

    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute task and return result"""
        try:
            result = await self._process_task(task)
            return {
                "status": "success",
                **result
            }
        except Exception as e:
            self.logger.error(f"Task execution error: {str(e)}")
            return {
                "status": "error",
                "error": str(e)
            }

    async def _execute_with_llm(self, task: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute task using LLM"""
        messages = [
            {
                "role": "system",
                "content": f"""You are an AI agent with:
                    Goal: {context['goal']}
                    Description: {context['description']}
                    Backstory: {context['backstory']}
                    
                    Make decisions based on this context and your capabilities."""
            },
            {
                "role": "user",
                "content": f"Task to execute: {json.dumps(task)}"
            }
        ]

        try:
            llm_response = await self.llm_handler.generate_response(messages)
            tool_calls = llm_response.get('tool_calls')

            if tool_calls:
                return await self._handle_tool_calls(tool_calls, task)

            return {
                "status": "completed",
                "output": llm_response['content']
            }

        except Exception as e:
            self.logger.error(f"LLM execution error: {str(e)}")
            raise

    async def _handle_tool_calls(self, tool_calls: List[Dict], task: Dict) -> Dict[str, Any]:
        """Handle tool calls from LLM"""
        results = []
        for tool_call in tool_calls:
            try:
                tool_name = tool_call["function"]["name"]
                if tool_name in self.tools:
                    args = json.loads(tool_call["function"]["arguments"])
                    result = await self.tools[tool_name](**args)
                    results.append(result)
            except Exception as e:
                self.logger.error(f"Tool execution error: {str(e)}")

        return {
            "status": "completed",
            "output": results[0] if len(results) == 1 else results
        }

    def _process_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Process and validate execution result"""
        if not isinstance(result, dict) or 'status' not in result:
            raise ValueError("Invalid execution result format")
        return result

    # Keep original methods below
    def _setup_logging(self, verbose: bool):
        """Setup basic logging configuration"""
        level = logging.DEBUG if verbose else logging.INFO
        self.logger.setLevel(level)

        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    def _setup_logging_from_config(self, log_config: 'LogConfig'):
        """Setup logging using LogConfig"""
        level = logging.DEBUG if log_config.verbose else logging.getLevelName(log_config.log_level)
        self.logger.setLevel(level)

        if not self.logger.handlers:
            if log_config.log_to_file:
                handler = logging.FileHandler(f"{log_config.log_dir}/agent_{self.id}.log")
            else:
                handler = logging.StreamHandler()

            formatter = logging.Formatter(log_config.log_format)
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    # Original methods for task management and metrics
    async def add_child_agent(self, agent: 'BaseAgent'):
        """Add a child agent to this agent"""
        try:
            agent.parent_agent = self
            self.child_agents[agent.id] = agent
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
            await agent.stop()
            agent.parent_agent = None
            del self.child_agents[agent_id]
            self.logger.info(f"Removed child agent {agent_id}")
        except Exception as e:
            self.logger.error(f"Failed to remove child agent: {str(e)}")
            raise

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
        task_entry = {
            "id": task_id,
            "status": "queued",
            "created_at": datetime.now().isoformat(),
            "data": task.copy()  # Create a copy of the task data
        }

        self.tasks[task_id] = task_entry
        await self.task_queue.put(task_entry)
        self.logger.debug(f"Added task {task_id}")
        return task_id

    async def _process_tasks(self):
        """Process tasks from the queue"""
        while True:
            if self.status == AgentStatus.STOPPED:
                break

            try:
                task_entry = await self.task_queue.get()
                self.status = AgentStatus.BUSY

                try:
                    result = await self.execute_task(task_entry["data"])

                    # Update task entry with result
                    self.tasks[task_entry["id"]].update({
                        "status": result.get("status", "completed"),
                        "result": result,
                        "completed_at": datetime.now().isoformat()
                    })
                except Exception as e:
                    self.tasks[task_entry["id"]].update({
                        "status": "failed",
                        "result": {"status": "error", "error": str(e)},
                        "failed_at": datetime.now().isoformat()
                    })
                finally:
                    self.task_queue.task_done()
                    self.status = AgentStatus.IDLE

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Task processing error: {str(e)}")
                await asyncio.sleep(1)

    async def _delegate_task_to(self, task: Dict[str, Any], agent_id: str) -> Dict[str, Any]:
        """Delegate task to a specific agent and track the delegation"""
        if agent_id not in self.child_agents:
            raise ValueError(f"Agent {agent_id} not found")

        agent = self.child_agents[agent_id]
        task_id = await agent.add_task(task)

        # Wait for task completion
        while True:
            if task_id not in agent.tasks:
                raise ValueError(f"Task {task_id} not found")

            task_status = agent.tasks[task_id]
            if task_status['status'] in ['completed', 'failed']:
                # Record delegation result
                result = task_status.get('result', {})
                self.task_delegator.record_delegation(agent_id, task, result)
                return result

            await asyncio.sleep(0.1)

    def _should_delegate(self, task: Dict[str, Any]) -> bool:
        """Determine if task should be delegated"""
        if not self.agent_config.can_delegate or not self.child_agents:
            return False

        if task.get('complexity', 0) > self.agent_config.max_task_complexity:
            return True

        if self.task_queue.qsize() >= self.agent_config.max_queue_size * 0.8:
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
        success_rate = (self.metrics['completed_tasks'] / total_tasks) if total_tasks > 0 else 1.0
        queue_size = self.task_queue.qsize()

        self.metrics.update({
            'success_rate': success_rate,
            'queue_utilization': queue_size / self.max_queue_size if self.max_queue_size > 0 else 0.0,
            'resource_usage': queue_size / (self.max_queue_size * 2) if self.max_queue_size > 0 else 0.0
        })

        return self.metrics.copy()