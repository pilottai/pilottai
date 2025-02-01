from typing import Dict
from pilott import Serve
from pilott.core import AgentConfig, AgentRole, LLMConfig, LogConfig
from example_agents import ManagerAgent, ExtractorAgent, EvaluatorAgent, GeneratorAgent
import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

def create_llm_config() -> LLMConfig:
    return LLMConfig(
        model_name="gpt-4",
        provider="openai",
        api_key=os.getenv("OPENAI_API_KEY", ""),
        temperature=0.7,
        max_tokens=2000
    )

async def setup_pipeline() -> Serve:
    llm_config = create_llm_config()

    # Create pilott instance
    pilott = Serve(name="PDF Processing System", verbose=True)

    # Create agent configurations
    agents_config = {
        "manager": AgentConfig(
            role="manager",
            role_type=AgentRole.ORCHESTRATOR,
            goal="Manage PDF processing workflow",
            description="Coordinates PDF extraction and validation",
            can_delegate=True,
        ),
        "extractor": AgentConfig(
            role="extractor",
            role_type=AgentRole.WORKER,
            goal="Extract content from PDFs",
            description="Processes PDF files and extracts content",
        ),
        "evaluator": AgentConfig(
            role="evaluator",
            role_type=AgentRole.WORKER,
            goal="Validate extraction results",
            description="Ensures extraction output is valid JSON",
        ),
        "generator": AgentConfig(
            role="Content Analyzer",
            role_type=AgentRole.WORKER,
            goal="Analyze PDF content and provide insights",
            description="Analyzes documents and provides detailed summaries",
            memory_enabled=True
        )
    }

    try:
        # Initialize agents
        manager = ManagerAgent(agents_config["manager"], llm_config)
        extractor = ExtractorAgent(agents_config["extractor"], llm_config)
        evaluator = EvaluatorAgent(agents_config["evaluator"], llm_config)
        generator = GeneratorAgent(agents_config["generator"], llm_config)

        # Set up agent hierarchy
        await manager.add_child_agent(extractor)
        await manager.add_child_agent(evaluator)
        await manager.add_child_agent(generator)

        # Add manager to pilott
        await pilott.add_agent(manager)

        # Start pilott
        await pilott.start()
        return pilott

    except Exception as e:
        raise RuntimeError(f"Failed to setup pipeline: {str(e)}") from e

async def process_pdf(pdf_path: str) -> Dict:
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    pilott = await setup_pipeline()
    try:
        return await pilott.execute_task({
            "type": "process_pdf",
            "file_path": pdf_path
        })
    finally:
        await pilott.stop()

async def main():
    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY not set")

    pdf_path = Path(__file__).parent / "sample_doc.pdf"
    try:
        result = await process_pdf(str(pdf_path))
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())