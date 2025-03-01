# Base Agent

The `BaseAgent` class is the foundation for all PilottAI agents. It provides the core functionality for task execution, tool management, and memory integration.

## Overview

The `BaseAgent` is responsible for:

- Executing tasks using LLMs
- Managing specialized tools
- Maintaining task context
- Tracking execution status
- Storing and retrieving memory

## Class Definition

```python
class BaseAgent:
    def __init__(
            self,
            config: AgentConfig,
            llm_config: Optional[LLMConfig] = None,
            tools: Optional[List[Tool]] = None,
            memory_enabled: bool = True
    ):
        # Core configuration
        self.config = config
        self.id = str(uuid.uuid4())

        # State management
        self.status = AgentStatus.IDLE
        self.current_task: Optional[Task] = None
        self._task_lock = asyncio.Lock()

        # Components
        self.tools = {tool.name: tool for tool in (tools or [])}
        self.memory = Memory() if memory_enabled else None
        self.llm = LLMHandler(llm_config) if llm_config else None

        # Setup logging
        self.logger = self._setup_logger()
```

## Configuration

The `BaseAgent` is configured using the `AgentConfig` class:

```python
from pilott.core import AgentConfig, AgentRole

config = AgentConfig(
    role="researcher",                  # Agent's role/type
    role_type=AgentRole.WORKER,         # Role classification
    goal="Find accurate information",    # Main objective
    description="Research assistant",    # Brief description
    backstory=None,                      # Optional background story
    tools=["web_search", "text_analyzer"], # Available tools
    required_capabilities=[],            # Required capabilities
    max_iterations=20,                   # Maximum execution iterations
    memory_enabled=True,                 # Enable memory
    verbose=False                        # Verbose logging
)
```

## Key Methods

### Task Execution

```python
async def execute_task(self, task: Union[Dict, Task]) -> Optional[TaskResult]:
    """Execute a task with proper handling and monitoring."""
    # Implementation details...
```

The task execution process involves:

1. Planning execution steps using LLM
2. Executing each step with proper error handling
3. Monitoring execution status and timeout
4. Recording execution in memory
5. Returning structured results

### Task Suitability Evaluation

```python
async def evaluate_task_suitability(self, task: Dict) -> float:
    """Evaluate how suitable this agent is for a task"""
    # Implementation details...
```

This method determines how well an agent can handle a specific task by:

- Checking required capabilities
- Matching task type with agent specializations
- Considering current agent load
- Analyzing task complexity

### Lifecycle Management

```python
async def start(self):
    """Start the agent"""
    # Implementation details...

async def stop(self):
    """Stop the agent"""
    # Implementation details...
```

These methods handle the agent's lifecycle, including:

- Initializing components
- Setting up connections
- Updating status
- Cleaning up resources

## Task Execution Pipeline

The `BaseAgent` follows a structured approach to task execution:

1. **Task Formatting**: Prepare task with context
2. **Execution Planning**: Generate a plan using LLM
3. **Step Execution**: Execute each step in the plan
4. **Tool Invocation**: Use tools as required
5. **Result Summarization**: Summarize and format results

```mermaid
sequenceDiagram
    participant A as Agent
    participant L as LLM
    participant T as Tools
    participant M as Memory
    
    A->>A: Format task
    A->>L: Request execution plan
    L-->>A: Return plan
    A->>M: Store plan
    
    loop For each step
        A->>T: Execute tool if needed
        T-->>A: Return tool result
        A->>L: Process step result
        L-->>A: Return processed result
        A->>M: Store step result
    end
    
    A->>L: Request summary
    L-->>A: Return summary
    A->>M: Store final result
```

## System Prompts

The `BaseAgent` uses system prompts to guide LLM behavior. The base system prompt follows this template:

```
You are an AI agent with:
Role: {role}
Goal: {goal}
Backstory: {backstory or 'No specific backstory.'}

Make decisions and take actions based on your role and goal.
```

## Error Handling

The `BaseAgent` implements robust error handling:

- Task timeouts
- LLM errors
- Tool execution failures
- Context validation

## Memory Integration

Agents maintain their own memory instance for:

- Task history tracking
- Context preservation
- Knowledge storage
- Pattern recognition

```python
# Store task in memory
await self.memory.store_task_start(
    task_id=task.id,
    description=task.description,
    agent_id=self.id
)

# Store result in memory
await self.memory.store_task_result(
    task_id=task.id,
    result=result,
    success=True,
    execution_time=execution_time,
    agent_id=self.id
)
```

## Extending BaseAgent

To create a specialized agent, extend the `BaseAgent` class:

```python
from pilott.core import BaseAgent, AgentConfig

class ResearchAgent(BaseAgent):
    def __init__(self, config: AgentConfig, **kwargs):
        super().__init__(config, **kwargs)
        self.specializations = ["research", "information_gathering"]
        
    async def evaluate_task_suitability(self, task: Dict) -> float:
        # Custom suitability logic
        base_score = await super().evaluate_task_suitability(task)
        if task.get("type") == "research":
            return min(1.0, base_score + 0.3)
        return base_score
```

## Examples

### Creating a Basic Agent

```python
from pilott.core import BaseAgent, AgentConfig, LLMConfig

# Configure LLM
llm_config = LLMConfig(
    model_name="gpt-4",
    provider="openai",
    api_key="your-api-key"
)

# Configure agent
config = AgentConfig(
    role="assistant",
    goal="Help with various tasks",
    description="General assistant agent"
)

# Create agent
agent = BaseAgent(config=config, llm_config=llm_config)
```

### Executing a Task

```python
# Create task
task = {
    "description": "Summarize the following text",
    "context": {
        "text": "PilottAI is a Python framework for building autonomous multi-agent systems..."
    }
}

# Execute task
result = await agent.execute_task(task)
print(f"Task result: {result.output}")
```

## API Reference

For a complete reference of all `BaseAgent` methods and attributes, see the [Agent API](../../api/agent.md) documentation.
