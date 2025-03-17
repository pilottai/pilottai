from pilott import Pilott
from pilott.core import LLMConfig
from pilott.tools import Tool

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
        role="learner",
        goal="Acquire and organize knowledge effectively",
        tools=[knowledge_base, pattern_recognizer],
        llm_config=llm_config
    )

    # Example tasks
    tasks = [
        {
            "type": "learn_topic",
            "content": "Introduction to Machine Learning",
            "store_results": True
        },
        {
            "type": "analyze_patterns",
            "data": "Historical market trends",
            "pattern_type": "trends"
        }
    ]

    # Execute tasks
    results = await pilott.execute(tasks)
    for task, result in zip(tasks, results):
        print(f"Task type: {task['type']}")
        print(f"Result: {result.output}\n")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
