from __future__ import annotations
import logging
import os
from typing import Set

from doc_classifier.extractors.base import BaseExtractor
from doc_classifier.models import ExtractionResult
from doc_classifier.utils import scan_text_for_keywords, detect_format_group

logger = logging.getLogger(__name__)


class ImageOcrExtractor(BaseExtractor):

    @property
    def name(self) -> str:
        return "image_ocr"

    @property
    def supported_groups(self) -> Set[str]:
        return {"pdf", "image"}

    def extract(self, filepath: str) -> ExtractionResult:
        result = ExtractionResult(extractor_name=self.name)

        file_size = os.path.getsize(filepath)
        if file_size > self.config.ocr_file_size_limit:
            result.errors.append(f"File too large for OCR ({file_size} bytes)")
            return result

        try:
            from PIL import Image
            import pytesseract
        except ImportError:
            result.errors.append("OCR dependencies missing (Pillow / pytesseract)")
            return result

        fmt = detect_format_group(filepath)

        try:
            if fmt == "image":
                img = Image.open(filepath)
                text = pytesseract.image_to_string(img)
                if text.strip():
                    result.raw_metadata["ocr_text_snippet"] = text[:500]
                    hits = scan_text_for_keywords(
                        text=text, config=self.config,
                        source="image_ocr", field_name="full_image",
                        confidence=0.75,
                    )
                    result.hits.extend(hits)
            elif fmt == "pdf":
                from pdf2image import convert_from_path
                images = convert_from_path(
                    filepath, dpi=self.config.ocr_dpi,
                    first_page=1, last_page=self.config.ocr_max_pages,
                )
                for i, img in enumerate(images):
                    text = pytesseract.image_to_string(img)
                    if text.strip():
                        result.raw_metadata[f"ocr_page_{i+1}_snippet"] = text[:500]
                        hits = scan_text_for_keywords(
                            text=text, config=self.config,
                            source="pdf_ocr", field_name=f"ocr_page_{i+1}",
                            page=i + 1, confidence=0.70,
                        )
                        result.hits.extend(hits)
        except Exception as exc:
            result.errors.append(f"OCR failed: {exc}")

        return result
