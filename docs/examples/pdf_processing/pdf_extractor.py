from typing import Dict, Any
from pathlib import Path
import pypdf
from pilott.tools import Tool


class PDFExtractorTool(Tool):
    def __init__(self):
        super().__init__(
            name="pdf_extractor",
            description="Extracts text from PDFs",
            parameters={
                "file_path": {
                    "type": "string",
                    "description": "Path to PDF file"
                }
            }
        )

    async def execute(self, file_path: str) -> Dict[str, Any]:
        try:
            path = Path(file_path)
            with open(path, 'rb') as file:
                pdf = pypdf.PdfReader(file)
                content = {
                    f"page_{i + 1}": page.extract_text()
                    for i, page in enumerate(pdf.pages)
                    if page.extract_text().strip()
                }

                return {
                    "status": "success",
                    "filename": path.name,
                    "total_pages": len(pdf.pages),
                    "content": content
                }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }