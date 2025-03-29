import os
from typing import Any, Optional
from datetime import datetime
import io
from PIL import Image
import pytesseract
import numpy as np

from pilott.knowledge.source.base_input import BaseInputSource


class ImageInput(BaseInputSource):
    """
    Input source for processing images.
    Extracts text content from images using OCR (Optical Character Recognition).
    """

    def __init__(
        self,
        name: str,
        file_path: Optional[str] = None,
        file_content: Optional[bytes] = None,
        image: Optional[Any] = None,
        lang: str = 'eng',
        ocr_config: str = '--psm 3',  # Page segmentation mode 3: fully automatic page segmentation
        preprocess: bool = True,
        **kwargs
    ):
        super().__init__(name=name, **kwargs)
        self.file_path = file_path
        self.file_content = file_content
        self.image = image
        self.lang = lang
        self.ocr_config = ocr_config
        self.preprocess = preprocess
        self.text_content = None
        self.pil_image = None

    async def connect(self) -> bool:
        """Check if the image is accessible"""
        try:
            # Already have a PIL Image
            if self.image and hasattr(self.image, 'mode'):
                self.pil_image = self.image
                self.is_connected = True
                return True

            # Load from binary content
            if self.file_content is not None:
                self.pil_image = Image.open(io.BytesIO(self.file_content))
                self.is_connected = True
                return True

            # Load from file path
            if self.file_path:
                if not os.path.exists(self.file_path):
                    self.logger.error(f"Image file not found: {self.file_path}")
                    self.is_connected = False
                    return False

                if not os.access(self.file_path, os.R_OK):
                    self.logger.error(f"Image file not readable: {self.file_path}")
                    self.is_connected = False
                    return False

                self.pil_image = Image.open(self.file_path)
                self.is_connected = True
                return True

            self.logger.error("No image source provided")
            self.is_connected = False
            return False

        except Exception as e:
            self.logger.error(f"Connection error: {str(e)}")
            self.is_connected = False
            return False

    async def query(self, query: str) -> Any:
        """Search for query in the extracted text content"""
        if not self.is_connected or not self.text_content:
            if not await self.extract_text():
                raise ValueError("Could not extract text from image")

        self.access_count += 1
        self.last_access = datetime.now()

        # Simple search implementation
        results = []
        if query.lower() in self.text_content.lower():
            context_size = 100  # Characters before and after match

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

    async def validate_content(self) -> bool:
        """Validate that image content is accessible and can be processed"""
        if not self.is_connected:
            if not await self.connect():
                return False

        # Just check if the image is valid
        return self.pil_image is not None and hasattr(self.pil_image, 'mode')

    async def extract_text(self) -> bool:
        """Extract text from the image using OCR"""
        try:
            if not self.pil_image:
                if not await self.connect():
                    return False

            # Preprocess image if requested
            image_for_ocr = self.pil_image
            if self.preprocess:
                image_for_ocr = self._preprocess_image(self.pil_image)

            # Run OCR
            self.text_content = pytesseract.image_to_string(
                image_for_ocr,
                lang=self.lang,
                config=self.ocr_config
            )

            return bool(self.text_content.strip())

        except Exception as e:
            self.logger.error(f"Error extracting text from image: {str(e)}")
            return False

    def _preprocess_image(self, image):
        """Preprocess image to improve OCR results"""
        try:
            # Convert to numpy array if needed
            if isinstance(image, Image.Image):
                img = np.array(image)
            else:
                img = image

            # Convert to grayscale if image is color
            if len(img.shape) == 3 and img.shape[2] >= 3:
                img = np.mean(img[:, :, :3], axis=2).astype(np.uint8)

            # Apply binary thresholding
            _, binary_img = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

            # Apply noise reduction
            denoised = cv2.fastNlMeansDenoising(binary_img, None, 10, 7, 21)

            # Convert back to PIL if needed
            return Image.fromarray(denoised)
        except Exception as e:
            self.logger.warning(f"Error preprocessing image: {str(e)}")
            return image

    async def _process_content(self) -> None:
        """Process and chunk the extracted text content"""
        if not self.text_content:
            if not await self.extract_text():
                return

        self.chunks = self._chunk_text(self.text_content)
        source_desc = self.file_path if self.file_path else "image data"
        self.logger.info(f"Created {len(self.chunks)} chunks from image {source_desc}")
