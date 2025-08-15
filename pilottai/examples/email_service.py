from pilottai import Pilott
from pilottai.core.base_config import LLMConfig
from pilottai.tools import Tool

async def main():
    # Initialize PilottAI Serve
    pilott = Pilott(name="EmailAgent")

    # Configure LLM
    llm_config = LLMConfig(
        model_name="gpt-4",
        provider="openai",
        api_key="your-api-key"
    )

    # Create email tools
    email_sender = Tool(
        name="email_sender",
        description="Send emails",
        function=lambda **kwargs: print(f"Sending email: {kwargs}"),
        parameters={
            "to": "str",
            "subject": "str",
            "body": "str",
            "attachments": "list"
        }
    )

    email_analyzer = Tool(
        name="email_analyzer",
        description="Analyze email content and intent",
        function=lambda **kwargs: print(f"Analyzing email: {kwargs}"),
        parameters={
            "content": "str",
            "analyze_sentiment": "bool"
        }
    )

    template_manager = Tool(
        name="template_manager",
        description="Manage email templates",
        function=lambda **kwargs: print(f"Using template: {kwargs}"),
        parameters={
            "template_name": "str",
            "variables": "dict"
        }
    )

    # Create email agent
    #TODO
    await pilott.add_agent(
        title="email_manager",
        goal="Handle email communications efficiently",
        tools=[email_sender, email_analyzer, template_manager],
        llm_config=llm_config
    )

    # Execute job
    results = await pilott.serve()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
