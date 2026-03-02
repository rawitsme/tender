"""PDF text extraction with OCR fallback.

Strategy:
1. Try pdfplumber for text extraction (fast, works for digital PDFs)
2. If text is too short/empty, fall back to Tesseract OCR via pdf2image
3. Return extracted text + metadata
"""

import logging
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


def extract_text_from_pdf(file_path: str | Path) -> Tuple[str, float]:
    """Extract text from a PDF file.
    
    Returns: (extracted_text, confidence_score)
    confidence_score: 1.0 for digital PDFs, 0.5-0.8 for OCR'd
    """
    file_path = Path(file_path)
    if not file_path.exists():
        logger.error(f"PDF not found: {file_path}")
        return "", 0.0

    # Step 1: Try pdfplumber (digital PDFs)
    text = _extract_with_pdfplumber(file_path)
    
    if text and len(text.strip()) > 100:
        logger.info(f"Extracted {len(text)} chars via pdfplumber from {file_path.name}")
        return text, 1.0

    # Step 2: Fallback to OCR
    logger.info(f"pdfplumber extracted little text ({len(text)} chars), trying OCR for {file_path.name}")
    ocr_text = _extract_with_ocr(file_path)
    
    if ocr_text and len(ocr_text.strip()) > 50:
        logger.info(f"OCR extracted {len(ocr_text)} chars from {file_path.name}")
        return ocr_text, 0.6

    # Return whatever we got
    return text or ocr_text or "", 0.3


def _extract_with_pdfplumber(file_path: Path) -> str:
    """Extract text using pdfplumber."""
    try:
        import pdfplumber
        text_parts = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        return "\n\n".join(text_parts)
    except Exception as e:
        logger.warning(f"pdfplumber failed for {file_path}: {e}")
        return ""


def _extract_with_ocr(file_path: Path) -> str:
    """Extract text using Tesseract OCR via pdf2image."""
    try:
        from pdf2image import convert_from_path
        import pytesseract

        images = convert_from_path(file_path, dpi=300)
        text_parts = []
        for i, img in enumerate(images):
            text = pytesseract.image_to_string(img, lang="eng+hin")  # English + Hindi
            if text:
                text_parts.append(text)
        return "\n\n".join(text_parts)
    except ImportError as e:
        logger.warning(f"OCR dependencies missing: {e}")
        return ""
    except Exception as e:
        logger.warning(f"OCR failed for {file_path}: {e}")
        return ""


def extract_tables_from_pdf(file_path: str | Path) -> list:
    """Extract tables from PDF (for BOQ extraction)."""
    file_path = Path(file_path)
    try:
        import pdfplumber
        tables = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_tables = page.extract_tables()
                for table in page_tables:
                    if table and len(table) > 1:
                        tables.append(table)
        return tables
    except Exception as e:
        logger.warning(f"Table extraction failed for {file_path}: {e}")
        return []
