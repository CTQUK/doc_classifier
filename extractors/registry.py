from __future__ import annotations
import logging
from typing import List, Type

from doc_classifier.config import ClassifierConfig
from doc_classifier.extractors.base import BaseExtractor

logger = logging.getLogger(__name__)


class ExtractorRegistry:

    def __init__(self, config: ClassifierConfig) -> None:
        self._config = config
        self._extractors: List[BaseExtractor] = []

    def register(self, extractor_cls: Type[BaseExtractor]) -> None:
        instance = extractor_cls(self._config)
        self._extractors.append(instance)
        logger.debug("Registered extractor: %s", instance.name)

    def register_all_defaults(self) -> None:
        from doc_classifier.extractors.office_metadata import OfficeMetadataExtractor
        from doc_classifier.extractors.office_watermark import OfficeWatermarkExtractor
        from doc_classifier.extractors.pdf_metadata import PdfMetadataExtractor
        from doc_classifier.extractors.pdf_watermark import PdfWatermarkExtractor

        for cls in [
            OfficeMetadataExtractor,
            OfficeWatermarkExtractor,
            PdfMetadataExtractor,
            PdfWatermarkExtractor,
        ]:
            self.register(cls)

        if self._config.enable_ocr:
            try:
                from doc_classifier.extractors.image_ocr import ImageOcrExtractor
                self.register(ImageOcrExtractor)
            except ImportError:
                logger.warning("OCR dependencies missing. Image OCR extractor disabled.")

    def get_extractors(self, format_group: str) -> List[BaseExtractor]:
        return [e for e in self._extractors if e.handles(format_group)]

    @property
    def all_extractors(self) -> List[BaseExtractor]:
        return list(self._extractors)
