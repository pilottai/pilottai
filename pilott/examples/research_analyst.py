from pilott import Pilott
from pilott.core import LLMConfig
from pilott.tools import Tool

async def main():
    # Initialize PilottAI Serve
    pilott = Pilott(name="ResearchAnalyst")

    # Configure LLM
    llm_config = LLMConfig(
        model_name="gpt-4",
        provider="openai",
        api_key="your-api-key"
    )

    # Create research tools
    data_analyzer = Tool(
        name="data_analyzer",
        description="Analyze research data",
        function=lambda **kwargs: print(f"Analyzing data: {kwargs}"),
        parameters={
            "data_source": "str",
            "analysis_type": "str",
            "variables": "list"
        }
    )

    research_synthesizer = Tool(
        name="research_synthesizer",
        description="Synthesize research findings",
        function=lambda **kwargs: print(f"Synthesizing research: {kwargs}"),
        parameters={
            "sources": "list",
            "focus_areas": "list"
        }
    )

    # Create research analyst agent
    research_agent = await pilott.add_agent(
        role="research_analyst",
        goal="Conduct thorough research and provide insights",
        tools=[data_analyzer, research_synthesizer],
        llm_config=llm_config
    )

    # Example tasks
    tasks = [
        {
            "type": "analyze_data",
            "data_source": "market_survey_2024",
            "analysis_type": "trend_analysis",
            "variables": ["price", "demand"]
        },
        {
            "type": "synthesize_research",
            "sources": ["industry_report", "competitor_analysis"],
            "focus_areas": ["market_share", "growth_potential"]
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
