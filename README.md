# Document Classification Detector — Technical Guide

**Version:** 1.0.0
**Last Updated:** 2026-03-23
**Author:** BTH Development Team

---

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture](#2-architecture)
3. [System Requirements](#3-system-requirements)
4. [Installation](#4-installation)

---

## 1. Overview

### 1.1 Purpose

The Document Classification Detector is a Python-based pre-processing
module designed to automatically detect document classification levels
(e.g., Secret, Restricted, Internal, No Classification, None) from multiple sources:

- **Microsoft Information Protection (MIP) Sensitivity Labels**
- **Office Document Properties** (core and custom)
- **PDF XMP Metadata and Info Dictionary**
- **Visible Watermarks** (VML, DrawingML, text-layer)
- **OCR** (optional, for scanned documents)

### 1.2 Key Features

| Feature                    | Description                                    |
|----------------------------|------------------------------------------------|
| Multi-source detection     | Checks labels, metadata, watermarks, and OCR   |
| Plugin architecture        | Add new formats without modifying core code     |
| Conflict resolution        | Escalates to highest classification found       |
| Full audit trail           | Every hit tracked with source and confidence    |
| JSON export                | Machine-readable output for pipeline integration|
| Configurable keywords      | Organisation-specific classification terms      |
| MIP label GUID cache       | Resolve Purview label GUIDs without API calls   |

### 1.3 Supported File Formats

| Format | Extensions          | Extractors Used                          |
|--------|---------------------|------------------------------------------|
| Office | .docx, .xlsx, .pptx | office_metadata, office_watermark        |
| PDF    | .pdf                | pdf_metadata, pdf_watermark, image_ocr   |
| Image  | .png, .jpg, .tiff   | image_ocr                                |


### 1.4 Project Structure

```text
doc_classifier/ (pip install -e: This makes `doc_classifier` importable from anywhere.)
│
├── pyproject.toml
├── requirements.txt
├── TECHNICAL_GUIDE.md
│
├── __init__.py            (← REQUIRED)
├── config.py              # Classification levels & settings
├── models.py              # Data models (dataclasses)
├── exceptions.py          # Custom exceptions
├── utils.py               # File-type routing, helpers
├── reconciler.py          # Conflict resolution logic
├── classifier.py          # Main orchestrator (entry point)
│
└── extractors/
    ├── __init__.py        (← REQUIRED)
    ├── base.py            # Abstract base extractor
    ├── registry.py        # Auto-discovery plugin registry
    ├── office_metadata.py # MSIP / custom properties
    ├── office_watermark.py# Word/PPT visible watermarks
    ├── pdf_metadata.py    # XMP + Info dict
    ├── pdf_watermark.py   # Text-layer + OCR watermark
    └── image_ocr.py       # Standalone image files
└── pipeline_output/       # output the results here. You can setup an output folder in file  documentClassificationDetector.py
│                          # for running the automation.
│
test_documents             # this is input testing documents. You can setup an input folder in file documentClassificationDetector.py
                           # for running the automation.


## 2. Architecture

### 2.1 High-Level Architecture
                 ┌──────────────────────┐
                 │  DocumentClassifier   │  ← Single entry point
                 │  .classify(filepath)  │
                 └──────────┬───────────┘
                            │
                 ┌──────────▼───────────┐
                 │   validate_file()     │
                 │   detect_format_group │
                 └──────────┬───────────┘
                            │
                 ┌──────────▼───────────┐
                 │  ExtractorRegistry    │
                 │  .get_extractors(fmt) │
                 └──┬───┬───┬───┬───┬───┘
                    │   │   │   │   │
          ┌─────────┘   │   │   │   └─────────┐
          ▼             ▼   ▼   ▼             ▼
    ┌──────────┐  ┌─────┐ ┌────┐ ┌─────┐  ┌──────┐
    │  Office  │  │ Off │ │PDF │ │ PDF │  │ OCR  │
    │ Metadata │  │Water│ │Meta│ │Water│  │Image │
    └────┬─────┘  └──┬──┘ └─┬──┘ └──┬──┘  └──┬───┘
         │            │      │       │        │
         └────────────┴──────┴───────┴────────┘
                            │
                 ┌──────────▼───────────┐
                 │     Reconciler        │
                 │  (highest level wins) │
                 └──────────┬───────────┘
                            │
                 ┌──────────▼───────────┐
                 │ ClassificationReport  │
                 │  .to_dict() / .level  │
                 └──────────────────────┘

### 2.2 Component Interaction

┌─────────────┐ ┌──────────────┐ ┌────────────────┐ │ Classifier │────▶│ Registry │────▶│ Extractors │ │ (entry pt) │ │ (plugin mgr)│ │ (5 built-in) │ └──────┬───────┘ └──────────────┘ └───────┬────────┘ │ │ │ ┌──────────────┐ │ └────────▶│ Reconciler │◀────────────────┘ │ (resolver) │ └──────┬───────┘ │ ┌──────▼───────┐ │ Report │ │ (output) │ └──────────────┘


### 2.3 Design Patterns Used

| Pattern            | Where                  | Why                              |
|--------------------|------------------------|----------------------------------|
| Strategy           | BaseExtractor          | Swappable extraction algorithms  |
| Registry/Plugin    | ExtractorRegistry      | Add formats without core changes |
| Builder            | ClassifierConfig       | Flexible configuration           |
| Data Transfer Obj  | ExtractionHit/Report   | Clean data boundaries            |
| Template Method    | BaseExtractor.extract  | Consistent extractor interface   |

---

## 3. System Requirements

### 3.1 Software Requirements

| Component       | Minimum Version | Required/Optional |
|-----------------|-----------------|-------------------|
| Python          | 3.10+           | Required          |
| pip             | 22.0+           | Required          |
| Tesseract OCR   | 5.0+            | Optional (OCR)    |
| Poppler         | 22.0+           | Optional (OCR)    |

### 3.2 Python Dependencies

| Package       | Version   | Purpose                              |
|---------------|-----------|--------------------------------------|
| python-docx   | >=1.1.0   | Read .docx structure                 |
| openpyxl      | >=3.1.2   | Read .xlsx structure                 |
| python-pptx   | >=0.6.23  | Read .pptx structure                 |
| pikepdf       | >=8.0.0   | PDF metadata (XMP + Info dict)       |
| pdfplumber    | >=0.10.0  | PDF text layer extraction            |
| lxml          | >=4.9.0   | XML parsing for all formats          |
| Pillow        | >=10.0.0  | Image handling                       |
| pdf2image     | >=1.16.3  | PDF to image conversion (OCR)        |
| pytesseract   | >=0.3.10  | OCR text recognition                 |

---

## 4. Installation

### 4.1 Standard Installation

```bash

# 1. Clone or copy the project
cd /path/to/your/projects
mkdir doc_classifier
cd doc_classifier

# 2. Create virtual environment
python -m venv .venv

# 3. Activate virtual environment
# Windows PowerShell:
.\\.venv\\Scripts\\Activate.ps1
# Windows CMD:
.\\.venv\\Scripts\\activate.bat
# Linux/macOS:
source .venv/bin/activate

# 4. Upgrade pip
python -m pip install --upgrade pip

# 5. Install dependencies
pip install -r requirements.txt

# 6. Verify installation
python -c "from doc_classifier import DocumentClassifier; print('OK')"

# 7. Run (powershell)
python createAllFiles.py # Create all python files
python documentClassificationDetector.py # Test and check the results in folder pipeline_output


### 4.2 How to define classification levels and Keywords

class ClassificationLevel(IntEnum): Just an example
    NONE          = 20
    INTERNAL      = 40
    RESTRICTED    = 60
    SECRET        = 90


DEFAULT_KEYWORD_MAP = {
    "SECRET":        ClassificationLevel.SECRET,
    "RESTRICTED":    ClassificationLevel.RESTRICTED,
    "INTERNAL":      ClassificationLevel.INTERNAL,
    "NO CLASSIFICATION":          ClassificationLevel.NONE,
}

### 4.3 How to Add MIP Label GUIDs
Find your label GUIDs in Microsoft Purview Compliance Portal → Information Protection → Labels, then:

(Recommend to keep MIP GUIDs in local file)

DEFAULT_MIP_LABEL_CACHE = {
    "xxx: "INTERNAL",
    "xxx": "NONE",
    "xxx": "RESTRICTED",
    "xxx": "SECRET",
}

DEFAULT_CONTENT_MARKING_PROPERTIES = [
    "ClassificationContentMarkingFooterText",
    "ClassificationContentMarkingHeaderText",
    "ClassificationContentMarkingWatermarkText",
]


### 4.4 Troubleshooting
| Problem                          | Cause                               | Solution                                                              |
|----------------------------------|-------------------------------------|-----------------------------------------------------------------------|
| UnsupportedFormatError           | File type not supported (.txt, .csv, etc.) | Only .docx/.xlsx/.pptx/.pdf are supported                             |
| FileAccessError                  | File not found or locked           | Check path, close file in other apps                                  |
| UNKNOWN for a labeled doc        | Label GUID not in cache            | Add GUID to `mip_label_cache` in config                               |
| OCR errors (Poppler)             | Poppler not installed              | Install Poppler or set `enable_ocr=False`                             |
| Slow processing                  | OCR running on large PDFs          | Set `enable_ocr=False` or reduce `ocr_max_pages`                      |
| Wrong classification             | Keyword in unrelated text          | Review hits in report, adjust `keyword_map`                           |

---
