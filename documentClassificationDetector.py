"""
Document Classification Detection
============================
A realistic implementation showing how to integrate the
document classifier into an actual document processing pipeline.

This example demonstrates:
  1. Configuration from environment / config file
  2. Batch processing with progress tracking
  3. Routing decisions based on classification
  4. Audit logging
  5. Error handling and reporting
  6. JSON + CSV export
"""

import csv
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
"""
from doc_classifier import (
    DocumentClassifier,
    ClassifierConfig,
    ClassificationLevel,
    ClassificationReport,
)
"""
from config import ClassifierConfig, ClassificationLevel
from classifier import DocumentClassifier
from exceptions import DocClassifierError
from models import ClassificationReport


# ======================================================================
# 1. CONFIGURATION
# ======================================================================

class PipelineConfig:

    # Input
    INPUT_DIR = Path("test_documents")
    # INPUT_DIR = Path("C:\\Users\\CTQUK\\OneDrive - Bayer\\Personal Data")

    # Output
    OUTPUT_DIR = Path("pipeline_output")
    AUDIT_LOG_FILE = OUTPUT_DIR / "audit_log.json"
    SUMMARY_CSV = OUTPUT_DIR / "classification_summary.csv"
    DETAILED_JSON = OUTPUT_DIR / "detailed_results.json"

    # Routing destinations
    STORAGE_TIERS = {
        "classified-vault":    OUTPUT_DIR / "routed" / "secret",
        "restricted-store":    OUTPUT_DIR / "routed" / "restricted",
        "internal-store":      OUTPUT_DIR / "routed" / "internal",
        "none-store":          OUTPUT_DIR / "routed" / "none",
        "general-store":       OUTPUT_DIR / "routed" / "general",
    }

    # Classification -> Routing Rules
    ROUTING_RULES = {
        ClassificationLevel.SECRET: {
            "storage_tier": "classified-vault",
            "encrypt": True,
            "audit": True,
            "notify": ["security-team@company.com"],
            "access_group": "secret-cleared",
            "retention_years": 7,
            "action": "ROUTE_SECURE",
        },
        ClassificationLevel.RESTRICTED: {
            "storage_tier": "restricted-store",
            "encrypt": True,
            "audit": True,
            "notify": [],
            "access_group": "restricted-team",
            "retention_years": 3,
            "action": "ROUTE_RESTRICTED",
        },
        ClassificationLevel.INTERNAL: {
            "storage_tier": "internal-store",
            "encrypt": False,
            "audit": False,
            "notify": [],
            "access_group": "all-employees",
            "retention_years": 2,
            "action": "ROUTE_INTERNAL",
        },
        ClassificationLevel.NONE: {
            "storage_tier": "none-store",
            "encrypt": False,
            "audit": True,
            "notify": ["compliance-team@company.com"],
            "access_group": "all-employees",
            "retention_years": 1,
            "action": "ROUTE_NONE",
        },
    }

    DEFAULT_ROUTING = {
        "storage_tier": "general-store",
        "encrypt": False,
        "audit": False,
        "notify": [],
        "access_group": "public",
        "retention_years": 1,
        "action": "ROUTE_GENERAL",
    }


# ======================================================================
# 2. AUDIT LOGGER
# ======================================================================

class AuditLogger:

    def __init__(self, log_file: Path):
        self.log_file = log_file
        self.entries: List[Dict] = []

    def log(
        self,
        filepath: str,
        classification: str,
        level_value: int,
        action: str,
        storage_tier: str,
        hit_count: int,
        sources: List[str],
        processing_ms: float,
    ):
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "filepath": filepath,
            "filename": os.path.basename(filepath),
            "classification": classification,
            "level_value": level_value,
            "action": action,
            "storage_tier": storage_tier,
            "hit_count": hit_count,
            "detection_sources": sources,
            "processing_ms": round(processing_ms, 2),
        }
        self.entries.append(entry)

    def save(self):
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_file, "w", encoding="utf-8") as f:
            json.dump(self.entries, f, indent=2)


# ======================================================================
# 3. DOCUMENT ROUTER
# ======================================================================

