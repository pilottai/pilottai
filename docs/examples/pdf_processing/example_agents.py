from typing import Dict, Any, Optional, List
from datetime import datetime
import json
from pathlib import Path
import pypdf
import asyncio

from pilott.core import BaseAgent, AgentConfig, LLMConfig
from pilott.engine.llm import LLMHandler
from pilott.tools import Tool


class ManagerAgent(BaseAgent):
    def __init__(self, agent_config: AgentConfig, llm_config: LLMConfig):
        super().__init__(agent_config, llm_config)
        llm_dict = {
            "model_name": llm_config.model_name,
            "provider": llm_config.provider,
            "api_key": llm_config.api_key,
            "temperature": llm_config.temperature,
            "max_tokens": llm_config.max_tokens
        }
        self.llm_handler = LLMHandler(llm_dict)


    def evaluate_task_suitability(self, task: Dict[str, Any]) -> float:
        return 1.0

    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute task with proper type handling"""
        self.metrics['total_tasks'] += 1

        try:
            # Get required agents
            extractor = self._get_agent_by_type("ExtractorAgent")
            evaluator = self._get_agent_by_type("EvaluatorAgent")
            generator = self._get_agent_by_type("GeneratorAgent")

            # Extract PDF content
            extraction_task = {
                "type": "extract",
                "file_path": task["file_path"]
            }
            extraction_id = await extractor.add_task(extraction_task)
            extraction_result = await self._wait_for_task(extractor, extraction_id)
            if not extraction_result or extraction_result.get("status") == "error":
                self.metrics['failed_tasks'] += 1
                return {
                    "status": "error",
                    "error": "Extraction failed",
                    "details": extraction_result.get("result", {})
                }

            # Evaluate extraction
            evaluation_task = {
                "type": "evaluate",
                "content": extraction_result["result"]
            }
            evaluation_id = await evaluator.add_task(evaluation_task)
            evaluation_result = await self._wait_for_task(evaluator, evaluation_id)

            # Generate if valid
            generation_result = {"status": "skipped"}
            if evaluation_result and evaluation_result.get("result", {}).get("is_valid_json"):
                generation_task = {
                    "type": "generate",
                    "content": extraction_result["result"]
                }
                generation_id = await generator.add_task(generation_task)
                generation_result = await self._wait_for_task(generator, generation_id)

            self.metrics['completed_tasks'] += 1
            return {
                "status": "success",
                "extraction": extraction_result["result"],
                "evaluation": evaluation_result["result"],
                "generation": generation_result.get("result", {})
            }

        except Exception as e:
            self.metrics['failed_tasks'] += 1
            self.logger.error(f"Pipeline execution failed: {str(e)}")
            return {"status": "error", "error": str(e)}

    async def _wait_for_task(self, agent: BaseAgent, task_id: str, timeout: int = 30) -> Dict[str, Any]:
        """Wait for task completion with proper result handling"""
        start_time = datetime.now()
        while (datetime.now() - start_time).seconds < timeout:
            if task_id in agent.tasks:
                task_entry = agent.tasks[task_id]
                if task_entry["status"] != "queued":
                    return task_entry

            await asyncio.sleep(0.1)

        return {
            "status": "error",
            "result": {
                "status": "error",
                "error": "Task timeout"
            }
        }

    def _get_agent_by_type(self, agent_type: str) -> BaseAgent:
        agent = next(
            (agent for agent in self.child_agents.values()
             if agent.__class__.__name__ == agent_type),
            None
        )
        if not agent:
            raise ValueError(f"Required agent type {agent_type} not found")
        return agent


class ExtractorAgent(BaseAgent):
    def __init__(self, agent_config: AgentConfig, llm_config: LLMConfig):
        super().__init__(agent_config, llm_config)
        llm_dict = {
            "model_name": llm_config.model_name,
            "provider": llm_config.provider,
            "api_key": llm_config.api_key,
            "temperature": llm_config.temperature,
            "max_tokens": llm_config.max_tokens
        }
        self.llm_handler = LLMHandler(llm_dict)

    def evaluate_task_suitability(self, task: Dict[str, Any]) -> float:
        return 1.0 if task.get("type") == "extract" else 0.0

    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute extraction task with proper result handling"""
        try:
            if not isinstance(task, dict):
                raise ValueError("Task must be a dictionary")

            file_path = task.get("file_path")
            if not file_path:
                return {
                    "status": "error",
                    "error": "No file path provided"
                }
            path = Path(file_path)
            if not path.exists():
                return {
                    "status": "error",
                    "error": f"File not found: {file_path}"
                }
            extraction_result = await self._extract_pdf_content(path)
            if extraction_result["status"] == "success":
                try:
                    await self.enhanced_memory.store_semantic(
                        json.dumps(extraction_result),
                        {"type": "extraction_result", "filename": path.name}
                    )
                except Exception as mem_error:
                    self.logger.warning(f"Failed to store in memory: {str(mem_error)}")

            return extraction_result

        except Exception as e:
            self.logger.error(f"Extraction failed: {str(e)}")
            return {
                "status": "error",
                "error": str(e)
            }

    async def _extract_pdf_content(self, file_path: Path) -> Dict[str, Any]:
        """Extract text content from PDF with proper error handling"""
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = pypdf.PdfReader(file)
                content_dict = {}
                for i in range(len(pdf_reader.pages)):
                    try:
                        page = pdf_reader.pages[i]
                        text = page.extract_text()
                        if text and text.strip():
                            content_dict[f"page_{i + 1}"] = text.strip()
                    except Exception as page_error:
                        self.logger.warning(f"Failed to extract page {i + 1}: {str(page_error)}")
                        content_dict[f"page_{i + 1}"] = f"Error: {str(page_error)}"
                if not content_dict:
                    return {
                        "status": "error",
                        "error": "No text content found in PDF"
                    }
                return {
                    "status": "success",
                    "metadata": {
                        "filename": file_path.name,
                        "total_pages": len(pdf_reader.pages),
                        "extracted_pages": len(content_dict),
                        "extraction_time": datetime.now().isoformat()
                    },
                    "content": content_dict
                }

        except Exception as e:
            self.logger.error(f"PDF extraction error: {str(e)}")
            return {
                "status": "error",
                "error": f"PDF extraction failed: {str(e)}"
            }

