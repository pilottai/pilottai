from typing import Dict, List, Optional, Union
import asyncio

from pilott.core.base_agent import BaseAgent
from pilott.config.config import AgentConfig, LLMConfig
from pilott.core.task import Task, TaskResult
from pilott.tools.tool import Tool
from pilott.knowledge.knowledge import DataManager


class Agent(BaseAgent):
    """
    Extended agent implementation with customized functionality
    """

    def __init__(
        self,
        role: str,
        goal: str,
        description: str,
        tasks: Union[str, Task, List[str], List[Task]],
        tools: Optional[List[Tool]] = None,
        source: Optional[DataManager] = None,
        config: Optional[AgentConfig] = None,
        llm_config: Optional[LLMConfig] = None,
        output_format=None,
        output_sample=None,
        memory_enabled: bool = True,
        reasoning: bool = True,
        feedback: bool = False
    ):
        super().__init__(
            role=role,
            goal=goal,
            description=description,
            tasks=tasks,
            tools=tools,
            source=source,
            config=config,
            llm_config=llm_config,
            output_format=output_format,
            output_sample=output_sample,
            memory_enabled=memory_enabled,
            reasoning=reasoning,
            feedback=feedback
        )
        # Custom initialization code here
        self.specializations = ["research", "analysis", "planning"]

    async def execute_task(self, task: Union[Dict, Task]) -> Optional[TaskResult]:
        """
        Override execute_task with custom implementation
        """
        # Custom pre-execution logic
        self.logger.info(f"Agent executing task: {task}")

        # Call parent implementation
        result = await super().execute_task(task)

        # Custom post-execution logic
        if result and result.success:
            self.logger.info(f"Task completed successfully in {result.execution_time}s")

        return result

    async def _plan_execution(self, task: str) -> Dict:
        """Enhanced planning capabilities"""
        # Custom planning logic with more detailed steps
        messages = [
            {
                "role": "system",
                "content": self._get_enhanced_system_prompt()
            },
            {
                "role": "user",
                "content": f"Plan detailed execution for task: {task}\n\n"
                           f"Available tools: {list(self.tools.keys() if self.tools else [])}\n"
                           f"Consider the most efficient approach."
            }
        ]

        if self.llm:
            response = await self.llm.generate_response(messages)
            try:
                plan = self._parse_json_response(response["content"])
                return {"steps": plan}
            except Exception as e:
                self.logger.warning(f"Error parsing plan: {e}, using fallback")
                return {"steps": [{"action": "direct_execution", "input": task}]}
        else:
            return {"steps": [{"action": "direct_execution", "input": task}]}

    def _get_enhanced_system_prompt(self) -> str:
        """Enhanced system prompt for better agent guidance"""
        basic_prompt = self._get_system_prompt()

        enhanced_prompt = f"""{basic_prompt}

        When planning task execution:
        1. Break complex tasks into smaller, manageable steps
        2. Prioritize using specialized tools when available
        3. Consider efficiency and resource constraints
        4. Maintain focus on the primary goal: {self.goal}

        Provide clear, structured output that can be easily parsed."""

        return enhanced_prompt
