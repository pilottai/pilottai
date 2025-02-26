# Basic Concepts

This guide introduces the core concepts of the PilottAI framework.

## Framework Architecture

PilottAI is designed around a modular, hierarchical architecture:

```mermaid
classDiagram
    class Serve {
        +agents: Dict[str, BaseAgent]
        +tasks: Dict[str, Task]
        +memory: Memory
        +add_agent()
        +create_task()
        +execute()
        +start()
        +stop()
    }

    class BaseAgent {
        +id: str
        +config: AgentConfig
        +status: AgentStatus
        +tools: Dict[str, Tool]
        +memory: Memory
        +llm: LLMHandler
        +execute_task()
        +evaluate_task_suitability()
        +start()
        +stop()
    }

    class Memory {
        +store_task_start()
        +store_task_result()
        +store_task_context()
        +get_task_history()
        +get_similar_tasks()
        +search()
    }

    class TaskRouter {
        +route_task()
        +_calculate_agent_scores()
        +_find_best_agent()
        +_analyze_agent_loads()
    }

    Serve *-- BaseAgent : manages
    Serve *-- Memory : uses
    BaseAgent *-- Memory : has
    Serve *-- TaskRouter : routes tasks
```

### Core Components

1. **Serve**: The main orchestrator that manages agents, routes tasks, and coordinates execution.

2. **Agents**: Autonomous entities that perform specific tasks using LLMs and tools.

3. **Tasks**: Units of work that are routed to appropriate agents for execution.

4. **Memory**: Storage system for context, task history, and knowledge.

5. **Tools**: Integrations and capabilities that agents can use to accomplish tasks.

6. **Orchestration**: Systems for scaling, load balancing, and fault tolerance.

## Agents

Agents are the primary actors in the PilottAI framework. Each agent:

- Has a specific role and goal
- Can use tools to interact with external systems
- Utilizes LLMs for decision-making and task execution
- Maintains its own memory and context

### Agent Types

PilottAI supports different agent roles:

- **Orchestrator**: Manages and delegates tasks to worker agents
- **Worker**: Executes specific tasks using specialized capabilities
- **Hybrid**: Combines orchestration and execution capabilities

### Agent Configuration

Agents are configured using the `AgentConfig` class:

```python
from pilott.core import AgentConfig, AgentRole

config = AgentConfig(
    role="document_processor",          # Agent's role/type
    role_type=AgentRole.WORKER,         # Role classification
    goal="Process documents efficiently", # Main objective
    description="Document processing worker", # Brief description
    backstory=None,                      # Optional background story
    knowledge_sources=[],                # Available knowledge sources
    tools=["text_extractor"],            # Available tools
    required_capabilities=[],            # Required capabilities
    max_iterations=20,                   # Maximum execution iterations
    max_rpm=None,                        # Rate limits
    memory_enabled=True,                 # Enable memory
    verbose=False                        # Verbose logging
)
```

## Tasks

Tasks represent units of work that agents perform. Each task:

- Has a description and context
- May be assigned to a specific agent or automatically routed
- Has a priority level
- Tracks execution status and results

### Task Lifecycle

```mermaid
stateDiagram-v2
    [*] --> PENDING: Created
    PENDING --> IN_PROGRESS: Started
    IN_PROGRESS --> COMPLETED: Success
    IN_PROGRESS --> FAILED: Error/Timeout
    COMPLETED --> [*]
    FAILED --> PENDING: Retry
    FAILED --> [*]: Max retries
```

### Task Creation

```python
from pilott.core import Task, TaskPriority

task = Task(
    description="Extract key information from document",
    priority=TaskPriority.HIGH,
    context={"file_path": "document.pdf"}
)
```

## Memory System

PilottAI includes a sophisticated memory system that:

- Stores task execution history
- Maintains agent context
- Enables semantic search and retrieval
- Supports knowledge persistence

### Memory Components

1. **Task Memory**: Records task execution details
2. **Semantic Memory**: Stores knowledge and context
3. **Enhanced Memory**: Advanced memory with pattern recognition

### Using Memory

```python
# Store information in semantic memory
await agent.memory.store_semantic(
    text="Important information about topic X",
    metadata={"topic": "X", "importance": "high"},
    tags={"research", "topic_x"}
)

# Search memory
results = await agent.memory.search(
    query="topic X",
    tags={"research"}
)
```

## LLM Integration

PilottAI uses Large Language Models for agent intelligence. Key concepts:

1. **LLM Configuration**: Settings for model, provider, and parameters
2. **LLM Handler**: Manages LLM interactions with proper error handling
3. **Function Calling**: Structured LLM output for tool use

### LLM Configuration

```python
from pilott.core import LLMConfig

llm_config = LLMConfig(
    model_name="gpt-4",
    provider="openai",
    api_key="your-api-key",
    temperature=0.7,
    max_tokens=2000
)
```

## Tools

Tools extend agent capabilities by providing:

- External system integrations
- Specialized functionality
- Task-specific utilities

### Tool Creation

```python
from pilott.tools import Tool

email_tool = Tool(
    name="email_sender",
    description="Send emails to recipients",
    function=lambda **kwargs: send_email(**kwargs),
    parameters={
        "to": "str",
        "subject": "str",
        "body": "str"
    }
)
```

## Orchestration

PilottAI includes advanced orchestration features:

### Dynamic Scaling

Automatically adjusts the number of agents based on system load:

```python
await pilott.enable_dynamic_scaling(
    config={
        "min_agents": 2,
        "max_agents": 10,
        "scale_up_threshold": 0.8,
        "scale_down_threshold": 0.3
    }
)
```

### Load Balancing

Distributes tasks across agents to optimize performance:

```python
await pilott.enable_load_balancing(
    config={
        "check_interval": 30,
        "overload_threshold": 0.7
    }
)
```

### Fault Tolerance

Handles agent failures and ensures system reliability:

```python
await pilott.enable_fault_tolerance(
    config={
        "health_check_interval": 30,
        "max_recovery_attempts": 3
    }
)
```

## Next Steps

Now that you understand the basic concepts of PilottAI, you can:

- Explore specialized [Agents](../core/agents/base-agent.md)
- Learn about [Memory Systems](../core/memory/overview.md)
- Dive into [Orchestration](../orchestration/overview.md) features
- See [Examples](../examples/basic.md) of PilottAI in action
