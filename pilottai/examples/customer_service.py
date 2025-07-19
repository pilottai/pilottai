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
    customer_service = await pilott.add_agent(
        title="customer_service",
        goal="Handle customer inquiries professionally",
        tools=[email_tool],
        llm_config=llm_config
    )

    # Create document processing agent
    doc_processor = await pilott.add_agent(
        title="document_processor",
        goal="Process and analyze documents efficiently",
        tools=[document_tool],
        llm_config=llm_config
    )

    # Create research analyst agent
    research_analyst = await pilott.add_agent(
        title="research_analyst",
        goal="Analyze data and provide insights",
        tools=[document_tool],
        llm_config=llm_config
    )

    # Example job
    jobs = [
        {
            "type": "customer_inquiry",
            "description": "Handle refund request",
            "agent": customer_service
        },
        {
            "type": "document_analysis",
            "description": "Analyze quarterly report",
            "agent": doc_processor
        },
        {
            "type": "market_research",
            "description": "Research competitor pricing",
            "agent": research_analyst
        }
    ]

    # Execute job
    results = await pilott.serve(jobs)
    for job, result in zip(jobs, results):
        print(f"Job: {job['description']}")
        print(f"Result: {result.output}\n")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
