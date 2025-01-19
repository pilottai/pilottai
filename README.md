# Pilott Framework

<div align="center">
    <img src="docs/assets/logo.svg" alt="Pilott Logo" width="400"/>
    <p><em>A Powerful Multi-Agent Framework for Intelligent Task Processing</em></p>
</div>

[![PyPI version](https://badge.fury.io/py/pilott.svg)](https://badge.fury.io/py/pilott)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

## 🚀 Overview

Pilott is a modern Python framework for building hierarchical multi-agent systems. It provides a robust foundation for creating autonomous agents that can work together to process complex tasks, with built-in support for orchestration, load balancing, and fault tolerance.

## ✨ Features

- **🤖 Hierarchical Agent System**
  - Manager agents for task orchestration
  - Worker agents for specialized tasks
  - Flexible agent communication patterns

- **🔄 Task Processing**
  - Asynchronous task execution
  - Priority-based task routing
  - Advanced queue management

- **⚡ Core Systems**
  - Dynamic scaling
  - Load balancing
  - Fault tolerance
  - Memory management

- **🛠️ Built-in Tools**
  - PDF processing capabilities
  - LLM integration (OpenAI)
  - Extensible tool system

## 🏗️ Architecture

```
┌─────────────────┐
│  Pilott System   │
└────────┬────────┘
         │
    ┌────┴────┐
    │ Manager │
    └────┬────┘
         │
    ┌────┴────┐
    │ Agents  │
    └────┬────┘
         │
  ┌──────┴──────┐
  │    Tools    │
  └─────────────┘
```

## 🚀 Quick Start

### Installation

```bash
pip install pilott
```

### Basic Usage

```python
from pilott import Serve
from pilott.core import AgentConfig, AgentRole

# Create agent configuration
config = AgentConfig(
  role="processor",
  role_type=AgentRole.WORKER,
  goal="Process tasks efficiently",
  description="Sample worker agent"
)

# Initialize Pilott system
pilott = Serve(
  name="MyPilottSystem",
  verbose=True
)


# Add agents and start processing
async def main():
  await pilott.start()
  result = await pilott.execute_task({"type": "sample_task"})
  await pilott.stop()
```

## 📚 Examples

Check out our [examples directory](docs/examples) for complete working examples, including:
- PDF Processing Pipeline
- Multi-Agent Task Delegation
- Custom Tool Integration

## 📖 Documentation

Visit our [documentation](docs/README.md) for:
- Detailed API reference
- Architecture overview
- Best practices
- Advanced usage examples

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details on:
- Code style
- Development setup
- Testing requirements
- Pull request process

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built with modern Python async/await patterns
- Inspired by multi-agent architectures
- Powered by Pydantic for robust data validation

<div align="center">
    <sub>Built with ❤️ by the Pilott team</sub>
</div>