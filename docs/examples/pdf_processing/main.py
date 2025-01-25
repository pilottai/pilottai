from typing import Dict
from pilott import Serve
from pilott.core import AgentConfig, AgentRole, LogConfig
from agents import ManagerAgent, ExtractorAgent, EvaluatorAgent, GeneratorAgent
import asyncio
import json
import os
from pathlib import Path

def create_log_config(enable_file_logging: bool = False) -> LogConfig:
    """Create logging configuration"""
    return LogConfig(
        verbose=True,
        log_to_file=enable_file_logging,
        log_dir="logs",
        log_format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        log_level="DEBUG" if enable_file_logging else "INFO"
    )

async def setup_pipeline(enable_file_logging: bool = False) -> Serve:
    """Set up the PDF processing pipeline."""
    # Create logging configuration
    log_config = create_log_config(enable_file_logging)

    # Create Pilott instance
    pilott = Serve(
        name="PDF Processing System",
        verbose=True
    )

    # Create agent configurations
    manager_config = AgentConfig(
        role="manager",
        role_type=AgentRole.ORCHESTRATOR,
        goal="Manage PDF processing workflow",
        description="Coordinates PDF extraction and validation",
        can_delegate=True,
        # logging=log_config
    )

    extractor_config = AgentConfig(
        role="extractor",
        role_type=AgentRole.WORKER,
        goal="Extract content from PDFs",
        description="Processes PDF files and extracts content",
        logging=log_config
    )

    evaluator_config = AgentConfig(
        role="evaluator",
        role_type=AgentRole.WORKER,
        goal="Validate extraction results",
        description="Ensures extraction output is valid JSON",
        logging=log_config
    )

    generator_config = AgentConfig(
        role="Content Analyzer",
        role_type=AgentRole.WORKER,
        goal="analyze PDF content and provide comprehensive insights and summaries",
        description="""I am a specialized content analyzer focused on extracting key information from PDFs.
        I provide detailed summaries, identify main themes, and highlight important points.""",
        backstory="""I have been trained to analyze various types of documents and can adapt my analysis 
        style based on the content type, whether it's academic, business, or technical material."""
    )

    # Create agents
    manager = ManagerAgent(manager_config)
    extractor = ExtractorAgent(extractor_config)
    evaluator = EvaluatorAgent(evaluator_config)
    generator = GeneratorAgent(generator_config)

    # Add child agents to manager
    await manager.add_child_agent(extractor)
    await manager.add_child_agent(evaluator)
    await manager.add_child_agent(generator)

    # Add manager to pilott
    pilott.agents.append(manager)

    # Start pilott
    await pilott.start()

    return pilott

async def process_pdf_file(pdf_path: str, enable_file_logging: bool = False) -> Dict:
    """Process a PDF file through the pipeline."""
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    pilott = await setup_pipeline(enable_file_logging)
    try:
        result = await pilott.execute_task({
            "id": "task_1",
            "type": "process_pdf",
            "file_path": pdf_path
        })
        return result
    finally:
        await pilott.stop()

async def main():
    # Check for OpenAI API key
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable not set")
        return

    # Check if file logging is requested
    enable_file_logging = os.getenv("ENABLE_LOG_FILES", "").lower() == "true"

    # Process PDF file
    current_dir = Path(__file__).parent
    sample_pdf = current_dir / "sample_doc.pdf"

    try:
        result = await process_pdf_file(str(sample_pdf), enable_file_logging)
        print(f"Processing result: {json.dumps(result, indent=2)}")
    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("Please make sure to place your PDF file in the samples directory")
    except Exception as e:
        print(f"Processing error: {e}")

if __name__ == "__main__":
    asyncio.run(main())