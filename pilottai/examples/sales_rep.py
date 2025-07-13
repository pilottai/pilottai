from pilottai import Pilott
from pilottai.core.base_config import LLMConfig
from pilottai.tools import Tool

async def main():
    # Initialize PilottAI Serve
    pilott = Pilott(name="SalesRepresentative")

    # Configure LLM
    llm_config = LLMConfig(
        model_name="gpt-4",
        provider="openai",
        api_key="your-api-key"
    )

    # Create sales tools
    lead_manager = Tool(
        name="lead_manager",
        description="Manage sales leads",
        function=lambda **kwargs: print(f"Managing lead: {kwargs}"),
        parameters={
            "lead_id": "str",
            "action": "str",
            "details": "dict"
        }
    )

    proposal_generator = Tool(
        name="proposal_generator",
        description="Generate sales proposals",
        function=lambda **kwargs: print(f"Generating proposal: {kwargs}"),
        parameters={
            "client_info": "dict",
            "product_line": "str",
            "customizations": "list"
        }
    )

    # Create sales agent
    sales_agent = await pilott.add_agent(
        role="sales_representative",
        goal="Manage leads and close sales effectively",
        tools=[lead_manager, proposal_generator],
        llm_config=llm_config
    )

    # Example task
    tasks = [
        {
            "type": "manage_lead",
            "lead_id": "LEAD123",
            "action": "qualify",
            "details": {
                "company": "TechCorp",
                "budget": "100k",
                "timeline": "Q2"
            }
        },
        {
            "type": "generate_proposal",
            "client_info": {
                "name": "TechCorp",
                "requirements": ["cloud storage", "analytics"]
            },
            "product_line": "enterprise",
            "customizations": ["custom dashboard", "api access"]
        }
    ]

    # Execute task
    results = await pilott.execute(tasks)
    for task, result in zip(tasks, results):
        print(f"Task type: {task['type']}")
        print(f"Result: {result.output}\n")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
