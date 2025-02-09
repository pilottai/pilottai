# Marketing Expert Agent Example

Simple example showing how to set up a marketing expert agent with PilottAI framework.

## Setup

```bash
pip install pilott
```

## Example Usage

```python
from pilott import Serve
from pilott.core import AgentConfig, LLMConfig

# Initialize
pilott = Serve(name="MarketingExpert")

# Create agent
marketing_agent = await pilott.add_agent(
    role="marketing_expert",
    goal="Create and optimize marketing campaigns",
    tools=["content_creator", "campaign_analyzer"]
)

# Create content
task = {
    "type": "create_content",
    "content_type": "social_post",
    "target_audience": "tech professionals"
}

result = await pilott.execute([task])
```

## Tools

- content_creator: Create marketing content
- campaign_analyzer: Analyze campaign performance

## Features

- Content creation
- Campaign analysis
- Performance tracking
- Audience targeting

## Code

Ready to use code [marketing_expert.py](../../pilott/agents/marketing_expert.py)