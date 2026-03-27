from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from config import ClassificationLevel


@dataclass(frozen=True)
class ExtractionHit:
    source: str
    field_name: str
    raw_value: str
    matched_keyword: str
    level: ClassificationLevel
    page: Optional[int] = None
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractionResult:
    extractor_name: str
    hits: List[ExtractionHit] = field(default_factory=list)
    raw_metadata: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)

    @property
    def highest_level(self) -> ClassificationLevel:
        if not self.hits:
            return ClassificationLevel.UNKNOWN
        return max(h.level for h in self.hits)


@dataclass
class ClassificationReport:
    filepath: str
    detected_level: ClassificationLevel
    detected_label: str
    all_hits: List[ExtractionHit] = field(default_factory=list)
    extractor_results: List[ExtractionResult] = field(default_factory=list)
    processing_time_ms: float = 0.0
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "filepath": self.filepath,
            "detected_level": self.detected_level.name,
            "detected_level_value": int(self.detected_level),
            "detected_label": self.detected_label,
            "hits": [
                {
                    "source": h.source,
                    "field": h.field_name,
                    "raw_value": h.raw_value,
                    "keyword": h.matched_keyword,
                    "level": h.level.name,
                    "page": h.page,
                    "confidence": h.confidence,
                }
                for h in self.all_hits
            ],
            "processing_time_ms": round(self.processing_time_ms, 2),
            "timestamp": self.timestamp,
        }
