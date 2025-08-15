from pilottai import Pilott
from pilottai.core.base_config import LLMConfig
from pilottai.tools import Tool

async def main():
    # Initialize PilottAI Serve
    pilott = Pilott(name="LearningAgent")

    # Configure LLM
    llm_config = LLMConfig(
        model_name="gpt-4",
        provider="openai",
        api_key="your-api-key"
    )

    # Create learning tools
    knowledge_base = Tool(
        name="knowledge_base",
        description="Store and retrieve knowledge",
        function=lambda **kwargs: print(f"Knowledge operation: {kwargs}"),
        parameters={
            "operation": "str",
            "content": "str",
            "tags": "list"
        }
    )

    pattern_recognizer = Tool(
        name="pattern_recognizer",
        description="Identify patterns in data",
        function=lambda **kwargs: print(f"Pattern analysis: {kwargs}"),
        parameters={
            "data": "str",
            "pattern_type": "str"
        }
    )

    # Create learning agent
    await pilott.add_agent(
        title="learner",
        goal="Acquire and organize knowledge effectively",
        tools=[knowledge_base, pattern_recognizer],
        llm_config=llm_config
    )

    results = await pilott.serve()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
