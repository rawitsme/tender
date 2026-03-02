"""NLP/regex field extraction from raw tender text.

Extracts structured fields (dates, amounts, EMD, eligibility criteria)
from unstructured tender text using pattern matching and heuristics.
"""

import re
import logging
from datetime import datetime
from typing import Optional, Dict, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ExtractedFields:
    tender_id: Optional[str] = None
    title: Optional[str] = None
    department: Optional[str] = None
    bid_close_date: Optional[datetime] = None
    publication_date: Optional[datetime] = None
    tender_value: Optional[float] = None
    emd_amount: Optional[float] = None
    document_fee: Optional[float] = None
    contact_person: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    eligibility: Optional[Dict] = None
    confidence: float = 0.0


def extract_fields(text: str) -> ExtractedFields:
    """Extract structured fields from raw tender text."""
    if not text:
        return ExtractedFields()

    fields = ExtractedFields()
    matches = 0
    total_fields = 10

    # Tender ID / NIT Number
    nit_patterns = [
        r'(?:NIT|Tender)\s*(?:No\.?|Number|ID)[:\s]*([A-Z0-9/\-]+(?:/[A-Z0-9\-]+)*)',
        r'(?:Reference|Ref\.?)\s*(?:No\.?|Number)[:\s]*([A-Z0-9/\-]+)',
        r'(NIT[-/ ]\d{1,4}[-/]\d{2,4}[-/]\d{2,4})',
    ]
    for pat in nit_patterns:
        m = re.search(pat, text, re.I)
        if m:
            fields.tender_id = m.group(1).strip()
            matches += 1
            break

    # Dates
    fields.bid_close_date = _extract_date(text, [
        r'(?:bid\s+)?(?:submission|closing)\s+(?:end\s+)?(?:date|deadline)[:\s]*(.+?)(?:\n|$)',
        r'(?:last\s+date|due\s+date)[:\s]*(.+?)(?:\n|$)',
        r'(?:close|closing)\s+(?:date|time)[:\s]*(.+?)(?:\n|$)',
    ])
    if fields.bid_close_date:
        matches += 1

    fields.publication_date = _extract_date(text, [
        r'(?:publish|published|publication)\s*(?:date)?[:\s]*(.+?)(?:\n|$)',
        r'(?:date\s+of\s+)?(?:issue|release|notice)[:\s]*(.+?)(?:\n|$)',
    ])
    if fields.publication_date:
        matches += 1

    # Amounts
    fields.tender_value = _extract_amount(text, [
        r'(?:estimated|tender|contract|approximate)\s*(?:cost|value|amount)[:\s]*(.+?)(?:\n|$)',
        r'(?:total|project)\s*(?:cost|value)[:\s]*(.+?)(?:\n|$)',
    ])
    if fields.tender_value:
        matches += 1

    fields.emd_amount = _extract_amount(text, [
        r'(?:EMD|earnest\s+money\s+deposit?|bid\s+security)[:\s]*(.+?)(?:\n|$)',
    ])
    if fields.emd_amount:
        matches += 1

    fields.document_fee = _extract_amount(text, [
        r'(?:document|tender)\s*(?:fee|cost|price)[:\s]*(.+?)(?:\n|$)',
        r'(?:cost\s+of\s+)?(?:bid|tender)\s*(?:document)[:\s]*(.+?)(?:\n|$)',
    ])
    if fields.document_fee:
        matches += 1

    # Contact
    email_match = re.search(r'[\w.+-]+@[\w-]+\.[\w.-]+', text)
    if email_match:
        fields.contact_email = email_match.group(0)
        matches += 1

    phone_match = re.search(r'(?:Ph|Phone|Tel|Contact|Mobile)[:\s.]*(\+?\d[\d\s\-]{8,15})', text, re.I)
    if phone_match:
        fields.contact_phone = phone_match.group(1).strip()
        matches += 1

    # Eligibility criteria
    fields.eligibility = _extract_eligibility(text)
    if fields.eligibility:
        matches += 1

    # Department
    dept_patterns = [
        r'(?:Department|Dept\.?|Ministry|Office)\s*(?:of\s+)?[:\s]*(.+?)(?:\n|$)',
        r'(?:Organisation|Organization)[:\s]*(.+?)(?:\n|$)',
    ]
    for pat in dept_patterns:
        m = re.search(pat, text, re.I)
        if m:
            fields.department = m.group(1).strip()[:300]
            matches += 1
            break

    fields.confidence = matches / total_fields
    return fields


