from __future__ import annotations
import logging
import re
from typing import Set

from lxml import etree

from extractors.base import BaseExtractor
from models import ExtractionResult, ExtractionHit
from utils import scan_text_for_keywords

logger = logging.getLogger(__name__)

MIP_PATTERN = re.compile(r"MSIP_Label_([0-9a-fA-F\-]+)_Name", re.IGNORECASE)


class PdfMetadataExtractor(BaseExtractor):

    @property
    def name(self) -> str:
        return "pdf_metadata"

    @property
    def supported_groups(self) -> Set[str]:
        return {"pdf"}

    def extract(self, filepath: str) -> ExtractionResult:
        result = ExtractionResult(extractor_name=self.name)

        try:
            import pikepdf
        except ImportError:
            result.errors.append("pikepdf not installed")
            return result

        try:
            with pikepdf.open(filepath) as pdf:
                self._extract_info_dict(pdf, result)
                if not result.hits:  # only parse XMP if info dict gave nothing
                    self._extract_xmp(pdf, result)
        except Exception as exc:
            result.errors.append(f"PDF metadata extraction failed: {exc}")

        return result

    def _match_mip_guid(self, guid: str, label_name: str, field_name: str, result: ExtractionResult) -> bool:
        """Try to match a MIP GUID against the cache. Returns True if matched."""
        if self.config.mip_label_cache:
            for cache_guid, level in self.config.mip_label_cache.items():
                if cache_guid.lower().replace("-", "") == guid.lower().replace("-", ""):
                    result.hits.append(ExtractionHit(
                        source="mip_label_guid",
                        field_name=field_name,
                        raw_value=guid,
                        matched_keyword=cache_guid,
                        level=level,
                        confidence=1.0,
                    ))
                    logger.debug("MIP GUID matched -> %s", level)
                    return True

        # Fallback: keyword scan on label name text
        if label_name:
            hits = scan_text_for_keywords(
                text=label_name, config=self.config,
                source="mip_label_name", field_name=field_name,
                confidence=0.95,
            )
            result.hits.extend(hits)

        return False
    def _extract_info_dict(self, pdf, result):
        """Extract standard fields AND MIP labels from the PDF info dict."""
        info = pdf.docinfo

        for field in info.keys():
            val = str(info[field]).strip()
            if not val:
                continue

            field_str = str(field)

            # Check for MIP label key e.g. /MSIP_Label_<GUID>_Name
            match = MIP_PATTERN.search(field_str)
            if match:
                guid = match.group(1)
                result.raw_metadata["mip_label_guid"] = guid
                result.raw_metadata["mip_label_name"] = val
                logger.debug("MIP label in info dict: GUID=%s Name=%s", guid, val)
                matched = self._match_mip_guid(guid, val, field_str, result)
                if matched:
                    return  # Definitive match, no need to continue

            # Standard fields
            elif field_str in ["/Title", "/Subject", "/Keywords", "/Author", "/Creator", "/Producer"]:
                result.raw_metadata[f"info{field_str}"] = val
                hits = scan_text_for_keywords(
                    text=val, config=self.config,
                    source="pdf_info_dict", field_name=field_str,
                )
                result.hits.extend(hits)

    def _extract_xmp(self, pdf, result):
        try:
            with pdf.open_metadata() as meta:
                for field in ["dc:description", "dc:subject", "dc:title", "pdf:Keywords", "xmp:Label"]:
                    try:
                        val = meta.get(field)
                        if val:
                            val_str = str(val)
                            result.raw_metadata[f"xmp:{field}"] = val_str
                            hits = scan_text_for_keywords(
                                text=val_str, config=self.config,
                                source="pdf_xmp", field_name=field,
                            )
                            result.hits.extend(hits)
                    except Exception:
                        pass
        except Exception:
            pass

        self._parse_raw_xmp(pdf, result)
        self._parse_mip_labels(pdf, result)

    def _parse_raw_xmp(self, pdf, result):
        try:
            metadata_stream = pdf.Root.get("/Metadata")
            if metadata_stream is None:
                return
            xmp_bytes = bytes(metadata_stream.read_bytes())
            root = etree.fromstring(xmp_bytes)
            custom_tags = ["classification", "sensitivity", "securitylabel", "marking"]
            for elem in root.iter():
                tag_local = etree.QName(elem.tag).localname.lower()
                text = (elem.text or "").strip()
                if text and any(ct in tag_local for ct in custom_tags):
                    result.raw_metadata[f"xmp_custom:{elem.tag}"] = text
                    hits = scan_text_for_keywords(
                        text=text, config=self.config,
                        source="pdf_xmp_custom", field_name=elem.tag,
                    )
                    result.hits.extend(hits)
        except Exception as exc:
            logger.debug("Raw XMP parsing skipped: %s", exc)

    def _parse_mip_labels(self, pdf, result):
        """Extract MIP labels from XMP metadata (Office-generated PDFs)."""
        try:
            metadata_stream = pdf.Root.get("/Metadata")
            if metadata_stream is None:
                return

            xmp_bytes = bytes(metadata_stream.read_bytes())
            root = etree.fromstring(xmp_bytes)

            for elem in root.iter():
                for attr_name, attr_value in elem.attrib.items():
                    local = etree.QName(attr_name).localname if "{" in attr_name else attr_name
                    match = MIP_PATTERN.search(local)
                    if match:
                        guid = match.group(1)
                        label_name = attr_value.strip()
                        result.raw_metadata["mip_label_guid"] = guid
                        result.raw_metadata["mip_label_name"] = label_name
                        logger.debug("MIP label in XMP: GUID=%s Name=%s", guid, label_name)
                        matched = self._match_mip_guid(guid, label_name, "MSIP_Label_Name", result)
                        if matched:
                            return

        except Exception as exc:
            logger.debug("MIP label XMP parsing skipped: %s", exc)