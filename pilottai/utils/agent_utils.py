from typing import Dict, List, Union, Tuple
import asyncio
import logging

from pilottai.task.task import Task
from pilottai.agent.agent import Agent
from pilottai.engine.llm import LLMHandler


class AgentUtils:
    """
    Utility class for agent operations, including task assignment and management.
    Contains static methods to handle common agent operations.
    """

    @staticmethod
    async def assign_task(
        task: Union[Dict, Task],
        agents: List[Agent],
        llm_handler: LLMHandler,
        max_concurrent_agents: int = 1,
        assignment_strategy: str = "llm"
    ) -> Tuple[Agent, float]:
        """
        Assign a task to the most suitable agent using specified strategy.

        Args:
            task: The task to assign
            agents: List of available agents
            llm_handler: LLM handler for making decisions
            max_concurrent_agents: Maximum number of agents to assign (default: 1)
            assignment_strategy: Strategy for assignment ('suitability', 'llm', 'round_robin')

        Returns:
            Tuple of (assigned_agent, confidence_score)
        """
        logger = logging.getLogger("AgentUtils")

        if not agents:
            raise ValueError("No agents available for task assignment")

        if isinstance(task, dict):
            task_obj = Task(**task)
        else:
            task_obj = task

        if assignment_strategy == "llm":
            return await AgentUtils._assign_task_using_llm(task_obj, agents, llm_handler)
        elif assignment_strategy == "suitability":
            return await AgentUtils._assign_task_by_suitability(task_obj, agents)
        elif assignment_strategy == "round_robin":
            return AgentUtils._assign_task_round_robin(task_obj, agents)
        else:
            logger.warning(f"Unknown assignment strategy: {assignment_strategy}, falling back to LLM")
            return await AgentUtils._assign_task_using_llm(task_obj, agents, llm_handler)

    @staticmethod
    async def _assign_task_using_llm(
        task: Task,
        agents: List[Agent],
        llm_handler: LLMHandler
    ) -> Tuple[Agent, float]:
        """
        Use LLM to decide which agent should handle a task based on capabilities and task requirements.

        Args:
            task: Task to assign
            agents: Available agents
            llm_handler: LLM handler for decision making

        Returns:
            Tuple of (assigned_agent, confidence_score)
        """
        # Create a summary of each agent's capabilities
        agent_descriptions = []
        for i, agent in enumerate(agents):
            desc = f"Agent {i + 1}:\n"
            desc += f"  Role: {agent.role}\n"
            desc += f"  Goal: {agent.goal}\n"
            desc += f"  Description: {agent.description}\n"
            agent_descriptions.append(desc)

        agent_info = '\n'.join(agent_descriptions)

        # Create the prompt for task assignment
        prompt = f"""
        # Task Assignment Decision

        ## Task Details
        Description: {task.description}
        Priority: {getattr(task, 'priority', 'Normal')}
        Required Capabilities: {getattr(task, 'required_capabilities', 'None specified')}

        ## Available Agents
        {agent_info}

        Based on the above information, determine which agent is best suited for this task.
        Provide your reasoning and a confidence score (0.0-1.0) for the assignment.

        Format your response as:
        ```json
        {{
            "selected_agent": <agent_number>,
            "confidence": <confidence_score>,
            "reasoning": "<your reasoning>"
        }}
        ```
        """

        # Generate response from LLM
        messages = [
            {"role": "system",
             "content": "You are an AI task allocation expert. Your job is to match task to the most suitable agent based on capabilities, availability, and task requirements."},
            {"role": "user", "content": prompt}
        ]

        response = await llm_handler.generate_response(messages)

        # Parse the response
        try:
            content = response["content"]
            # Extract JSON from potential markdown code block
            if "```json" in content:
                json_part = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                json_part = content.split("```")[1].split("```")[0].strip()
            else:
                json_part = content

            # Use safer eval-based parsing
            import ast
            decision = ast.literal_eval(json_part.replace('true', 'True').replace('false', 'False'))

            selected_idx = int(decision["selected_agent"]) - 1  # Convert to 0-based index
            confidence = float(decision["confidence"])

            if 0 <= selected_idx < len(agents):
                return agents[selected_idx], confidence
            else:
                # Fallback to first agent if index is invalid
                logging.warning(f"Invalid agent index {selected_idx}, defaulting to first agent")
                return agents[0], 0.5

        except Exception as e:
            logging.error(f"Error parsing LLM response for task assignment: {e}")
            # Fallback to first available agent
            return agents[0], 0.5

    @staticmethod
    async def _assign_task_by_suitability(
        task: Task,
        agents: List[Agent]
    ) -> Tuple[Agent, float]:
        """
        Assign task based on each agent's self-reported suitability score.

        Args:
            task: Task to assign
            agents: Available agents

        Returns:
            Tuple of (assigned_agent, suitability_score)
        """
        # Convert task to dict if needed for compatibility
        task_dict = task.__dict__ if not isinstance(task, dict) else task

        best_agent = None
        best_score = -1

        # Collect suitability scores from all agents
        scores = []
        for agent in agents:
            try:
                score = await agent.evaluate_task_suitability(task_dict)
                scores.append((agent, score))
            except Exception as e:
                logging.error(f"Error getting suitability from agent {agent.id}: {e}")
                scores.append((agent, 0.0))

        # Sort by score and pick the best
        scores.sort(key=lambda x: x[1], reverse=True)

        if scores:
            return scores[0]
        else:
            # Fallback to first agent with minimum confidence
            return agents[0], 0.1

    @staticmethod
    def _assign_task_round_robin(
        task: Task,
        agents: List[Agent]
    ) -> Tuple[Agent, float]:
        """
        Simple round-robin assignment (static sequential counter).

        Args:
            task: Task to assign
            agents: Available agents

        Returns:
            Tuple of (assigned_agent, confidence_score)
        """
        # Use a class variable to track last assigned agent
        if not hasattr(AgentUtils, "_last_assigned_index"):
            AgentUtils._last_assigned_index = -1

        # Find available agents
        available_agents = [a for a in agents if a.status != "BUSY"]

        if not available_agents:
            logging.warning("No available agents, assigning to potentially busy agent")
            available_agents = agents

        # Update index and wrap around
        AgentUtils._last_assigned_index = (AgentUtils._last_assigned_index + 1) % len(available_agents)

        # Return selected agent with medium confidence
        return available_agents[AgentUtils._last_assigned_index], 0.7

    @staticmethod
    async def distribute_tasks(
        tasks: List[Task],
        agents: List[Agent],
        llm_handler: LLMHandler,
        strategy: str = "llm",
        parallel: bool = True
    ) -> Dict[str, Tuple[Agent, Task]]:
        """
        Distribute multiple task among available agents.

        Args:
            tasks: List of task to distribute
            agents: Available agents
            llm_handler: LLM handler
            strategy: Assignment strategy
            parallel: Whether to process assignments in parallel

        Returns:
            Dictionary mapping task IDs to (agent, task) tuples
        """
        assignments = {}

        if parallel:
            # Create task for parallel execution
            assignment_tasks = []
            for task in tasks:
                assignment_tasks.append(
                    AgentUtils.assign_task(task, agents, llm_handler, assignment_strategy=strategy)
                )

            # Execute all assignments in parallel
            results = await asyncio.gather(*assignment_tasks, return_exceptions=True)

            # Process results
            for i, result in enumerate(results):
                task = tasks[i]
                if isinstance(result, Exception):
                    logging.error(f"Error assigning task {task.id}: {result}")
                    continue

                agent, confidence = result
                assignments[task.id] = (agent, task)
        else:
            # Sequential assignment
            for task in tasks:
                try:
                    agent, confidence = await AgentUtils.assign_task(
                        task, agents, llm_handler, assignment_strategy=strategy
                    )
                    assignments[task.id] = (agent, task)
                except Exception as e:
                    logging.error(f"Error assigning task {task.id}: {e}")

        return assignments
