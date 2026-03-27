from __future__ import annotations
import logging
from typing import List, Set

from lxml import etree

from config import ClassifierConfig
from extractors.base import BaseExtractor
from models import ExtractionResult
from utils import get_office_subtype, scan_text_for_keywords

logger = logging.getLogger(__name__)


class OfficeWatermarkExtractor(BaseExtractor):

    @property
    def name(self) -> str:
        return "office_watermark"

    @property
    def supported_groups(self) -> Set[str]:
        return {"office"}

    def extract(self, filepath: str) -> ExtractionResult:
        result = ExtractionResult(extractor_name=self.name)
        subtype = get_office_subtype(filepath)

        try:
            if subtype == "docx":
                self._extract_docx_watermark(filepath, result)
            elif subtype == "pptx":
                self._extract_pptx_watermark(filepath, result)
        except Exception as exc:
            result.errors.append(f"Watermark extraction failed: {exc}")

        return result

    def _extract_docx_watermark(self, filepath: str, result: ExtractionResult) -> None:
        from zipfile import ZipFile

        with ZipFile(filepath, "r") as zf:
            header_files = [
                n for n in zf.namelist()
                if n.startswith("word/header") and n.endswith(".xml")
            ]
            for hf in header_files:
                raw = zf.read(hf)
                root = etree.fromstring(raw)
                watermark_texts = self._find_vml_watermarks(root)
                watermark_texts += self._find_drawingml_watermarks(root)

                for wt in watermark_texts:
                    result.raw_metadata.setdefault("watermark_texts", []).append(wt)
                    hits = scan_text_for_keywords(
                        text=wt,
                        config=self.config,
                        source="office_watermark",
                        field_name=hf,
                        confidence=0.95,
                    )
                    result.hits.extend(hits)

    @staticmethod
    def _find_vml_watermarks(root) -> List[str]:
        texts = []
        for textpath in root.iter("{urn:schemas-microsoft-com:vml}textpath"):
            string_val = textpath.get("string")
            if string_val:
                texts.append(string_val)
        return texts

    @staticmethod
    def _find_drawingml_watermarks(root) -> List[str]:
        a_ns = "http://schemas.openxmlformats.org/drawingml/2006/main"
        texts = []
        for t_elem in root.iter(f"{{{a_ns}}}t"):
            if t_elem.text and t_elem.text.strip():
                texts.append(t_elem.text.strip())
        return texts

    def _extract_pptx_watermark(self, filepath: str, result: ExtractionResult) -> None:
        from zipfile import ZipFile

        a_ns = "http://schemas.openxmlformats.org/drawingml/2006/main"

        with ZipFile(filepath, "r") as zf:
            slide_layouts = [
                n for n in zf.namelist()
                if ("slideLayout" in n or "slideMaster" in n) and n.endswith(".xml")
            ]
            for sl in slide_layouts:
                raw = zf.read(sl)
                root = etree.fromstring(raw)
                for t_elem in root.iter(f"{{{a_ns}}}t"):
                    if t_elem.text and t_elem.text.strip():
                        hits = scan_text_for_keywords(
                            text=t_elem.text.strip(),
                            config=self.config,
                            source="pptx_layout_watermark",
                            field_name=sl,
                            confidence=0.85,
                        )
                        result.hits.extend(hits)
