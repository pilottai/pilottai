from pilottai import Pilott
from pilottai.core.base_config import LLMConfig
from pilottai.tools import Tool

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
    await pilott.add_agent(
        title="research_analyst",
        goal="Conduct thorough research and provide insights",
        tools=[data_analyzer, research_synthesizer],
        llm_config=llm_config
    )


    # Execute job
    await pilott.serve()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
