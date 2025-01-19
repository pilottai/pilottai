from pilott.core import BaseAgent, AgentConfig
import json
import asyncio
from datetime import datetime
from openai import AsyncOpenAI
import os
from typing import Dict, Any
from pathlib import Path
import pypdf


class ManagerAgent(BaseAgent):
    """Manager agent that orchestrates the PDF processing pipeline."""

    def evaluate_task_suitability(self, task: Dict[str, Any]) -> float:
        """Always returns 1.0 as this is the manager."""
        return 1.0

    async def _get_agent_result(self, agent: BaseAgent, task_id: str) -> Dict[str, Any]:
        """Wait for and get agent task result."""
        max_retries = 50  # 5 seconds max wait
        retry_count = 0

        while retry_count < max_retries:
            if task_id in agent.tasks and agent.tasks[task_id]["status"] != "queued":
                return agent.tasks[task_id].get("result", {
                    "status": "error",
                    "error": "No result available"
                })
            await asyncio.sleep(0.1)
            retry_count += 1

        return {
            "status": "error",
            "error": "Task timeout"
        }

    async def _default_task_handler(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Handle task delegation and oversight."""
        self.logger.info(f"Manager received task: {task['id']}")

        try:
            # Get required agents
            extractor = self._get_agent_by_type(ExtractorAgent)
            evaluator = self._get_agent_by_type(EvaluatorAgent)
            generator = self._get_agent_by_type(GeneratorAgent)

            # Step 1: Extract PDF content
            self.logger.debug(f"Starting extraction for file: {task.get('file_path')}")
            extraction_id = await extractor.add_task({
                "type": "extract",
                "file_path": task["file_path"]
            })
            extraction_result = await self._get_agent_result(extractor, extraction_id)

            # Early return if extraction failed
            if isinstance(extraction_result, str):
                extraction_result = json.loads(extraction_result)
            if extraction_result.get("status") == "error":
                self.logger.error(f"Extraction failed: {extraction_result.get('error')}")
                return {
                    "status": "error",
                    "phase": "extraction",
                    "error": extraction_result.get("error")
                }

            # Step 2: Validate extraction output
            evaluation_id = await evaluator.add_task({
                "type": "evaluate",
                "content": json.dumps(extraction_result) if isinstance(extraction_result, dict) else extraction_result
            })
            evaluation_result = await self._get_agent_result(evaluator, evaluation_id)

            # Step 3: Generate analysis if validation passed
            generation_result = {"status": "skipped"}
            if evaluation_result.get("is_valid_json"):
                generation_id = await generator.add_task({
                    "type": "generate",
                    "content": extraction_result
                })
                generation_result = await self._get_agent_result(generator, generation_id)

            return {
                "status": "success",
                "extraction": extraction_result,
                "evaluation": evaluation_result,
                "generation": generation_result
            }

        except Exception as e:
            self.logger.error(f"Pipeline execution failed: {str(e)}")
            return {
                "status": "error",
                "error": str(e)
            }

    def _get_agent_by_type(self, agent_type: type) -> BaseAgent:
        """Get an agent of specific type from child agents."""
        agent = next(
            (agent for agent in self.child_agents.values()
             if isinstance(agent, agent_type)),
            None
        )
        if not agent:
            raise ValueError(f"Required agent type {agent_type.__name__} not found")
        return agent


class ExtractorAgent(BaseAgent):
    """Agent responsible for PDF extraction."""

    def evaluate_task_suitability(self, task: Dict[str, Any]) -> float:
        """Check if task is PDF extraction."""
        return 1.0 if task.get("type") in ["extract", "process_pdf"] else 0.0

    async def _default_task_handler(self, task: Dict[str, Any]) -> str:
        """Handle PDF extraction."""
        try:
            file_path = task.get("file_path")
            if not file_path:
                raise ValueError("No file path provided in task")

            file_path = Path(file_path)
            if not file_path.exists():
                raise FileNotFoundError(f"PDF file not found: {file_path}")

            # Extract content using PyPDF
            with open(file_path, 'rb') as file:
                pdf_reader = pypdf.PdfReader(file)

                # Initialize the result dictionary
                result = {
                    "status": "success",
                    "filename": file_path.name,
                    "total_pages": len(pdf_reader.pages),
                    "content": {}
                }

                # Extract text from each page
                for i, page in enumerate(pdf_reader.pages):
                    text = page.extract_text()
                    if text.strip():  # Only include non-empty pages
                        result["content"][f"page_{i + 1}"] = text

                if not result["content"]:
                    raise ValueError("No text content found in PDF")

                self.logger.info(f"Successfully extracted content from {file_path.name}")
                return json.dumps(result)

        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"Extraction failed: {error_msg}")
            return json.dumps({
                "status": "error",
                "error": error_msg
            })


class EvaluatorAgent(BaseAgent):
    """Agent responsible for evaluating extraction results."""

    def evaluate_task_suitability(self, task: Dict[str, Any]) -> float:
        """Check if task is evaluation."""
        return 1.0 if task.get("type") == "evaluate" else 0.0

    async def _default_task_handler(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Validate JSON format of extraction result."""
        try:
            content = task["content"]
            timestamp = datetime.now().isoformat()  # Using utcnow() instead of now()

            # Check if content is valid JSON
            if isinstance(content, str):
                try:
                    json.loads(content)
                    is_valid = True
                except json.JSONDecodeError:
                    is_valid = False
            else:
                is_valid = False

            return {
                "status": "success",
                "is_valid_json": is_valid,
                "timestamp": timestamp
            }

        except Exception as e:
            self.logger.error(f"Evaluation failed: {str(e)}")
            return {
                "status": "error",
                "error": str(e)
            }


class GeneratorAgent(BaseAgent):
    """Agent responsible for generating responses using LLM."""

    def __init__(self, config: 'AgentConfig'):
        super().__init__(config)
        # Initialize OpenAI client
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
        self.client = AsyncOpenAI(api_key=api_key)

        # Construct system message from config
        self.system_message = self._create_system_message()

    def _create_system_message(self) -> str:
        """Create system message from agent configuration."""
        messages = [
            f"You are an AI assistant with the role: {self.config.role}",
            f"Your goal is to {self.config.goal}",
            f"Description: {self.config.description}"
        ]

        if self.config.backstory:
            messages.append(f"Background: {self.config.backstory}")

        return "\n".join(messages)

    def evaluate_task_suitability(self, task: Dict[str, Any]) -> float:
        """Check if task is for content generation."""
        return 1.0 if task.get("type") == "generate" else 0.0

    async def _default_task_handler(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Handle content generation using LLM."""
        try:
            content = task.get("content")
            if not content:
                raise ValueError("No content provided for generation")

            # Parse the JSON content if it's a string
            if isinstance(content, str):
                content = json.loads(content)

            # Prepare the text for LLM
            pdf_text = self._prepare_text(content)

            # Generate response using LLM
            response = await self._generate_response(pdf_text)

            return {
                "status": "success",
                "generated_content": response,
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            self.logger.error(f"Generation failed: {str(e)}")
            return {
                "status": "error",
                "error": str(e)
            }

    def _prepare_text(self, content: Dict[str, Any]) -> str:
        """Prepare PDF content for LLM processing."""
        if "content" not in content:
            raise ValueError("Invalid content format")

        # Get metadata
        metadata = {
            "filename": content.get("filename", "Unknown"),
            "total_pages": content.get("total_pages", 0)
        }

        # Combine all pages into a single text
        pages_text = []
        for page_num in sorted(content["content"].keys()):
            page_text = content["content"][page_num]
            pages_text.append(f"Page {page_num}: {page_text}")

        # Combine metadata and content
        full_text = [
            f"Document: {metadata['filename']}",
            f"Total Pages: {metadata['total_pages']}",
            "\nContent:",
            "\n\n".join(pages_text)
        ]

        return "\n".join(full_text)

    async def _generate_response(self, text: str) -> str:
        """Generate response using OpenAI's API."""
        try:
            response = await self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": self.system_message},
                    {"role": "user", "content": f"Please analyze this PDF content:\n\n{text}"}
                ],
                temperature=0.7,
                max_tokens=500
            )

            return response.choices[0].message.content

        except Exception as e:
            self.logger.error(f"OpenAI API error: {str(e)}")
            raise