class DocumentRouter:

    def __init__(self, config: PipelineConfig):
        self.config = config
        for tier_path in config.STORAGE_TIERS.values():
            tier_path.mkdir(parents=True, exist_ok=True)

    def route(self, filepath: str, report: ClassificationReport) -> Dict:
        rules = self.config.ROUTING_RULES.get(
            report.detected_level,
            self.config.DEFAULT_ROUTING,
        )

        tier_name = rules["storage_tier"]
        destination = self.config.STORAGE_TIERS.get(tier_name)

        result = {
            "filepath": filepath,
            "filename": os.path.basename(filepath),
            "classification": report.detected_label,
            "level": report.detected_level.name,
            "level_value": int(report.detected_level),
            "routing": {
                "action": rules["action"],
                "storage_tier": tier_name,
                "destination": str(destination),
                "encrypt": rules["encrypt"],
                "audit_required": rules["audit"],
                "access_group": rules["access_group"],
                "retention_years": rules["retention_years"],
            },
            "detection": {
                "hit_count": len(report.all_hits),
                "sources": list(set(h.source for h in report.all_hits)),
                "highest_confidence": max(
                    (h.confidence for h in report.all_hits), default=0
                ),
            },
            "processing_ms": round(report.processing_time_ms, 2),
        }

        if rules["action"] == "ROUTE_SECURE":
            result["routing"]["blocked"] = False

        if rules["notify"]:
            result["routing"]["notifications"] = rules["notify"]

        return result


# ======================================================================
# 4. PIPELINE ORCHESTRATOR
# ======================================================================

class DocumentPipeline:

    def __init__(self):
        self.pipeline_config = PipelineConfig()

        # Classifier uses defaults from config.py which now
        # includes BAYER_LABEL_CACHE automatically
        classifier_config = ClassifierConfig(
            enable_ocr=False,
            escalate_on_conflict=True,
        )

        self.classifier = DocumentClassifier(config=classifier_config)
        self.router = DocumentRouter(self.pipeline_config)
        self.audit = AuditLogger(self.pipeline_config.AUDIT_LOG_FILE)

        self.results: List[Dict] = []
        self.errors: List[Dict] = []

    def process_file(self, filepath: str) -> Optional[Dict]:
        try:
            report = self.classifier.classify(filepath)
            routing_result = self.router.route(filepath, report)

            self.audit.log(
                filepath=filepath,
                classification=report.detected_label,
                level_value=int(report.detected_level),
                action=routing_result["routing"]["action"],
                storage_tier=routing_result["routing"]["storage_tier"],
                hit_count=len(report.all_hits),
                sources=list(set(h.source for h in report.all_hits)),
                processing_ms=report.processing_time_ms,
            )

            self.results.append(routing_result)
            return routing_result

        except DocClassifierError as e:
            error_entry = {
                "filepath": filepath,
                "error": str(e),
                "error_type": type(e).__name__,
            }
            self.errors.append(error_entry)
            return None

    def process_directory(self, input_dir: Path) -> None:
        supported_extensions = {
            ".docx", ".xlsx", ".pptx", ".pdf",
            ".png", ".jpg", ".jpeg", ".tiff",
        }

        files = sorted([
            f for f in input_dir.iterdir()
            if f.is_file() and f.suffix.lower() in supported_extensions
        ])

        print(f"\n  Found {len(files)} supported files\n")

        for i, filepath in enumerate(files, 1):
            filename = filepath.name
            result = self.process_file(str(filepath))

            if result:
                level = result["classification"]
                action = result["routing"]["action"]
                tier = result["routing"]["storage_tier"]
                ms = result["processing_ms"]

                icon_map = {
                    "ROUTE_SECURE": "🔒",
                    "ROUTE_RESTRICTED": "🟡",
                    "ROUTE_INTERNAL": "🔵",
                    "ROUTE_NONE": "⬜",
                    "ROUTE_GENERAL": "✅",
                    "ROUTE_UNCLASSIFIED": "✅",
                }
                icon = icon_map.get(action, "📄")

                print(
                    f"  [{i:2d}/{len(files)}] {icon} {filename:<40} "
                    f"{level:<15} -> {tier:<25} ({ms:.0f}ms)"
                )
            else:
                print(f"  [{i:2d}/{len(files)}] ⚠️  {filename:<40} ERROR")

    def export_results(self) -> None:
        output_dir = self.pipeline_config.OUTPUT_DIR
        output_dir.mkdir(parents=True, exist_ok=True)

        json_path = self.pipeline_config.DETAILED_JSON
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(
                {"results": self.results, "errors": self.errors},
                f, indent=2,
            )

        csv_path = self.pipeline_config.SUMMARY_CSV
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Filename", "Classification", "Level Value",
                "Action", "Storage Tier", "Encrypt",
                "Access Group", "Hit Count", "Sources",
                "Processing (ms)",
            ])
            for r in self.results:
                writer.writerow([
                    r["filename"],
                    r["classification"],
                    r["level_value"],
                    r["routing"]["action"],
                    r["routing"]["storage_tier"],
                    r["routing"]["encrypt"],
                    r["routing"]["access_group"],
                    r["detection"]["hit_count"],
                    "; ".join(r["detection"]["sources"]),
                    r["processing_ms"],
                ])

        self.audit.save()

        print(f"\n  Output directory : {output_dir.resolve()}")
        print(f"  Detailed JSON    : {json_path.name}")
        print(f"  Summary CSV      : {csv_path.name}")
        print(f"  Audit log        : {self.pipeline_config.AUDIT_LOG_FILE.name}")

    def print_summary(self) -> None:
        from collections import Counter

        level_counts = Counter(r["classification"] for r in self.results)
        tier_counts = Counter(r["routing"]["storage_tier"] for r in self.results)
        action_counts = Counter(r["routing"]["action"] for r in self.results)

        total = len(self.results)
        classified = sum(1 for r in self.results if r["level_value"] > 5)
        none_count = sum(1 for r in self.results if r["level_value"] == 5)
        unknown_count = sum(1 for r in self.results if r["level_value"] == 0)
        needs_encryption = sum(
            1 for r in self.results if r["routing"]["encrypt"]
        )

        print(f"\n  {'=' * 60}")
        print(f"  PIPELINE SUMMARY")
        print(f"  {'=' * 60}")

        print(f"\n  Overview:")
        print(f"    Total processed    : {total}")
        print(f"    Classified         : {classified}")
        print(f"    None (unlabeled)   : {none_count}")
        print(f"    Unknown (no data)  : {unknown_count}")
        print(f"    Errors             : {len(self.errors)}")
        print(f"    Need encryption    : {needs_encryption}")

        print(f"\n  By Classification Level:")
        for level_name, count in sorted(level_counts.items()):
            bar = chr(9608) * count
            print(f"    {level_name:<20} {count:>3}  {bar}")

        print(f"\n  By Storage Tier:")
        for tier, count in sorted(tier_counts.items()):
            print(f"    {tier:<25} {count:>3}")

        print(f"\n  By Action:")
        for action, count in sorted(action_counts.items()):
            print(f"    {action:<25} {count:>3}")

        if self.errors:
            print(f"\n  Errors:")
            for err in self.errors:
                print(f"    {err['filepath']}: {err['error']}")

        # Show MIP label cache info
        print(f"\n  {'─' * 60}")
        
        """
        print(f"  MIP Label Cache (from config.py):")
        from doc_classifier.config import DEFAULT_MIP_LABEL_CACHE
        for guid, name in DEFAULT_MIP_LABEL_CACHE.items():
            short_guid = guid[:8] + "..."
            print(f"    {short_guid:<15} -> {name}")
        """
        # NEW - reads from the live config instead
        print(f"\n  MIP Label Cache:")
        for guid, level in self.classifier.config.mip_label_cache.items():
            short_guid = guid[:8] + "..."
            level_name = level.name if hasattr(level, 'name') else str(level)
            print(f"    {short_guid:<15} -> {level_name}")
        
        print(f"\n  {'=' * 60}")


