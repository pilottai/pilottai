import os
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
import re
from bs4 import BeautifulSoup
import markdown
import yaml
import json
from xml.etree import ElementTree as ET

from pilott.knowledge.source.base_input import BaseInputSource


class MarkupInput(BaseInputSource):
    """
    Input source for processing markup documents (HTML, XML, Markdown, YAML).
    Extracts and processes content from various markup formats.
    """

    def __init__(
        self,
        name: str,
        markup_type: str = "html",  # html, xml, markdown, yaml
        file_path: Optional[str] = None,
        file_content: Optional[Union[str, bytes]] = None,
        extract_metadata: bool = True,
        extract_text_only: bool = True,
        keep_structure: bool = False,
        selectors: Optional[List[str]] = None,  # CSS selectors for HTML/XML
        **kwargs
    ):
        super().__init__(name=name, **kwargs)
        self.markup_type = markup_type.lower()
        self.file_path = file_path
        self.file_content = file_content
        self.extract_metadata = extract_metadata
        self.extract_text_only = extract_text_only
        self.keep_structure = keep_structure
        self.selectors = selectors or []

        # Validate markup type
        valid_types = ["html", "xml", "markdown", "md", "yaml", "yml"]
        if self.markup_type not in valid_types:
            raise ValueError(f"Invalid markup type: {self.markup_type}. Must be one of {valid_types}")

        # Storage
        self.text_content = None
        self.raw_content = None
        self.metadata = {}
        self.structured_data = None

    async def connect(self) -> bool:
        """Check if the markup content is accessible"""
        try:
            # Handle direct content
            if self.file_content is not None:
                if isinstance(self.file_content, bytes):
                    self.raw_content = self.file_content.decode('utf-8')
                else:
                    self.raw_content = self.file_content

                self.is_connected = bool(self.raw_content)
                return self.is_connected

            # Handle file path
            if self.file_path:
                if not os.path.exists(self.file_path):
                    self.logger.error(f"File not found: {self.file_path}")
                    self.is_connected = False
                    return False

                if not os.access(self.file_path, os.R_OK):
                    self.logger.error(f"File not readable: {self.file_path}")
                    self.is_connected = False
                    return False

                with open(self.file_path, 'r', encoding='utf-8') as f:
                    self.raw_content = f.read()

                self.is_connected = bool(self.raw_content)
                return self.is_connected

            self.logger.error("No content source provided")
            self.is_connected = False
            return False

        except Exception as e:
            self.logger.error(f"Connection error: {str(e)}")
            self.is_connected = False
            return False

    async def query(self, query: str) -> Any:
        """Search for query in the processed content"""
        if not self.is_connected or not self.text_content:
            if not await self.process_markup():
                raise ValueError("Could not process markup content")

        self.access_count += 1
        self.last_access = datetime.now()

        # Handle special queries
        if query.startswith("metadata:"):
            return self._query_metadata(query[9:].strip())

        if query.startswith("selector:") and self.markup_type in ["html", "xml"]:
            return self._query_selector(query[9:].strip())

        # Simple text search implementation
        results = []
        if query.lower() in self.text_content.lower():
            context_size = 200  # Characters before and after match

            # Find all occurrences
            start_idx = 0
            query_lower = query.lower()
            text_lower = self.text_content.lower()

            while True:
                idx = text_lower.find(query_lower, start_idx)
                if idx == -1:
                    break

                # Get context around the match
                context_start = max(0, idx - context_size)
                context_end = min(len(self.text_content), idx + len(query) + context_size)
                context = self.text_content[context_start:context_end]

                results.append({
                    "match": self.text_content[idx:idx + len(query)],
                    "context": context,
                    "position": idx
                })

                start_idx = idx + len(query)

        return results

    def _query_metadata(self, key: str) -> Any:
        """Query the extracted metadata"""
        if not self.metadata:
            return {"error": "No metadata available"}

        if not key:
            return self.metadata

        # Handle nested keys (e.g., "author.name")
        parts = key.split(".")
        current = self.metadata

        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return {"error": f"Metadata key '{key}' not found"}

        return {key: current}

    def _query_selector(self, selector: str) -> List[Dict[str, Any]]:
        """Query HTML/XML using CSS selectors"""
        if not self.raw_content:
            return {"error": "No content available"}

        try:
            if self.markup_type == "html":
                soup = BeautifulSoup(self.raw_content, 'html.parser')
                elements = soup.select(selector)
            else:  # xml
                # For XML, use ElementTree with limited CSS selector support
                root = ET.fromstring(self.raw_content)
                # Very basic selector implementation for XML
                if selector.startswith("#"):
                    # ID selector
                    id_value = selector[1:]
                    elements = [elem for elem in root.findall(".//*")
                                if elem.get("id") == id_value]
                elif selector.startswith("."):
                    # Class selector
                    class_value = selector[1:]
                    elements = [elem for elem in root.findall(".//*")
                                if elem.get("class") and class_value in elem.get("class").split()]
                else:
                    # Tag selector
                    elements = root.findall(f".//{selector}")

            results = []
            for element in elements:
                if self.markup_type == "html":
                    results.append({
                        "text": element.get_text(),
                        "html": str(element)
                    })
                else:  # xml
                    results.append({
                        "text": ET.tostring(element, encoding='unicode'),
                        "tag": element.tag,
                        "attributes": element.attrib
                    })

            return results

        except Exception as e:
            return {"error": f"Selector query error: {str(e)}"}

    async def validate_content(self) -> bool:
        """Validate that markup content is accessible and can be processed"""
        if not self.is_connected:
            if not await self.connect():
                return False

        if not self.raw_content:
            return False

        # Validate markup based on type
        try:
            if self.markup_type == "html":
                BeautifulSoup(self.raw_content, 'html.parser')
            elif self.markup_type == "xml":
                ET.fromstring(self.raw_content)
            elif self.markup_type in ["markdown", "md"]:
                # Markdown doesn't really have a validation step
                pass
            elif self.markup_type in ["yaml", "yml"]:
                yaml.safe_load(self.raw_content)
            else:
                return False

            return True

        except Exception as e:
            self.logger.error(f"Validation error for {self.markup_type}: {str(e)}")
            return False

    async def process_markup(self) -> bool:
        """Process markup content based on its type"""
        if not self.is_connected or not self.raw_content:
            if not await self.connect():
                return False

        try:
            if self.markup_type == "html":
                return self._process_html()
            elif self.markup_type == "xml":
                return self._process_xml()
            elif self.markup_type in ["markdown", "md"]:
                return self._process_markdown()
            elif self.markup_type in ["yaml", "yml"]:
                return self._process_yaml()
            else:
                self.logger.error(f"Unsupported markup type: {self.markup_type}")
                return False

        except Exception as e:
            self.logger.error(f"Error processing {self.markup_type}: {str(e)}")
            return False

    def _process_html(self) -> bool:
        """Process HTML content"""
        try:
            soup = BeautifulSoup(self.raw_content, 'html.parser')

            # Extract metadata
            if self.extract_metadata:
                self._extract_html_metadata(soup)

            # Extract text content
            if self.extract_text_only:
                if self.selectors:
                    # Extract text from specific selectors
                    text_parts = []
                    for selector in self.selectors:
                        elements = soup.select(selector)
                        for element in elements:
                            text_parts.append(element.get_text())

                    self.text_content = "\n\n".join(text_parts)
                else:
                    # Remove script and style elements
                    for script in soup(["script", "style"]):
                        script.extract()

                    # Extract text
                    self.text_content = soup.get_text(separator='\n')

                    # Clean up whitespace
                    self.text_content = re.sub(r'\n+', '\n', self.text_content)
                    self.text_content = re.sub(r'\s+', ' ', self.text_content)
                    self.text_content = self.text_content.strip()
            else:
                # Keep full HTML
                self.text_content = str(soup)

            return bool(self.text_content)

        except Exception as e:
            self.logger.error(f"HTML processing error: {str(e)}")
            return False

    def _extract_html_metadata(self, soup: BeautifulSoup) -> None:
        """Extract metadata from HTML"""
        metadata = {}

        # Extract title
        title_tag = soup.find('title')
        if title_tag:
            metadata['title'] = title_tag.string

        # Extract meta tags
        for meta in soup.find_all('meta'):
            name = meta.get('name') or meta.get('property')
            content = meta.get('content')

            if name and content:
                metadata[name] = content

        # Extract Open Graph metadata
        og_metadata = {}
        for meta in soup.find_all('meta', property=re.compile('^og:')):
            prop = meta.get('property')
            if prop and prop.startswith('og:'):
                key = prop[3:]  # Remove 'og:' prefix
                og_metadata[key] = meta.get('content')

        if og_metadata:
            metadata['og'] = og_metadata

        # Extract JSON-LD
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                ld_data = json.loads(script.string)
                if 'jsonld' not in metadata:
                    metadata['jsonld'] = []
                metadata['jsonld'].append(ld_data)
            except Exception as e:
                self.logger.error(f"Error parsing JSON-LD: {str(e)}")

        self.metadata = metadata

    def _process_xml(self) -> bool:
        """Process XML content"""
        try:
            root = ET.fromstring(self.raw_content)

            # Extract text content
            if self.extract_text_only:
                # Extract all text from XML
                def get_text(element):
                    text = element.text or ""
                    for child in element:
                        text += get_text(child)
                    if element.tail:
                        text += element.tail
                    return text

                self.text_content = get_text(root)

                # Clean up whitespace
                self.text_content = re.sub(r'\s+', ' ', self.text_content).strip()
            else:
                # Keep full XML
                self.text_content = ET.tostring(root, encoding='unicode')

            # Extract basic metadata
            if self.extract_metadata:
                self.metadata = {
                    'root_tag': root.tag,
                    'attributes': dict(root.attrib)
                }

            return bool(self.text_content)

        except Exception as e:
            self.logger.error(f"XML processing error: {str(e)}")
            return False

    def _process_markdown(self) -> bool:
        """Process Markdown content"""
        try:
            # Check for YAML frontmatter
            if self.extract_metadata:
                frontmatter, content = self._extract_frontmatter(self.raw_content)
                if frontmatter:
                    self.metadata = frontmatter
                    markdown_content = content
                else:
                    markdown_content = self.raw_content
            else:
                markdown_content = self.raw_content

            # Convert to HTML if needed
            if not self.extract_text_only and self.keep_structure:
                self.text_content = markdown.markdown(markdown_content)
            else:
                # Convert markdown to plaintext
                # First convert to HTML, then extract text with BeautifulSoup
                html = markdown.markdown(markdown_content)
                soup = BeautifulSoup(html, 'html.parser')
                self.text_content = soup.get_text(separator='\n')

                # Clean up whitespace
                self.text_content = re.sub(r'\n+', '\n', self.text_content)
                self.text_content = self.text_content.strip()

            return bool(self.text_content)

        except Exception as e:
            self.logger.error(f"Markdown processing error: {str(e)}")
            return False

    def _extract_frontmatter(self, content: str) -> tuple:
        """Extract YAML frontmatter from markdown"""
        frontmatter_match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)', content, re.DOTALL)

        if frontmatter_match:
            frontmatter_yaml = frontmatter_match.group(1)
            content_without_frontmatter = frontmatter_match.group(2)

            try:
                frontmatter = yaml.safe_load(frontmatter_yaml)
                return frontmatter, content_without_frontmatter
            except Exception as e:
                self.logger.error(f"Error parsing frontmatter: {str(e)}")
                return None, content

        return None, content

    def _process_yaml(self) -> bool:
        """Process YAML content"""
        try:
            # Parse YAML
            data = yaml.safe_load(self.raw_content)
            self.structured_data = data

            if self.extract_metadata and isinstance(data, dict):
                # Use top-level keys as metadata
                self.metadata = {k: v for k, v in data.items() if isinstance(v, (str, int, float, bool))}

            # Convert to text
            if self.extract_text_only:
                # Flatten YAML into text representation
                text_parts = []

                def flatten_yaml(obj, prefix=''):
                    if isinstance(obj, dict):
                        for k, v in obj.items():
                            new_prefix = f"{prefix}.{k}" if prefix else k
                            flatten_yaml(v, new_prefix)
                    elif isinstance(obj, list):
                        for i, item in enumerate(obj):
                            new_prefix = f"{prefix}[{i}]"
                            flatten_yaml(item, new_prefix)
                    else:
                        text_parts.append(f"{prefix}: {obj}")

                flatten_yaml(data)
                self.text_content = "\n".join(text_parts)
            else:
                # Keep structured representation as YAML
                self.text_content = yaml.dump(data, sort_keys=False)

            return bool(self.text_content)

        except Exception as e:
            self.logger.error(f"YAML processing error: {str(e)}")
            return False

    async def _process_content(self) -> None:
        """Process markup content and chunk it"""
        if not self.text_content:
            if not await self.process_markup():
                return

        self.chunks = self._chunk_text(self.text_content)
        source_desc = self.file_path if self.file_path else f"{self.markup_type} data"
        self.logger.info(f"Created {len(self.chunks)} chunks from {source_desc}")
