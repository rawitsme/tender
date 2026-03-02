"""BOQ (Bill of Quantities) extraction from PDF tables."""

import re
import logging
from typing import List, Optional
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class BOQRow:
    item_number: Optional[int] = None
    description: Optional[str] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None
    estimated_rate: Optional[float] = None
    total_amount: Optional[float] = None


def extract_boq_from_pdf(file_path: str | Path) -> List[BOQRow]:
    """Extract BOQ line items from a PDF.
    
    Looks for tables with typical BOQ columns:
    S.No | Description | Qty | Unit | Rate | Amount
    """
    from backend.ingestion.parser.pdf_parser import extract_tables_from_pdf
    
    tables = extract_tables_from_pdf(file_path)
    boq_items = []
    
    for table in tables:
        if _is_boq_table(table):
            items = _parse_boq_table(table)
            boq_items.extend(items)
    
    logger.info(f"Extracted {len(boq_items)} BOQ items from {file_path}")
    return boq_items


def _is_boq_table(table: list) -> bool:
    """Heuristic: check if a table looks like a BOQ."""
    if not table or len(table) < 2:
        return False
    
    header = " ".join(str(cell or "").lower() for cell in table[0])
    
    # BOQ tables typically have these column keywords
    boq_keywords = ["description", "qty", "quantity", "unit", "rate", "amount", "item"]
    matches = sum(1 for kw in boq_keywords if kw in header)
    
    return matches >= 3


def _parse_boq_table(table: list) -> List[BOQRow]:
    """Parse a BOQ table into structured rows."""
    if len(table) < 2:
        return []
    
    header = [str(cell or "").lower().strip() for cell in table[0]]
    
    # Map column indices
    col_map = _map_columns(header)
    
    items = []
    for i, row in enumerate(table[1:], start=1):
        try:
            item = BOQRow(
                item_number=i,
                description=_get_cell(row, col_map.get("description")),
                quantity=_parse_number(_get_cell(row, col_map.get("quantity"))),
                unit=_get_cell(row, col_map.get("unit")),
                estimated_rate=_parse_number(_get_cell(row, col_map.get("rate"))),
                total_amount=_parse_number(_get_cell(row, col_map.get("amount"))),
            )
            if item.description and len(item.description) > 3:
                items.append(item)
        except Exception:
            continue
    
    return items


def _map_columns(header: list) -> dict:
    """Map BOQ column names to their indices."""
    mapping = {}
    
    keywords = {
        "description": ["description", "item description", "work", "particulars", "name of item"],
        "quantity": ["qty", "quantity", "quan"],
        "unit": ["unit", "uom"],
        "rate": ["rate", "unit rate", "estimated rate"],
        "amount": ["amount", "total", "total amount", "value"],
    }
    
    for i, col in enumerate(header):
        for field, kws in keywords.items():
            if field not in mapping:
                for kw in kws:
                    if kw in col:
                        mapping[field] = i
                        break
    
    return mapping


def _get_cell(row: list, index: Optional[int]) -> Optional[str]:
    if index is None or index >= len(row):
        return None
    val = str(row[index] or "").strip()
    return val if val else None


def _parse_number(text: Optional[str]) -> Optional[float]:
    if not text:
        return None
    cleaned = re.sub(r'[,\s₹Rs.]', '', text)
    try:
        return float(cleaned)
    except ValueError:
        return None