# ======================================================================
# 5. MAIN
# ======================================================================

def main():
    print("=" * 70)
    print("  DOCUMENT CLASSIFICATION PIPELINE")
    print("  Document Classification Automation Detection Project")
    print("=" * 70)

    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)s: %(message)s",
    )

    pipeline = DocumentPipeline()

    # Show config
    config = pipeline.classifier.config
    print(f"\n  Configuration:")
    print(f"    MIP Label Cache  : {len(config.mip_label_cache)} GUIDs mapped")
    print(f"    Keywords         : {len(config.keyword_map)} defined")
    print(f"    OCR              : {'Enabled' if config.enable_ocr else 'Disabled'}")
    print(f"    Escalate         : {config.escalate_on_conflict}")

    input_dir = Path("test_documents")
    # input_dir = Path("C:\\Users\\CTQUK\\OneDrive - Bayer\\Personal Data")
    if not input_dir.exists():
        print(f"\n  Input directory not found: {input_dir}")
        return

    print(f"\n  Input: {input_dir.resolve()}")

    pipeline.process_directory(input_dir)

    print(f"\n{'─' * 70}")
    print(f"  EXPORTING RESULTS")
    print(f"{'─' * 70}")
    pipeline.export_results()

    pipeline.print_summary()


if __name__ == "__main__":
    main()