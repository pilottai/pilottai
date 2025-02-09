# PilottAI Agent Examples

This directory contains example implementations showing how to create and use different types of agents with the PilottAI framework.

## Overview

The examples demonstrate how to:
- Set up multiple specialized agents
- Create and configure tools
- Execute tasks across different agents
- Use the PilottAI Serve orchestrator

## Installation

1. Install PilottAI:
```bash
pip install pilott
```

2. Set up your OpenAI API key:
```bash
export OPENAI_API_KEY="your-api-key"
```

## Included Examples

### Agents
- **Customer Service Agent**: Handles customer inquiries and support requests
- **Document Processor**: Processes and analyzes documents
- **Research Analyst**: Conducts research and provides insights

### Tools
- **Email Sender**: Tool for sending emails to customers
- **Document Processor**: Tool for document analysis and processing

## Usage

Run the examples:

```python
from examples.agents import main

# Run the example
import asyncio
asyncio.run(main())
```

## Example Output

```
Task: Handle refund request
Result: Customer refund request processed successfully

Task: Analyze quarterly report
Result: Document analysis complete: 3 key insights found

Task: Research competitor pricing
Result: Market research analysis completed
```

## Creating Your Own Agents

1. Configure the agent:
```python
agent_config = AgentConfig(
    role="your_agent_role",
    goal="your_agent_goal",
    tools=["tool1", "tool2"]
)
```

2. Add to PilottAI:
```python
agent = await pilott.add_agent(
    role=agent_config.role,
    goal=agent_config.goal,
    tools=agent_config.tools,
    llm_config=llm_config
)
```

## Best Practices

1. **Agent Design**
   - Give each agent a clear, focused role
   - Provide specific goals and tools
   - Use appropriate LLM configurations

2. **Tool Management**
   - Create reusable tools
   - Define clear tool interfaces
   - Handle tool errors gracefully

3. **Task Execution**
   - Group related tasks
   - Set appropriate priorities
   - Monitor execution results

## Configuration Options

### LLM Configuration
```python
llm_config = LLMConfig(
    model_name="gpt-4",  # or other models
    provider="openai",   # or other providers
    temperature=0.7     # adjust based on needs
)
```

### Tool Configuration
```python
tool = Tool(
    name="tool_name",
    description="tool_description",
    function=your_function,
    parameters={
        "param1": "type1",
        "param2": "type2"
    }
)
```

## Error Handling

The examples include basic error handling. In production, you should:
- Add comprehensive error handling
- Implement retries for failed tasks
- Log errors appropriately
- Handle API rate limits

## Contributing

Feel free to:
- Add new agent examples
- Create additional tools
- Improve documentation
- Report issues
- Submit pull requests

## Code

Ready to use code [customer_service.py](../../pilott/agents/customer_service.py) 