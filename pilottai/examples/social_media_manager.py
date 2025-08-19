from pilottai import Pilott
from pilottai.core.base_config import LLMConfig
from pilottai.tools import Tool

async def main():
    # Initialize PilottAI Serve
    pilott = Pilott(name="SocialMediaManager")

    # Configure LLM
    llm_config = LLMConfig(
        model_name="gpt-4",
        provider="openai",
        api_key="your-api-key"
    )

    # Create social media tools
    content_scheduler = Tool(
        name="content_scheduler",
        description="Schedule social media content",
        function=lambda **kwargs: print(f"Scheduling content: {kwargs}"),
        parameters={
            "platform": "str",
            "content": "str",
            "schedule_time": "str",
            "media_attachments": "list"
        }
    )

    engagement_analyzer = Tool(
        name="engagement_analyzer",
        description="Analyze social media engagement",
        function=lambda **kwargs: print(f"Analyzing engagement: {kwargs}"),
        parameters={
            "post_id": "str",
            "metrics": "list",
            "timeframe": "str"
        }
    )

    # Create social media agent
    await pilott.add_agent(
        title="social_media_manager",
        goal="Manage social media presence and engagement",
        tools=[content_scheduler, engagement_analyzer],
        llm_config=llm_config
    )

    # Execute job
    results = await pilott.serve()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
