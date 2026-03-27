from __future__ import annotations
from typing import List

from doc_classifier.config import ClassificationLevel, ClassifierConfig
from doc_classifier.models import ClassificationReport, ExtractionResult


def _to_level(val) -> ClassificationLevel:
    """Safely coerce a level value to ClassificationLevel enum."""
    if isinstance(val, ClassificationLevel):
        return val
    try:
        return ClassificationLevel[str(val).upper()]
    except KeyError:
        return ClassificationLevel.UNKNOWN


def reconcile(
    filepath: str,
    results: List[ExtractionResult],
    config: ClassifierConfig,
    processing_time_ms: float = 0.0,
) -> ClassificationReport:
    all_hits = []
    for r in results:
        all_hits.extend(r.hits)

    if not all_hits:
        detected_level = ClassificationLevel.UNKNOWN
    else:
        detected_level = max(_to_level(h.level) for h in all_hits)

    return ClassificationReport(
        filepath=filepath,
        detected_level=detected_level,
        detected_label=detected_level.name.replace("_", " ").title(),
        all_hits=sorted(all_hits, key=lambda h: -_to_level(h.level)),
        extractor_results=results,
        processing_time_ms=processing_time_ms,
    )