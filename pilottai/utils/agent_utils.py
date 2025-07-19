from typing import Dict, List, Union, Tuple
import asyncio
import logging

from pilottai.job.job import Job
from pilottai.agent.agent import Agent
from pilottai.engine.llm import LLMHandler


class AgentUtils:
    """
    Utility class for agent operations, including job assignment and management.
    Contains static methods to handle common agent operations.
    """

    @staticmethod
    async def assign_job(
        job: Union[Dict, Job],
        agents: List[Agent],
        llm_handler: LLMHandler,
        max_concurrent_agents: int = 1,
        assignment_strategy: str = "llm"
    ) -> Tuple[Agent, float]:
        """
        Assign a job to the most suitable agent using specified strategy.

        Args:
            job: The job to assign
            agents: List of available agents
            llm_handler: LLM handler for making decisions
            max_concurrent_agents: Maximum number of agents to assign (default: 1)
            assignment_strategy: Strategy for assignment ('suitability', 'llm', 'round_robin')

        Returns:
            Tuple of (assigned_agent, confidence_score)
        """
        logger = logging.getLogger("AgentUtils")

        if not agents:
            raise ValueError("No agents available for job assignment")

        if isinstance(job, dict):
            job_obj = Job(**job)
        else:
            job_obj = job

        if assignment_strategy == "llm":
            return await AgentUtils._assign_job_using_llm(job_obj, agents, llm_handler)
        elif assignment_strategy == "suitability":
            return await AgentUtils._assign_job_by_suitability(job_obj, agents)
        elif assignment_strategy == "round_robin":
            return AgentUtils._assign_job_round_robin(job_obj, agents)
        else:
            logger.warning(f"Unknown assignment strategy: {assignment_strategy}, falling back to LLM")
            return await AgentUtils._assign_job_using_llm(job_obj, agents, llm_handler)

    @staticmethod
    async def _assign_job_using_llm(
        job: Job,
        agents: List[Agent],
        llm_handler: LLMHandler
    ) -> Tuple[Agent, float]:
        """
        Use LLM to decide which agent should handle a job based on capabilities and job requirements.

        Args:
            job: Job to assign
            agents: Available agents
            llm_handler: LLM handler for decision making

        Returns:
            Tuple of (assigned_agent, confidence_score)
        """
        # Create a summary of each agent's capabilities
        agent_descriptions = []
        for i, agent in enumerate(agents):
            desc = f"Agent {i + 1}:\n"
            desc += f"  Title: {agent.title}\n"
            desc += f"  Goal: {agent.goal}\n"
            desc += f"  Description: {agent.description}\n"
            agent_descriptions.append(desc)

        agent_info = '\n'.join(agent_descriptions)

        # Create the prompt for job assignment
        prompt = f"""
        # Job Assignment Decision

        ## Job Details
        Description: {job.description}
        Priority: {getattr(job, 'priority', 'Normal')}
        Required Capabilities: {getattr(job, 'required_capabilities', 'None specified')}

        ## Available Agents
        {agent_info}

        Based on the above information, determine which agent is best suited for this job.
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
             "content": "You are an AI job allocation expert. Your job is to match job to the most suitable agent based on capabilities, availability, and job requirements."},
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
            logging.error(f"Error parsing LLM response for job assignment: {e}")
            # Fallback to first available agent
            return agents[0], 0.5

    @staticmethod
    async def _assign_job_by_suitability(
        job: Job,
        agents: List[Agent]
    ) -> Tuple[Agent, float]:
        """
        Assign job based on each agent's self-reported suitability score.

        Args:
            job: Job to assign
            agents: Available agents

        Returns:
            Tuple of (assigned_agent, suitability_score)
        """
        # Convert job to dict if needed for compatibility
        job_dict = job.__dict__ if not isinstance(job, dict) else job

        best_agent = None
        best_score = -1

        # Collect suitability scores from all agents
        scores = []
        for agent in agents:
            try:
                score = await agent.evaluate_job_suitability(job_dict)
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
    def _assign_job_round_robin(
        job: Job,
        agents: List[Agent]
    ) -> Tuple[Agent, float]:
        """
        Simple round-robin assignment (static sequential counter).

        Args:
            job: Job to assign
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
    async def distribute_jobs(
        jobs: List[Job],
        agents: List[Agent],
        llm_handler: LLMHandler,
        strategy: str = "llm",
        parallel: bool = True
    ) -> Dict[str, Tuple[Agent, Job]]:
        """
        Distribute multiple job among available agents.

        Args:
            jobs: List of job to distribute
            agents: Available agents
            llm_handler: LLM handler
            strategy: Assignment strategy
            parallel: Whether to process assignments in parallel

        Returns:
            Dictionary mapping job IDs to (agent, job) tuples
        """
        assignments = {}

        if parallel:
            # Create job for parallel execution
            assignment_jobs = []
            for job in jobs:
                assignment_jobs.append(
                    AgentUtils.assign_job(job, agents, llm_handler, assignment_strategy=strategy)
                )

            # Execute all assignments in parallel
            results = await asyncio.gather(*assignment_jobs, return_exceptions=True)

            # Process results
            for i, result in enumerate(results):
                job = jobs[i]
                if isinstance(result, Exception):
                    logging.error(f"Error assigning job {job.id}: {result}")
                    continue

                agent, confidence = result
                assignments[job.id] = (agent, job)
        else:
            # Sequential assignment
            for job in jobs:
                try:
                    agent, confidence = await AgentUtils.assign_job(
                        job, agents, llm_handler, assignment_strategy=strategy
                    )
                    assignments[job.id] = (agent, job)
                except Exception as e:
                    logging.error(f"Error assigning job {job.id}: {e}")

        return assignments
