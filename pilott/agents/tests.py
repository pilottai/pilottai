import asyncio
import os
from typing import Dict, List, Optional, Set, Any, Union
from datetime import datetime

from pilott import Serve
from pilott.core import Agent, AgentConfig, LLMConfig, AgentStatus


class WebAnalyzerAgent(Agent):
    """Enhanced agent for website analysis and email extraction"""

    def __init__(
            self,
            role: str = "Web Analyzer",
            goal: str = "Analyze websites and extract information",
            backstory: str = "Specialized in analyzing websites and extracting valuable information",
            verbose: bool = False,
            llm_config: Optional[Union[Dict, LLMConfig]] = None
    ):
        # Initialize base agent
        super().__init__(
            role=role,
            goal=goal,
            backstory=backstory,
            verbose=verbose,
            llm_config=llm_config
        )

        # Web analyzer specific attributes
        self.session = None
        self.analyzed_urls = set()
        self.metrics = {
            'total_tasks': 0,
            'completed_tasks': 0,
            'failed_tasks': 0,
            'queue_utilization': 0.0,
            'success_rate': 1.0,
            'resource_usage': 0.0,
            'urls_analyzed': 0,
            'emails_found': 0
        }
        self.last_heartbeat = datetime.now()

    async def get_metrics(self) -> Dict[str, Any]:
        """Get agent metrics"""
        total_tasks = self.metrics['total_tasks']
        self.metrics.update({
            'success_rate': (self.metrics['completed_tasks'] / total_tasks) if total_tasks > 0 else 1.0,
            'queue_utilization': self.task_queue.qsize() / self.task_queue.maxsize if self.task_queue.maxsize > 0 else 0.0,
            'resource_usage': len(self.analyzed_urls) / 100  # Example metric
        })
        return self.metrics

    async def send_heartbeat(self) -> datetime:
        """Send heartbeat signal"""
        self.last_heartbeat = datetime.now()
        return self.last_heartbeat

    async def reset(self) -> None:
        """Reset agent state"""
        # Clear basic state
        self.analyzed_urls.clear()
        self.metrics = {
            'total_tasks': 0,
            'completed_tasks': 0,
            'failed_tasks': 0,
            'queue_utilization': 0.0,
            'success_rate': 1.0,
            'resource_usage': 0.0,
            'urls_analyzed': 0,
            'emails_found': 0
        }

        # Reset task queue
        self.task_queue = asyncio.Queue(maxsize=self.agent_config.max_queue_size if self.agent_config else 100)

        # Reset status
        self.status = AgentStatus.IDLE
        self.last_heartbeat = datetime.now()

        # Clear session
        if self.session:
            await self.session.close()
            self.session = None

    async def _process_task(self, task: Dict[str, Any], context: Optional[Dict] = None) -> Dict[str, Any]:
        """Process the analysis task"""
        try:
            url = task.get("url")
            if not url:
                return {
                    "status": "error",
                    "error": "URL is required"
                }

            # Setup session if needed
            if not self.session:
                await self._setup_session()

            try:
                # Fetch and analyze content
                content = await self._fetch_webpage(url)
                if not content:
                    return {
                        "status": "error",
                        "error": "Failed to fetch content"
                    }

                # Extract information
                links = await self._extract_links(content, url)
                emails = await self._extract_emails(content)
                self.analyzed_urls.add(url)

                # Process discovered links (up to 5)
                additional_emails = set()
                for link in links[:5]:
                    if link not in self.analyzed_urls:
                        self.analyzed_urls.add(link)
                        link_content = await self._fetch_webpage(link)
                        if link_content:
                            link_emails = await self._extract_emails(link_content)
                            additional_emails.update(link_emails)

                # Update metrics
                self.metrics['urls_analyzed'] += 1
                self.metrics['emails_found'] += len(emails) + len(additional_emails)
                self.metrics['total_tasks'] += 1
                self.metrics['completed_tasks'] += 1

                # Combine results
                all_emails = emails.union(additional_emails)
                result = {
                    "status": "success",
                    "output": {
                        "url": url,
                        "links_found": len(links),
                        "emails_found": len(all_emails),
                        "links": links,
                        "emails": list(all_emails),
                        "timestamp": datetime.now().isoformat()
                    }
                }

                return result

            except Exception as e:
                self.metrics['failed_tasks'] += 1
                raise e

        except Exception as e:
            self.logger.error(f"Analysis failed for {url}: {str(e)}")
            return {
                "status": "error",
                "error": str(e)
            }
        finally:
            if self.session and self.status == AgentStatus.STOPPED:
                await self.session.close()
                self.session = None

    # ... rest of the WebAnalyzerAgent methods stay the same ...


# Example usage
async def main():
    # Create agent
    agent = WebAnalyzerAgent(
        verbose=True,
        llm_config={
            "model_name": "gpt-4",
            "provider": "openai",
            "api_key": os.getenv('OPENAI_API_KEY')
        }
    )

    serve = Serve(
        name="Website Analysis Service",
        agents=[agent],
        verbose=True
    )

    # Start service
    await serve.start()

    try:
        # Execute analysis
        results = await serve.execute([{
            "type": "analyze",
            "url": "https://example.com"
        }])

        # Print results
        for result in results:
            if result.status == "completed":
                print("\nAnalysis Results:")
                print(result.result)
            else:
                print(f"Error: {result.error}")

    finally:
        await serve.stop()

if __name__ == "__main__":
    asyncio.run(main())