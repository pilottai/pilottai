# PilottAI Framework

<div align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/anuj0456/pilottai/main/interface/assets/logo.png">
    <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/anuj0456/pilottai/main/interface/assets/logo.png">
    <img alt="PilottAI Framework Logo" src="https://raw.githubusercontent.com/anuj0456/pilottai/main/interface/assets/logo.png" width="400">
  </picture>
  <h3>Build Intelligent Multi-Agent Systems with Python</h3>
  <p><em>Scale your AI applications with orchestrated autonomous agents</em></p>
</div>

<div align="center">
  
[![PyPI version](https://badge.fury.io/py/pilott.svg)](https://badge.fury.io/py/pilott)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Documentation Status](https://readthedocs.org/projects/pilottai/badge/?version=latest)](https://pilottai.readthedocs.io)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

</div>

## Overview

PilottAI is a Python framework for building autonomous multi-agent systems with advanced orchestration capabilities. It provides enterprise-ready features for building scalable AI applications.

### Key Features

- 🤖 **Hierarchical Agent System**
  - Manager and worker agent hierarchies
  - Intelligent task routing
  - Context-aware processing

- 🚀 **Production Ready**
  - Asynchronous processing
  - Dynamic scaling
  - Load balancing
  - Fault tolerance
  - Comprehensive logging

- 🧠 **Advanced Memory**
  - Semantic storage
  - Task history tracking
  - Context preservation
  - Knowledge retrieval

- 🔌 **Integrations**
  - Multiple LLM providers (OpenAI, Anthropic, Google)
  - Document processing
  - WebSocket support
  - Custom tool integration

## Installation

```bash
pip install pilott
```

## Quick Start

```python
from pilott import Serve
from pilott.core import AgentConfig, AgentRole, LLMConfig

# Configure LLM
llm_config = LLMConfig(
    model_name="gpt-4",
    provider="openai",
    api_key="your-api-key"
)

# Setup agent configuration
config = AgentConfig(
    role="processor",
    role_type=AgentRole.WORKER,
    goal="Process documents efficiently",
    description="Document processing worker",
    max_queue_size=100
)

async def main():
    # Initialize system
    pilott = Serve(name="DocumentProcessor")
    
    try:
        # Start system
        await pilott.start()
        
        # Add agent
        agent = await pilott.add_agent(
            agent_type="processor",
            config=config,
            llm_config=llm_config
        )
        
        # Process document
        result = await pilott.execute_task({
            "type": "process_document",
            "file_path": "document.pdf"
        })
        
        print(f"Processing result: {result}")
        
    finally:
        await pilott.stop()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

## Documentation

Visit our [documentation](https://pilottai.readthedocs.io) for:
- Detailed guides
- API reference
- Examples
- Best practices

## Example Use Cases

- 📄 **Document Processing**
  ```python
  # Process PDF documents
  result = await pilott.execute_task({
      "type": "process_pdf",
      "file_path": "document.pdf"
  })
  ```

- 🤖 **AI Agents**
  ```python
  # Create specialized agents
  researcher = await pilott.add_agent(
      agent_type="researcher",
      config=researcher_config
  )
  ```

- 🔄 **Task Orchestration**
  ```python
  # Orchestrate complex workflows
  task_result = await manager_agent.execute_task({
      "type": "complex_workflow",
      "steps": ["extract", "analyze", "summarize"]
  })
  ```

## Advanced Features

### Memory Management
```python
# Store and retrieve context
await agent.enhanced_memory.store_semantic(
    text="Important information",
    metadata={"type": "research"}
)
```

### Load Balancing
```python
# Configure load balancing
config = LoadBalancerConfig(
    check_interval=30,
    overload_threshold=0.8
)
```

### Fault Tolerance
```python
# Configure fault tolerance
config = FaultToleranceConfig(
    recovery_attempts=3,
    heartbeat_timeout=60
)
```

## Project Structure

```
pilott/
├── core/            # Core framework components
├── agents/          # Agent implementations
├── memory/          # Memory management
├── orchestration/   # System orchestration
├── tools/           # Tool integrations
└── utils/           # Utility functions
```

## Contributing

We welcome contributions! See our [Contributing Guide](CONTRIBUTING.md) for details on:
- Development setup
- Coding standards
- Pull request process

## Support

- 📚 [Documentation](https://pilottai.readthedocs.io)
- 💬 [Discord](https://discord.gg/pilottai)
- 📝 [GitHub Issues](https://github.com/pilottai/pilott/issues)
- 📧 [Email Support](mailto:support@pilottai.com)

## License

PilottAI is MIT licensed. See [LICENSE](LICENSE) for details.

---

<div align="center">
  <sub>Built with ❤️ by the PilottAI Team</sub>
</div>