<h1 align="center" style="margin-bottom: -100px;">PilottAI</h1>

<div align="center" style="margin-top: 20px;">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/pygig/pilottai/main/docs/assets/logo.svg">
    <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/pygig/pilottai/main/docs/assets/logo.svg">
    <img alt="PilottAI Framework Logo" src="https://raw.githubusercontent.com/pygig/pilottai/main/docs/assets/logo.svg" width="500">
  </picture>
  <h3>Build Intelligent Multi-Agent Systems with Python</h3>
  <p><em>Scale your AI applications with orchestrated autonomous agents</em></p>


[![PyPI version](https://badge.fury.io/py/pilottai.svg)](https://badge.fury.io/py/pilottai)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Documentation Status](https://github.com/pilottai/pilottai/actions/workflows/deploy-docs.yml/badge.svg?branch=main)](https://docs.pilottai.com)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Commit Activity](https://img.shields.io/github/commit-activity/m/pygig/pilottai?style=flat-square)](https://github.com/pygig/pilottai)

⭐ Star us | 🧠 Agentic AI | 🧰 Multi-Agent Framework | ⚡ Build Anything with LLMs

</div>



## Overview

PilottAI is a Python framework for building autonomous multi-agent systems with advanced orchestration capabilities. It provides enterprise-ready features for building scalable AI applications.

### Key Features

- 🤖 **Hierarchical Agent System**
  - Manager and worker agent hierarchies
  - Intelligent job routing
  - Context-aware processing
  - Specialized agent implementations

- 🚀 **Production Ready**
  - Asynchronous processing
  - Dynamic scaling
  - Load balancing
  - Fault tolerance
  - Comprehensive logging

- 🧠 **Advanced Memory**
  - Semantic storage
  - Job history tracking
  - Context preservation
  - Knowledge retrieval

- 🔌 **Integrations**
  - Multiple LLM providers (OpenAI, Anthropic, Google)
  - Document processing
  - WebSocket support
  - Custom tool integration

## Installation

```bash
pip install pilottai
```

## Quick Start

```python
from pilottai import Pilott
from pilottai.tools import Tool
from pilottai.agent import Agent
from duckduckgo_search import DDGS
from pilottai.core import AgentConfig, AgentType, LLMConfig

# Configure LLM
llm_config = LLMConfig(
  model_name="gpt-4",
  provider="openai",
  api_key="your-api-key"
)

def duckduckgo_search(query, max_results=5):
    """Perform a DuckDuckGo search and return top results."""
    with DDGS() as ddgs:
        results = ddgs.text(query, max_results=max_results)
        return [{"title": r["title"], "link": r["href"], "snippet": r["body"]} for r in results]

search_tool = Tool(
                name="duckduckgo_search",
                description="Search DuckDuckGo for relevant information on any topic",
                function=duckduckgo_search,
                parameters={
                    "query": "str - The search query",
                    "num_results": "int - Number of results to return (max 10)"
                }
            )

query = "Type your question here"

search_agent = Agent(
                title="search_specialist",
                goal="Find the most relevant and credible sources for any given query",
                description="An expert at formulating search queries and identifying high-quality, relevant sources",
                jobs=f"Search for information about: '{query}' using DuckDuckGo and rank the results by relevance and credibility. Return the top 5 most relevant sources.",
                tools=[search_tool],
                llm_config=llm_config
              )


synthesis_results = await Pilott(agents=[search_agent], name="Search Bot", llm_config=llm_config).serve()

```

## Specialized Agents

PilottAI includes ready-to-use specialized agents:

- 🎫 [Customer Service Agent](pilottai/examples/customer_service.py): Ticket and support management
- 📄 [Document Processing Agent](pilottai/examples/document_processing.py): Document analysis and extraction
- 📧 [Email Agent](pilottai/examples/email_service.py): Email handling and template management
- 🧠 [Learning Agent](pilottai/examples/teacher.py): Knowledge acquisition and pattern recognition
- 📢 [Marketing Expert Agent](pilottai/examples/marketing_expert.py): Campaign management and content creation
- 📊 [Research Analyst Agent](pilottai/examples/research_analyst.py): Data analysis and research synthesis
- 💼 [Sales Representative Agent](pilottai/examples/sales_rep.py): Lead management and proposals
- 🌐 [Social Media Agent](pilottai/examples/social_media_manager.py): Content scheduling and engagement
- 🔍 [Web Search Agent](pilottai/examples/web_search.py): Search operations and analysis

## 📚 Documentation

👉 **[Read the full documentation here](https://docs.pilottai.com)**

The documentation includes:
- Detailed guides
- API reference
- Best practices

## Project Structure

```
pilott/
├── core/            # Core framework components
├── agents/          # Agent implementations
├── memory/          # Memory management
├── tools/           # Tool integrations
└── utils/           # Utility functions
```

## Contributing

We welcome contributions! See our [Contributing Guide](.github/CONTRIBUTING.md) for details on:
- Development setup
- Coding standards
- Pull request process

## Support

- 📚 [Documentation](https://docs.pilottai.com)
- 💬 [Discord](https://discord.gg/pilottai) <!-- TODO: Correct link -->
- 📝 [GitHub Issues](https://github.com/pilottai/pilott/issues)
- 📧 [Email Support](mailto:support@pilottai.com)

## License

PilottAI is MIT licensed. See [LICENSE](LICENSE) for details.

---

<div align="center">
  <sub>Built with ❤️ by the PilottAI Team</sub>
</div>
