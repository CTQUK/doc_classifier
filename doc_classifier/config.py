from __future__ import annotations
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, List


class ClassificationLevel(IntEnum):
    UNKNOWN       = 0
    NONE          = 20
    INTERNAL      = 40
    RESTRICTED    = 60
    SECRET        = 90


DEFAULT_KEYWORD_MAP = {
    "SECRET":        ClassificationLevel.SECRET,
    "RESTRICTED":    ClassificationLevel.RESTRICTED,
    "INTERNAL":      ClassificationLevel.INTERNAL,
    "NO CLASSIFICATION":  ClassificationLevel.NONE,
}

DEFAULT_CONTENT_MARKING_PROPERTIES = [
    "ClassificationContentMarkingFooterText",
    "ClassificationContentMarkingHeaderText",
    "ClassificationContentMarkingWatermarkText",
]


import json
from pathlib import Path
import logging
logger = logging.getLogger(__name__)

def _load_mip_label_cache(json_path: Path) -> Dict[str, ClassificationLevel]:
    """Load MIP label cache from a JSON file."""
    if not json_path.exists():
        logger.warning("MIP label cache file not found: %s", json_path)
        return {}
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        cache = {}
        for guid, level_name in raw.items():
            try:
                cache[guid.lower()] = ClassificationLevel[level_name.upper()]
            except KeyError:
                logger.warning("Unknown ClassificationLevel '%s' for GUID %s", level_name, guid)
        return cache
    except Exception as exc:
        logger.warning("Failed to load MIP label cache: %s", exc)
        return {}

# Default cache file location — same folder as config.py
_DEFAULT_CACHE_FILE = Path(__file__).parent / "mip_label_cache.json"

@dataclass
class ClassifierConfig:
    keyword_map: Dict[str, ClassificationLevel] = field(
        default_factory=lambda: dict(DEFAULT_KEYWORD_MAP)
    )
    keyword_search_order: List[str] = field(
        default_factory=list, init=False
    )
    enable_ocr: bool = True
    ocr_dpi: int = 150
    ocr_max_pages: int = 3
    mip_label_cache: Dict[str, ClassificationLevel] = field(
        default_factory=lambda: _load_mip_label_cache(_DEFAULT_CACHE_FILE)
    )
    mip_label_cache_file: Path = field(
        default=_DEFAULT_CACHE_FILE, repr=False
    )
    content_marking_properties: List[str] = field(
        default_factory=lambda: list(DEFAULT_CONTENT_MARKING_PROPERTIES)
    )
    ocr_file_size_limit: int = 100 * 1024 * 1024
    escalate_on_conflict: bool = True

    def __post_init__(self) -> None:
        self.keyword_search_order = sorted(
            self.keyword_map.keys(),
            key=lambda k: (-len(k), k)
        )