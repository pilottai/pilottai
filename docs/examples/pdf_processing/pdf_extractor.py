from pilott.tools import Tool
from typing import Dict, Any
import pypdf
import io


class PDFExtractorTool(Tool):
    """Tool for extracting content from PDFs."""

    def __init__(self):
        super().__init__(
            name="pdf_extractor",
            description="Extracts text content from PDF files",
            function=self.extract_pdf
        )

    def extract_pdf(self, pdf_content: bytes) -> Dict[str, Any]:
        """Extract text content from PDF."""
        try:
            # Create PDF reader object
            pdf_file = io.BytesIO(pdf_content)
            pdf_reader = pypdf.PdfReader(pdf_file)

            # Extract content from each page
            content = {}
            for i, page in enumerate(pdf_reader.pages):
                content[f"page_{i + 1}"] = page.extract_text()

            return {
                "status": "success",
                "total_pages": len(pdf_reader.pages),
                "content": content
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }