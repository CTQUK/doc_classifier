from __future__ import annotations
import logging
import time
from typing import Optional

from doc_classifier.config import ClassifierConfig
from doc_classifier.exceptions import UnsupportedFormatError
from doc_classifier.extractors.registry import ExtractorRegistry
from doc_classifier.models import ClassificationReport
from doc_classifier.reconciler import reconcile
from doc_classifier.utils import detect_format_group, validate_file

logger = logging.getLogger(__name__)


class DocumentClassifier:

    def __init__(
        self,
        config: Optional[ClassifierConfig] = None,
        registry: Optional[ExtractorRegistry] = None,
    ) -> None:
        self.config = config or ClassifierConfig()
        self.registry = registry or ExtractorRegistry(self.config)

        if registry is None:
            self.registry.register_all_defaults()

    def classify(self, filepath: str) -> ClassificationReport:
        start = time.perf_counter()
        validate_file(filepath)

        fmt_group = detect_format_group(filepath)
        logger.info("File '%s' detected as format group: %s", filepath, fmt_group)

        extractors = self.registry.get_extractors(fmt_group)
        if not extractors:
            raise UnsupportedFormatError(
                f"No extractors registered for format group '{fmt_group}'"
            )

        results = []
        for ext in extractors:
            logger.debug("Running extractor: %s", ext.name)
            try:
                res = ext.extract(filepath)
                results.append(res)
                if res.errors:
                    for err in res.errors:
                        logger.warning("[%s] %s", ext.name, err)
            except Exception as exc:
                logger.error("Extractor '%s' crashed: %s", ext.name, exc)

        elapsed_ms = (time.perf_counter() - start) * 1000

        report = reconcile(
            filepath=filepath,
            results=results,
            config=self.config,
            processing_time_ms=elapsed_ms,
        )

        logger.info(
            "Classification for '%s': %s (%.1f ms, %d hits)",
            filepath, report.detected_label,
            report.processing_time_ms, len(report.all_hits),
        )

        return report
