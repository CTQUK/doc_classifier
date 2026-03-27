from __future__ import annotations
import mimetypes
import os
from pathlib import Path
from typing import List, Optional

from config import ClassifierConfig
from models import ExtractionHit


FORMAT_GROUPS = {
    "office": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/vnd.ms-excel",
        "application/vnd.ms-powerpoint",
        "application/msword",
    },
    "pdf": {
        "application/pdf",
    },
    "image": {
        "image/png",
        "image/jpeg",
        "image/tiff",
        "image/bmp",
    },
}

EXT_GROUP = {
    ".docx": "office", ".xlsx": "office", ".pptx": "office",
    ".doc": "office", ".xls": "office", ".ppt": "office",
    ".pdf": "pdf",
    ".png": "image", ".jpg": "image", ".jpeg": "image",
    ".tiff": "image", ".tif": "image", ".bmp": "image",
}


def detect_format_group(filepath: str) -> str:
    mime, _ = mimetypes.guess_type(filepath)
    if mime:
        for group, mimes in FORMAT_GROUPS.items():
            if mime in mimes:
                return group
    ext = Path(filepath).suffix.lower()
    return EXT_GROUP.get(ext, "unknown")


def get_office_subtype(filepath: str) -> str:
    ext = Path(filepath).suffix.lower()
    mapping = {
        ".docx": "docx", ".doc": "docx",
        ".xlsx": "xlsx", ".xls": "xlsx",
        ".pptx": "pptx", ".ppt": "pptx",
    }
    return mapping.get(ext, "unknown")


def scan_text_for_keywords(
    text: str,
    config: ClassifierConfig,
    source: str,
    field_name: str = "",
    page: Optional[int] = None,
    confidence: float = 1.0,
) -> List[ExtractionHit]:
    upper = text.upper()
    hits: List[ExtractionHit] = []
    seen: set = set()

    for keyword in config.keyword_search_order:
        if keyword in upper and keyword not in seen:
            seen.add(keyword)
            hits.append(
                ExtractionHit(
                    source=source,
                    field_name=field_name,
                    raw_value=text[:200],
                    matched_keyword=keyword,
                    level=config.keyword_map[keyword],
                    page=page,
                    confidence=confidence,
                )
            )
    return hits


def validate_file(filepath: str) -> None:
    from exceptions import FileAccessError
    if not os.path.isfile(filepath):
        raise FileAccessError(f"File not found: {filepath}")
    if not os.access(filepath, os.R_OK):
        raise FileAccessError(f"File not readable: {filepath}")