class EvaluatorAgent(BaseAgent):
    def __init__(self, agent_config: AgentConfig, llm_config: LLMConfig):
        super().__init__(agent_config, llm_config)
        llm_dict = {
            "model_name": llm_config.model_name,
            "provider": llm_config.provider,
            "api_key": llm_config.api_key,
            "temperature": llm_config.temperature,
            "max_tokens": llm_config.max_tokens
        }
        self.llm_handler = LLMHandler(llm_dict)

    def evaluate_task_suitability(self, task: Dict[str, Any]) -> float:
        return 1.0 if task.get("type") == "evaluate" else 0.0

    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate extracted content"""
        try:
            # Validate task input
            if not isinstance(task, dict):
                raise ValueError("Task must be a dictionary")

            content = task.get("content")
            if not content:
                return {
                    "status": "error",
                    "error": "No content provided for evaluation"
                }

            # Evaluate the content
            evaluation_result = self._evaluate_content(content)

            # Store evaluation result in memory
            try:
                await self.enhanced_memory.store_semantic(
                    json.dumps(evaluation_result),
                    {"type": "evaluation_result"}
                )
            except Exception as mem_error:
                self.logger.warning(f"Failed to store in memory: {str(mem_error)}")

            return evaluation_result

        except Exception as e:
            self.logger.error(f"Evaluation failed: {str(e)}")
            return {
                "status": "error",
                "error": str(e)
            }

    def _evaluate_content(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate the extracted content"""
        try:
            # Check basic structure
            if not isinstance(content, dict):
                return {
                    "status": "error",
                    "error": "Content must be a dictionary"
                }

            # Check required fields
            metadata = content.get("metadata", {})
            content_data = content.get("content", {})

            if not metadata or not content_data:
                return {
                    "status": "error",
                    "error": "Missing required fields: metadata or content"
                }

            # Validate content structure
            validation_results = {
                "has_metadata": bool(metadata),
                "has_content": bool(content_data),
                "total_pages": metadata.get("total_pages", 0),
                "extracted_pages": metadata.get("extracted_pages", 0),
                "is_valid_json": True
            }

            return {
                "status": "success",
                "is_valid_json": True,
                "validation_results": validation_results,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            return {
                "status": "error",
                "error": f"Content validation failed: {str(e)}"
            }


class GeneratorAgent(BaseAgent):
    def __init__(self, agent_config: AgentConfig, llm_config: LLMConfig):
        super().__init__(agent_config, llm_config)
        llm_dict = {
            "model_name": llm_config.model_name,
            "provider": llm_config.provider,
            "api_key": llm_config.api_key,
            "temperature": llm_config.temperature,
            "max_tokens": llm_config.max_tokens
        }
        self.llm_handler = LLMHandler(llm_dict)

    def evaluate_task_suitability(self, task: Dict[str, Any]) -> float:
        return 1.0 if task.get("type") == "generate" else 0.0

    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute generation task with proper result handling"""
        try:
            if not isinstance(task, dict):
                raise ValueError("Task must be a dictionary")

            content = task.get("content")
            if not content:
                return {
                    "status": "error",
                    "error": "No content provided for generation"
                }

            # Get similar documents from memory
            try:
                similar_docs = await self.enhanced_memory.semantic_search(
                    json.dumps(content),
                    limit=5
                )
            except Exception as mem_error:
                self.logger.warning(f"Memory search failed: {str(mem_error)}")
                similar_docs = []

            # Prepare content for LLM
            text_content = self._prepare_text(content)

            # Generate response using LLM
            messages = [
                {
                    "role": "system",
                    "content": f"Goal: {self.agent_config.get('goal', 'Analyze content')}. "
                               f"Generate insights based on the provided content."
                },
                {
                    "role": "user",
                    "content": text_content
                }
            ]

            try:
                response = await self.llm_handler.generate_response(messages)
                result = {
                    "status": "success",
                    "content": response.get("content", ""),
                    "timestamp": datetime.now().isoformat(),
                    "metadata": {
                        "similar_docs_found": len(similar_docs),
                        "input_length": len(text_content)
                    }
                }
            except Exception as llm_error:
                return {
                    "status": "error",
                    "error": f"LLM generation failed: {str(llm_error)}"
                }

            # Store result in memory
            try:
                await self.enhanced_memory.store_semantic(
                    json.dumps(result),
                    {"type": "generation_result"}
                )
            except Exception as mem_error:
                self.logger.warning(f"Failed to store in memory: {str(mem_error)}")

            return result

        except Exception as e:
            self.logger.error(f"Generation failed: {str(e)}")
            return {
                "status": "error",
                "error": str(e)
            }

    def _prepare_text(self, content: Dict[str, Any]) -> str:
        """Prepare text content for LLM processing"""
        try:
            # Extract metadata
            metadata = content.get("metadata", {})
            filename = metadata.get("filename", "Unknown")
            total_pages = metadata.get("total_pages", 0)

            # Extract content
            pages_content = content.get("content", {})
            if not pages_content:
                return "No content available for analysis."

            # Build text content
            text_parts = [
                f"Document: {filename}",
                f"Total Pages: {total_pages}",
                "\nContent:"
            ]

            # Add page content
            for page_num, text in sorted(pages_content.items()):
                if text and isinstance(text, str):
                    text_parts.append(f"\n{page_num}: {text.strip()}")

            return "\n".join(text_parts)

        except Exception as e:
            self.logger.error(f"Error preparing text: {str(e)}")
            return "Error preparing content for analysis."