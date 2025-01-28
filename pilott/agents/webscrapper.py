from typing import Dict, Any, List, Optional, Union
import re
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
from dataclasses import dataclass

from pilott.core.agent import BaseAgent
from pilott.core.config import AgentConfig, LLMConfig


@dataclass
class ScrapingConfig:
    """Configuration for web scraping"""
    url: str
    selectors: Dict[str, Union[str, List[str]]]  # Map field names to CSS selectors
    wait_time: int = 5  # Seconds to wait for page load
    use_headless: bool = True
    pagination: Optional[Dict[str, str]] = None  # Pagination selectors if needed
    required_fields: List[str] = None  # Fields that must be present
    custom_filters: Dict[str, callable] = None  # Custom filtering functions


class GenericWebScraperAgent(BaseAgent):
    """Generic web scraper that can be configured for any website"""

    def __init__(self,
                 agent_config: AgentConfig,
                 llm_config: LLMConfig,
                 scraping_config: ScrapingConfig):
        super().__init__(agent_config, llm_config)
        self.scraping_config = scraping_config
        self.driver = None
        self._setup_webdriver()

    def _setup_webdriver(self):
        """Initialize webdriver with configuration"""
        chrome_options = Options()
        if self.scraping_config.use_headless:
            chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.implicitly_wait(self.scraping_config.wait_time)

    async def _process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process a scraping task"""
        try:
            task_type = task.get('type', 'scrape')

            if task_type == 'scrape':
                return await self._scrape_data()
            elif task_type == 'analyze':
                return await self._analyze_page()
            elif task_type == 'extract':
                return await self._extract_specific(task.get('fields', []))
            else:
                raise ValueError(f"Unknown task type: {task_type}")

        except Exception as e:
            self.logger.error(f"Task execution error: {str(e)}")
            return {"status": "error", "error": str(e)}

    async def _scrape_data(self) -> Dict[str, Any]:
        """Main scraping function"""
        try:
            self.driver.get(self.scraping_config.url)
            all_data = []
            page = 1

            while True:
                soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                page_data = await self._extract_page_data(soup)

                if page_data:
                    all_data.extend(page_data)

                # Handle pagination if configured
                if self.scraping_config.pagination and self._has_next_page(soup):
                    if not self._go_to_next_page():
                        break
                    page += 1
                else:
                    break

            # Verify required fields
            if self.scraping_config.required_fields:
                all_data = self._verify_required_fields(all_data)

            # Apply custom filters
            if self.scraping_config.custom_filters:
                all_data = self._apply_custom_filters(all_data)

            return {
                "status": "completed",
                "data": all_data,
                "pages_scraped": page,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            self.logger.error(f"Scraping error: {str(e)}")
            raise

    async def _extract_page_data(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Extract data from a single page"""
        page_data = []

        for field, selector in self.scraping_config.selectors.items():
            if isinstance(selector, list):
                # Try multiple selectors for the field
                for sel in selector:
                    elements = soup.select(sel)
                    if elements:
                        break
            else:
                elements = soup.select(selector)

            field_data = [elem.text.strip() for elem in elements if elem.text.strip()]

            # Create record for each found element
            while len(page_data) < len(field_data):
                page_data.append({})

            # Add field data to records
            for i, value in enumerate(field_data):
                if i < len(page_data):
                    page_data[i][field] = value

        return page_data

    def _has_next_page(self, soup: BeautifulSoup) -> bool:
        """Check if there's a next page based on pagination config"""
        if not self.scraping_config.pagination:
            return False

        next_selector = self.scraping_config.pagination.get('next_button')
        if not next_selector:
            return False

        next_button = soup.select_one(next_selector)
        return bool(next_button and not next_button.get('disabled'))

    def _go_to_next_page(self) -> bool:
        """Attempt to navigate to next page"""
        try:
            next_selector = self.scraping_config.pagination['next_button']
            next_button = self.driver.find_element_by_css_selector(next_selector)
            if next_button.is_enabled():
                next_button.click()
                return True
            return False
        except Exception as e:
            self.logger.warning(f"Navigation error: {str(e)}")
            return False

    def _verify_required_fields(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter out records missing required fields"""
        if not self.scraping_config.required_fields:
            return data

        return [
            record for record in data
            if all(field in record for field in self.scraping_config.required_fields)
        ]

    def _apply_custom_filters(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Apply custom filtering functions to the data"""
        filtered_data = data

        for field, filter_func in self.scraping_config.custom_filters.items():
            filtered_data = [
                record for record in filtered_data
                if field not in record or filter_func(record[field])
            ]

        return filtered_data

    async def stop(self):
        """Cleanup resources"""
        if self.driver:
            self.driver.quit()
        await super().stop()


# Example usage
async def main():
    # Define scraping configuration
    scraping_config = ScrapingConfig(
        url="https://example.com",
        selectors={
            "title": "h1.title",  # Single selector
            "price": [".price", ".sale-price"],  # Multiple selectors (fallback)
            "description": "div.description"
        },
        pagination={
            "next_button": "a.next-page"
        },
        required_fields=["title", "price"],
        custom_filters={
            "price": lambda x: float(re.sub(r'[^\d.]', '', x)) <= 100  # Filter items <= $100
        }
    )

    # Configure the agent
    agent_config = AgentConfig(
        role="web_scraper",
        goal="Extract structured data from websites",
        description="Generic web scraping agent",
        verbose=True
    )

    llm_config = LLMConfig(
        model_name="gpt-4",
        provider="openai",
        api_key="your-api-key"
    )

    # Create and start the agent
    scraper = GenericWebScraperAgent(
        agent_config=agent_config,
        llm_config=llm_config,
        scraping_config=scraping_config
    )

    await scraper.start()

    # Execute scraping task
    task = {"type": "scrape"}
    result = await scraper.execute_task(task)
    print(result)

    await scraper.stop()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())