def _extract_date(text: str, patterns: List[str]) -> Optional[datetime]:
    """Extract a date using multiple regex patterns."""
    for pat in patterns:
        m = re.search(pat, text, re.I)
        if m:
            date_str = m.group(1).strip()
            parsed = _parse_date_string(date_str)
            if parsed:
                return parsed
    return None


def _parse_date_string(date_str: str) -> Optional[datetime]:
    """Parse various Indian date formats."""
    date_str = re.sub(r'\s+', ' ', date_str.strip())[:50]
    formats = [
        "%d-%b-%Y %I:%M %p", "%d-%b-%Y %H:%M", "%d-%m-%Y %H:%M",
        "%d/%m/%Y %H:%M", "%d.%m.%Y %H:%M", "%d-%b-%Y", "%d-%m-%Y",
        "%d/%m/%Y", "%d.%m.%Y", "%Y-%m-%d",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str[:len(fmt) + 5], fmt)
        except ValueError:
            continue
    return None


def _extract_amount(text: str, patterns: List[str]) -> Optional[float]:
    """Extract a monetary amount using regex patterns."""
    for pat in patterns:
        m = re.search(pat, text, re.I)
        if m:
            amount_str = m.group(1).strip()
            parsed = _parse_indian_amount(amount_str)
            if parsed:
                return parsed
    return None


def _parse_indian_amount(text: str) -> Optional[float]:
    """Parse Indian currency amounts: ₹1,50,000 / Rs. 15 Lakh / 2.5 Crore."""
    if not text:
        return None
    cleaned = re.sub(r'[₹Rs.\s]', '', text)
    
    multiplier = 1
    lower = text.lower()
    if 'crore' in lower or 'cr' in lower:
        multiplier = 10_000_000
        cleaned = re.sub(r'(?i)(crore|cr\.?)', '', cleaned)
    elif 'lakh' in lower or 'lac' in lower:
        multiplier = 100_000
        cleaned = re.sub(r'(?i)(lakh|lac)', '', cleaned)
    
    cleaned = re.sub(r'[,\s]', '', cleaned).strip()
    
    # Extract first number
    num_match = re.search(r'[\d.]+', cleaned)
    if num_match:
        try:
            return float(num_match.group(0)) * multiplier
        except ValueError:
            pass
    return None


def _extract_eligibility(text: str) -> Optional[Dict]:
    """Extract eligibility criteria from tender text."""
    criteria = {}
    
    # Work experience
    exp_match = re.search(r'(?:work\s+)?experience[:\s]*(\d+)\s*(?:years?|yrs?)', text, re.I)
    if exp_match:
        criteria["min_experience_years"] = int(exp_match.group(1))
    
    # Financial turnover
    turnover_match = re.search(
        r'(?:annual\s+)?(?:turn\s*over|turnover)[:\s]*(?:Rs\.?\s*)?(.+?)(?:\n|$)', text, re.I
    )
    if turnover_match:
        amount = _parse_indian_amount(turnover_match.group(1))
        if amount:
            criteria["min_annual_turnover"] = amount
    
    # Registration requirements
    if re.search(r'(?:registered|registration)\s+(?:with|under|in)', text, re.I):
        criteria["registration_required"] = True
    
    # Class/category
    class_match = re.search(r'(?:class|category)[:\s]*([A-D]|[IV]+|\d+)', text, re.I)
    if class_match:
        criteria["contractor_class"] = class_match.group(1)

    return criteria if criteria else None
