"""OCR engine — receipt image processing, text extraction, and parsing."""

import re
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
import pytesseract


class OCRResult:
    """Result of an OCR extraction."""

    def __init__(
        self,
        raw_text: str,
        confidence: float,
        vendor: Optional[str] = None,
        amount: Optional[Decimal] = None,
        tx_date: Optional[date] = None,
    ):
        self.raw_text = raw_text
        self.confidence = confidence  # 0.0 - 1.0
        self.vendor = vendor
        self.amount = amount
        self.tx_date = tx_date

    def is_reliable(self, threshold: float = 0.6) -> bool:
        return self.confidence >= threshold


def preprocess_image(image_path: str | Path) -> np.ndarray:
    """Load and preprocess a receipt image for OCR."""
    img = cv2.imread(str(image_path))
    if img is None:
        raise ValueError(f"Could not load image: {image_path}")

    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Denoise
    denoised = cv2.fastNlMeansDenoising(gray, h=10)

    # Threshold to binary
    _, binary = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    return binary


def extract_text(image: np.ndarray) -> tuple[str, float]:
    """Extract text from a preprocessed image using Tesseract."""
    data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)

    # Calculate mean confidence (filter out -1 entries)
    confidences = [c for c in data["conf"] if c > 0]
    mean_conf = sum(confidences) / len(confidences) / 100.0 if confidences else 0.0

    # Build full text
    text_lines = []
    current_line = []
    prev_left = 0
    prev_top = 0

    for i in range(len(data["text"])):
        text = data["text"][i].strip()
        if not text:
            continue
        # New line if y position changed significantly
        if data["top"][i] > prev_top + 10 and current_line:
            text_lines.append(" ".join(current_line))
            current_line = []
        current_line.append(text)
        prev_left = data["left"][i]
        prev_top = data["top"][i]

    if current_line:
        text_lines.append(" ".join(current_line))

    return "\n".join(text_lines), mean_conf


def parse_vendor(text: str) -> Optional[str]:
    """Extract vendor/merchant name from OCR text."""
    lines = text.strip().split("\n")

    # Usually the first non-empty line is the vendor
    for line in lines:
        line = line.strip()
        if line and len(line) > 2:
            # Skip if it looks like a date or amount
            if re.match(r"^\d", line):
                continue
            if re.match(r"^[\d$€£.]", line):
                continue
            return line.strip()
    return None


def parse_amount(text: str) -> Optional[Decimal]:
    """Extract total amount from OCR text."""
    # Look for "TOTAL", "AMOUNT", "BALANCE DUE" followed by a dollar amount
    patterns = [
        r"(?:total|amount|balance\s*due|amount\s*due|sum)\s*:?\s*\$?(\d+\.\d{2})",
        r"\$?(\d+\.\d{2})\s*(?:total|amount)",
        r"(?:^|\n)\$?(\d+\.\d{2})\s*$",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            try:
                return Decimal(match.group(1))
            except Exception:
                pass

    # Fallback: find the largest monetary amount
    amounts = re.findall(r"\$?(\d+\.\d{2})", text)
    if amounts:
        try:
            return Decimal(max(amounts, key=lambda x: float(x)))
        except Exception:
            pass

    return None


def parse_date(text: str) -> Optional[date]:
    """Extract transaction date from OCR text."""
    from dateparser import parse as dp_parse

    # Common date formats on receipts
    patterns = [
        r"(\d{1,2}/\d{1,2}/\d{4})",
        r"(\d{4}-\d{2}-\d{2})",
        r"(\d{1,2}/\d{1,2}/\d{2})",
        r"(\d{2}\.\d{2}\.\d{4})",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            parsed = dp_parse(match.group(1))
            if parsed:
                return parsed.date()

    return None


def confidence_score(
    raw_text: str, ocr_confidence: float, vendor: bool, amount: bool, tx_date: bool
) -> float:
    """Calculate overall confidence score for the extraction."""
    score = ocr_confidence * 0.4  # Base OCR quality

    if vendor:
        score += 0.2
    if amount:
        score += 0.25
    if tx_date:
        score += 0.15

    return min(score, 1.0)


def process_receipt(image_path: str | Path) -> OCRResult:
    """Full OCR pipeline: load → preprocess → extract → parse."""
    image = preprocess_image(image_path)
    raw_text, ocr_conf = extract_text(image)

    vendor = parse_vendor(raw_text)
    amount = parse_amount(raw_text)
    tx_date = parse_date(raw_text)

    conf = confidence_score(raw_text, ocr_conf, vendor is not None, amount is not None, tx_date is not None)

    return OCRResult(
        raw_text=raw_text,
        confidence=conf,
        vendor=vendor,
        amount=amount,
        tx_date=tx_date,
    )
