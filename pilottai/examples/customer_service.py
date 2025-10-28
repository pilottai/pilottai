from pilottai.core.base_config import LLMConfig
from pilottai.pilott import Pilott
from pilottai.tools.tool import Tool


async def main():
    # Initialize PilottAI Serve
    pilott = Pilott(name="MultiAgentSystem")

    # Configure LLM
    llm_config = LLMConfig(
        model_name="gpt-4",
        provider="openai",
        api_key="your-api-key"
    )

    # Create tools
    email_tool = Tool(
        name="email_sender",
        description="Send emails to customers",
        function=lambda **kwargs: print(f"Sending email: {kwargs}"),
        parameters={"to": "str", "subject": "str", "body": "str"}
    )

    document_tool = Tool(
        name="document_processor",
        description="Process and analyze documents",
        function=lambda **kwargs: print(f"Processing document: {kwargs}"),
        parameters={"content": "str", "type": "str"}
    )

    # Create customer service agent
    await pilott.add_agent(
        title="customer_service",
        goal="Handle customer inquiries professionally",
        description = "Handle refund request",
        tools=[email_tool],
        llm_config=llm_config
    )

    # Create document processing agent
    await pilott.add_agent(
        title="document_processor",
        goal="Process and analyze documents efficiently",
        description= "Analyze quarterly report",
        tools=[document_tool],
        llm_config=llm_config
    )

    # Create research analyst agent
    await pilott.add_agent(
        title="research_analyst",
        goal="Analyze data and provide insights",
        description= "Research competitor pricing",
        tools=[document_tool],
        llm_config=llm_config
    )


    # Execute job
    results = await pilott.serve()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
