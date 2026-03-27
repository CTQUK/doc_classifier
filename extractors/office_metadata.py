from __future__ import annotations
import logging
import re
from typing import Dict, Set
from zipfile import ZipFile, BadZipFile

from lxml import etree

from doc_classifier.config import ClassifierConfig, ClassificationLevel
from doc_classifier.extractors.base import BaseExtractor
from doc_classifier.models import ExtractionHit, ExtractionResult
from doc_classifier.utils import scan_text_for_keywords

logger = logging.getLogger(__name__)

_NS_CUSTOM = "http://schemas.openxmlformats.org/officeDocument/2006/custom-properties"
_NS_VT = "http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"
_NS = {"cp": _NS_CUSTOM, "vt": _NS_VT}

_MSIP_RE = re.compile(
    r"^MSIP_Label_([0-9a-fA-F\-]+)_(Name|Enabled|Method|SiteId|SetDate|ContentBits|ActionId|Tag)$"
)

_GUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)

# OLE2 Compound Document magic bytes (encrypted Office files)
OLE2_MAGIC = b"\xd0\xcf\x11\xe0"


class OfficeMetadataExtractor(BaseExtractor):

    def __init__(self, config: ClassifierConfig) -> None:
        super().__init__(config)

    @property
    def name(self) -> str:
        return "office_metadata"

    @property
    def supported_groups(self) -> Set[str]:
        return {"office"}

    def extract(self, filepath: str) -> ExtractionResult:
        result = ExtractionResult(extractor_name=self.name)

        # Check if file is encrypted (OLE2 / RMS Protected)
        if self._is_encrypted(filepath):
            result.raw_metadata["encrypted"] = True
            result.raw_metadata["encryption_type"] = "OLE2/RMS"
            # In Bayer tenant, encrypted files = SECRET (Protected)
            result.hits.append(
                ExtractionHit(
                    source="encrypted_file_detection",
                    field_name="file_format",
                    raw_value="OLE2/RMS encrypted file detected",
                    matched_keyword="SECRET",
                    level=ClassificationLevel.SECRET,
                    confidence=0.85,
                    metadata={
                        "note": "File is RMS encrypted. Encrypted = SECRET (Protected)."
                    },
                )
            )
            return result

        # Read metadata from OOXML package
        try:
            custom_props = self._read_custom_properties(filepath)
            core_props = self._read_core_properties(filepath)
        except (BadZipFile, Exception) as exc:
            result.errors.append(f"Failed to open OOXML package: {exc}")
            return result

        result.raw_metadata = {
            "custom_properties": custom_props,
            "core_properties": core_props,
        }

        # 1. Content Marking Properties (most reliable)
        for prop_name in self.config.content_marking_properties:
            if prop_name in custom_props:
                marking_text = custom_props[prop_name]
                result.raw_metadata[f"content_marking:{prop_name}"] = marking_text
                hits = scan_text_for_keywords(
                    text=marking_text,
                    config=self.config,
                    source="content_marking",
                    field_name=prop_name,
                    confidence=1.0,
                )
                result.hits.extend(hits)

        # 2. MSIP Labels
        msip_groups = self._group_msip_labels(custom_props)
        for label_id, fields in msip_groups.items():
            label_name = fields.get("Name", "")
            enabled = fields.get("Enabled", "").lower() == "true"

            if not enabled:
                continue

            resolved = None

            if _GUID_RE.match(label_name):
                resolved = self.config.mip_label_cache.get(label_name)
                if not resolved:
                    resolved = self.config.mip_label_cache.get(label_id)
                if resolved:
                    logger.info("Resolved GUID %s to %s", label_name, resolved)
                else:
                    result.raw_metadata.setdefault("unresolved_guids", []).append({
                        "label_id": label_id,
                        "name_value": label_name,
                    })
                    logger.warning("MSIP GUID %s not in mip_label_cache.", label_name)
            else:
                resolved = label_name  # plain text like "SECRET"

            if resolved is None:
                continue

            # If cache returned a ClassificationLevel enum, create hit directly
            if isinstance(resolved, ClassificationLevel):
                result.hits.append(ExtractionHit(
                    source="msip_label",
                    field_name=f"MSIP_Label_{label_id}_Name",
                    raw_value=label_name,
                    matched_keyword=str(resolved.name),
                    level=resolved,
                    confidence=1.0,
                ))
            else:
                # Plain text label name — scan against keywords
                hits = scan_text_for_keywords(
                    text=resolved,
                    config=self.config,
                    source="msip_label",
                    field_name=f"MSIP_Label_{label_id}_Name",
                )
                result.hits.extend(hits)
                if not hits:
                    result.raw_metadata.setdefault("unmatched_labels", []).append({
                        "label_id": label_id,
                        "resolved_name": resolved,
                    })

        # 3. Non-MSIP custom properties
        skip_props = set(self.config.content_marking_properties)
        for key, val in custom_props.items():
            if key in skip_props:
                continue
            if not _MSIP_RE.match(key) and val:
                hits = scan_text_for_keywords(
                    text=val,
                    config=self.config,
                    source="office_custom_property",
                    field_name=key,
                )
                result.hits.extend(hits)

        # 4. Core properties
        for key, val in core_props.items():
            if val:
                hits = scan_text_for_keywords(
                    text=val,
                    config=self.config,
                    source="office_core_property",
                    field_name=key,
                )
                result.hits.extend(hits)

        return result

    @staticmethod
    def _is_encrypted(filepath: str) -> bool:
        try:
            with open(filepath, "rb") as f:
                magic = f.read(4)
            return magic == OLE2_MAGIC
        except Exception:
            return False

    @staticmethod
    def _read_custom_properties(filepath: str) -> Dict[str, str]:
        props = {}
        try:
            with ZipFile(filepath, "r") as zf:
                if "docProps/custom.xml" not in zf.namelist():
                    return props
                raw = zf.read("docProps/custom.xml")
                root = etree.fromstring(raw)
                for prop in root.findall("cp:property", _NS):
                    pname = prop.get("name", "")
                    for child in prop:
                        if child.text:
                            props[pname] = child.text.strip()
                            break
        except Exception as exc:
            logger.warning("Could not read custom properties: %s", exc)
        return props

    @staticmethod
    def _read_core_properties(filepath: str) -> Dict[str, str]:
        props = {}
        ns_core = {
            "cp": "http://schemas.openxmlformats.org/package/2006/metadata/core-properties",
            "dc": "http://purl.org/dc/elements/1.1/",
            "dcterms": "http://purl.org/dc/terms/",
        }
        try:
            with ZipFile(filepath, "r") as zf:
                if "docProps/core.xml" not in zf.namelist():
                    return props
                raw = zf.read("docProps/core.xml")
                root = etree.fromstring(raw)
                fields = [
                    ("dc:subject", "subject"),
                    ("dc:description", "description"),
                    ("dc:title", "title"),
                    ("cp:keywords", "keywords"),
                    ("cp:category", "category"),
                ]
                for xpath, key in fields:
                    el = root.find(xpath, ns_core)
                    if el is not None and el.text:
                        props[key] = el.text.strip()
        except Exception as exc:
            logger.warning("Could not read core properties: %s", exc)
        return props

    @staticmethod
    def _group_msip_labels(props: Dict[str, str]) -> Dict[str, Dict[str, str]]:
        groups = {}
        for key, val in props.items():
            m = _MSIP_RE.match(key)
            if m:
                guid = m.group(1)
                field_name = m.group(2)
                groups.setdefault(guid, {})[field_name] = val
        return groups
