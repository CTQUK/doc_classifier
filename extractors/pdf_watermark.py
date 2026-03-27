from __future__ import annotations
import logging
from typing import Set

from extractors.base import BaseExtractor
from models import ExtractionResult
from utils import scan_text_for_keywords

logger = logging.getLogger(__name__)


class PdfWatermarkExtractor(BaseExtractor):

    @property
    def name(self) -> str:
        return "pdf_watermark"

    @property
    def supported_groups(self) -> Set[str]:
        return {"pdf"}

    def extract(self, filepath: str) -> ExtractionResult:
        result = ExtractionResult(extractor_name=self.name)

        try:
            import pdfplumber
        except ImportError:
            result.errors.append("pdfplumber not installed")
            return result

        try:
            with pdfplumber.open(filepath) as pdf:
                max_pages = min(len(pdf.pages), self.config.ocr_max_pages)
                for i in range(max_pages):
                    page = pdf.pages[i]
                    text = page.extract_text() or ""
                    if text.strip():
                        result.raw_metadata[f"page_{i+1}_text_snippet"] = text[:300]
                        hits = scan_text_for_keywords(
                            text=text,
                            config=self.config,
                            source="pdf_text_layer",
                            field_name=f"page_{i+1}",
                            page=i + 1,
                            confidence=0.90,
                        )
                        result.hits.extend(hits)
        except Exception as exc:
            result.errors.append(f"PDF text extraction failed: {exc}")

        return result
