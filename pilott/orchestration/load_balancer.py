from typing import Dict, List, Tuple, Optional
import asyncio
from datetime import datetime
import logging
from pydantic import BaseModel, Field
import traceback

from pilott.core.agent import BaseAgent, AgentStatus


class LoadBalancerConfig(BaseModel):
    """Configuration for the load balancer"""
    check_interval: int = Field(
        default=30,
        description="Interval in seconds between load checks"
    )
    overload_threshold: float = Field(
        default=0.8,
        description="Load threshold above which an agent is considered overloaded"
    )
    underload_threshold: float = Field(
        default=0.2,
        description="Load threshold below which an agent is considered underloaded"
    )
    max_tasks_per_agent: int = Field(
        default=10,
        description="Maximum number of tasks per agent"
    )
    balance_batch_size: int = Field(
        default=3,
        description="Maximum number of tasks to move in one balancing operation"
    )
    min_load_difference: float = Field(
        default=0.3,
        description="Minimum load difference to trigger task movement"
    )


class LoadBalancer:
    """Manages load distribution across agents in the system"""

    def __init__(self, orchestrator, config: Optional[Dict] = None):
        self.orchestrator = orchestrator
        self.config = LoadBalancerConfig(**(config or {}))
        self.logger = logging.getLogger("LoadBalancer")
        self.running = False
        self.balancing_task: Optional[asyncio.Task] = None
        self._setup_logging()

    def _setup_logging(self):
        """Setup logging for the load balancer"""
        self.logger.setLevel(logging.DEBUG if self.orchestrator.verbose else logging.INFO)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(
                logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            )
            self.logger.addHandler(handler)

    async def start(self):
        """Start the load balancing process"""
        if self.running:
            self.logger.warning("Load balancer is already running")
            return

        self.running = True
        self.balancing_task = asyncio.create_task(self._balancing_loop())
        self.logger.info("Load balancer started")

    async def stop(self):
        """Stop the load balancing process"""
        if not self.running:
            return

        self.running = False
        if self.balancing_task:
            self.balancing_task.cancel()
            try:
                await self.balancing_task
            except asyncio.CancelledError:
                pass
        self.logger.info("Load balancer stopped")

    async def _balancing_loop(self):
        """Main loop for load balancing"""
        while self.running:
            try:
                await self._balance_system_load()
                await asyncio.sleep(self.config.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in balancing loop: {str(e)}\n{traceback.format_exc()}")
                await asyncio.sleep(self.config.check_interval)  # Still sleep on error

    async def _balance_system_load(self):
        """Balance load across all agents"""
        try:
            overloaded, underloaded = await self._analyze_agent_loads()

            if not overloaded or not underloaded:
                return

            await self._redistribute_tasks(overloaded, underloaded)

        except Exception as e:
            self.logger.error(f"Load balancing error: {str(e)}\n{traceback.format_exc()}")

    async def _analyze_agent_loads(self) -> Tuple[List[BaseAgent], List[BaseAgent]]:
        """Analyze and categorize agent loads"""
        overloaded = []
        underloaded = []

        try:
            agents = await self._get_available_agents()

            for agent in agents:
                load = await self._calculate_agent_load(agent)

                if load > self.config.overload_threshold:
                    overloaded.append(agent)
                elif load < self.config.underload_threshold:
                    underloaded.append(agent)

            if overloaded:
                self.logger.debug(f"Found {len(overloaded)} overloaded agents")
            if underloaded:
                self.logger.debug(f"Found {len(underloaded)} underloaded agents")

        except Exception as e:
            self.logger.error(f"Error analyzing agent loads: {str(e)}")
            return [], []

        return overloaded, underloaded

    async def _get_available_agents(self) -> List[BaseAgent]:
        """Get list of available agents"""
        return [
            agent for agent in self.orchestrator.child_agents.values()
            if agent.status != AgentStatus.STOPPED
        ]

    async def _calculate_agent_load(self, agent: BaseAgent) -> float:
        """Calculate comprehensive load for an agent"""
        try:
            metrics = await agent.get_metrics()

            # Calculate different types of load
            task_load = metrics['total_tasks'] / self.config.max_tasks_per_agent
            queue_load = metrics['queue_utilization']
            error_rate = 1 - metrics['success_rate']  # Convert success rate to error rate

            # Weighted average with error rate penalty
            base_load = (
                    0.4 * task_load +
                    0.4 * queue_load +
                    0.2 * error_rate
            )

            return min(1.0, base_load)  # Cap at 1.0

        except Exception as e:
            self.logger.error(f"Error calculating agent load: {str(e)}")
            return 0.0

    async def _redistribute_tasks(self, overloaded: List[BaseAgent],
                                  underloaded: List[BaseAgent]):
        """Move tasks from overloaded to underloaded agents"""
        for over_agent in overloaded:
            try:
                moveable_tasks = await self._get_moveable_tasks(over_agent)
                moves_made = 0

                for task in moveable_tasks:
                    if moves_made >= self.config.balance_batch_size:
                        break

                    best_agent = await self._find_best_agent(task, underloaded)
                    if best_agent:
                        try:
                            await self._move_task(task, over_agent, best_agent)
                            moves_made += 1
                        except Exception as e:
                            self.logger.error(f"Failed to move task {task['id']}: {str(e)}")

                if moves_made > 0:
                    self.logger.info(f"Moved {moves_made} tasks from agent {over_agent.id}")

            except Exception as e:
                self.logger.error(f"Error redistributing tasks for agent {over_agent.id}: {str(e)}")

    async def _get_moveable_tasks(self, agent: BaseAgent) -> List[Dict]:
        """Get tasks that can be moved to other agents"""
        try:
            return [
                task for task in agent.tasks.values()
                if self._is_task_moveable(task)
            ]
        except Exception as e:
            self.logger.error(f"Error getting moveable tasks: {str(e)}")
            return []

    def _is_task_moveable(self, task: Dict) -> bool:
        """Check if a task can be moved"""
        return (
                task['status'] == 'queued' and
                not task.get('locked', False) and
                not task.get('in_progress', False) and
                not task.get('unmoveable', False)
        )

    async def _find_best_agent(self, task: Dict, candidates: List[BaseAgent]) -> Optional[BaseAgent]:
        """Find the best agent for a specific task"""
        best_agent = None
        best_score = float('-inf')

        try:
            for agent in candidates:
                if await self._can_accept_task(agent):
                    score = await self._calculate_agent_suitability(agent, task)
                    if score > best_score:
                        best_score = score
                        best_agent = agent

        except Exception as e:
            self.logger.error(f"Error finding best agent: {str(e)}")

        return best_agent

    async def _can_accept_task(self, agent: BaseAgent) -> bool:
        """Check if an agent can accept new tasks"""
        try:
            metrics = await agent.get_metrics()
            return (
                    agent.status != AgentStatus.STOPPED and
                    metrics['queue_utilization'] < self.config.overload_threshold
            )
        except Exception:
            return False

    async def _calculate_agent_suitability(self, agent: BaseAgent, task: Dict) -> float:
        """Calculate how suitable an agent is for a task"""
        try:
            # Base suitability from agent's own evaluation
            base_score = agent.evaluate_task_suitability(task)

            # Current load penalty
            load = await self._calculate_agent_load(agent)
            load_penalty = load * 0.5  # Up to 50% penalty based on load

            # Performance bonus based on success rate
            metrics = await agent.get_metrics()
            performance_bonus = metrics['success_rate'] * 0.2  # Up to 20% bonus

            return base_score - load_penalty + performance_bonus

        except Exception as e:
            self.logger.error(f"Error calculating agent suitability: {str(e)}")
            return float('-inf')

    async def _move_task(self, task: Dict, from_agent: BaseAgent, to_agent: BaseAgent):
        """Move a task from one agent to another"""
        task_id = task['id']

        try:
            # Mark task as being moved
            task['in_progress'] = True

            # Remove from source agent
            await from_agent.remove_task(task_id)

            # Add to destination agent
            await to_agent.add_task(task)

            await self.orchestrator.broadcast_update("task_moved", {
                "task_id": task_id,
                "from_agent": from_agent.id,
                "to_agent": to_agent.id,
                "timestamp": datetime.now().isoformat()
            })

            self.logger.debug(f"Moved task {task_id} from {from_agent.id} to {to_agent.id}")

        except Exception as e:
            self.logger.error(f"Failed to move task {task_id}: {str(e)}")
            # Try to restore task to original agent
            try:
                if not task.get('locked'):
                    await from_agent.add_task(task)
            except Exception as restore_error:
                self.logger.error(f"Failed to restore task {task_id}: {str(restore_error)}")
            raise