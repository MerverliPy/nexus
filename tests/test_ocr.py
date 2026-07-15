"""Tests for OCR engine — image preprocessing, text extraction, and parsing.

All heavy dependencies (cv2, pytesseract) are mocked so tests run without
OpenCV or Tesseract installed.
"""

from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

import numpy as np
import pytest

from nexus.utils.ocr import (
    OCRResult,
    confidence_score,
    extract_text,
    parse_amount,
    parse_date,
    parse_vendor,
    preprocess_image,
    process_receipt,
)


# ── OCRResult ────────────────────────────────────────────────────────────────


class TestOCRResult:
    def test_init_sets_fields(self):
        result = OCRResult(
            raw_text="Receipt text",
            confidence=0.85,
            vendor="Store",
            amount=Decimal("42.50"),
            tx_date=date(2024, 1, 15),
        )
        assert result.raw_text == "Receipt text"
        assert result.confidence == 0.85
        assert result.vendor == "Store"
        assert result.amount == Decimal("42.50")
        assert result.tx_date == date(2024, 1, 15)

    def test_is_reliable_above_threshold(self):
        assert OCRResult("", 0.8).is_reliable() is True
        assert OCRResult("", 0.6).is_reliable() is True

    def test_is_reliable_below_threshold(self):
        assert OCRResult("", 0.4).is_reliable() is False
        assert OCRResult("", 0.59).is_reliable() is False

    def test_is_reliable_custom_threshold(self):
        assert OCRResult("", 0.7).is_reliable(threshold=0.75) is False
        assert OCRResult("", 0.8).is_reliable(threshold=0.75) is True

    def test_init_defaults(self):
        result = OCRResult(raw_text="", confidence=0.0)
        assert result.vendor is None
        assert result.amount is None
        assert result.tx_date is None


# ── preprocess_image ─────────────────────────────────────────────────────────


@patch("nexus.utils.ocr.cv2")
def test_preprocess_image_success(mock_cv2):
    mock_img = MagicMock()
    mock_cv2.imread.return_value = mock_img
    mock_gray = MagicMock()
    mock_cv2.cvtColor.return_value = mock_gray
    mock_denoised = MagicMock()
    mock_cv2.fastNlMeansDenoising.return_value = mock_denoised
    mock_binary = MagicMock()
    mock_cv2.threshold.return_value = (None, mock_binary)

    result = preprocess_image("/path/to/receipt.jpg")

    assert result is mock_binary
    mock_cv2.imread.assert_called_once_with("/path/to/receipt.jpg")
    mock_cv2.cvtColor.assert_called_once_with(mock_img, mock_cv2.COLOR_BGR2GRAY)
    mock_cv2.fastNlMeansDenoising.assert_called_once_with(mock_gray, h=10)
    mock_cv2.threshold.assert_called_once()


@patch("nexus.utils.ocr.cv2")
def test_preprocess_image_not_found(mock_cv2):
    mock_cv2.imread.return_value = None

    with pytest.raises(ValueError, match="Could not load image"):
        preprocess_image("/nonexistent/image.jpg")


@patch("nexus.utils.ocr.cv2")
def test_preprocess_image_with_pathlib_path(mock_cv2):
    mock_img = MagicMock()
    mock_cv2.imread.return_value = mock_img
    mock_cv2.cvtColor.return_value = MagicMock()
    mock_cv2.fastNlMeansDenoising.return_value = MagicMock()
    mock_cv2.threshold.return_value = (None, MagicMock())

    result = preprocess_image(Path("/path/receipt.png"))
    assert result is not None
    # Verify cv2.imread was called with the string path
    mock_cv2.imread.assert_called_once_with("/path/receipt.png")


# ── extract_text ─────────────────────────────────────────────────────────────


@patch("nexus.utils.ocr.pytesseract")
def test_extract_text_returns_joined_lines(mock_ts):
    mock_ts.image_to_data.return_value = {
        "conf": [90, 85, -1, 95],
        "text": ["Total", "", "$42.50", ""],
        "top": [0, 0, 20, 20],
    }

    text, conf = extract_text(np.zeros((100, 100), dtype=np.uint8))
    assert "Total" in text
    assert "$42.50" in text
    assert conf == pytest.approx(0.9, abs=0.01)  # (90 + 85 + 95) / 3 / 100


@patch("nexus.utils.ocr.pytesseract")
def test_extract_text_no_valid_confidence(mock_ts):
    """When all confidences are -1, mean confidence is 0.0."""
    mock_ts.image_to_data.return_value = {
        "conf": [-1, -1, -1],
        "text": ["a", "b", "c"],
        "top": [0, 10, 20],
    }

    text, conf = extract_text(np.zeros((100, 100), dtype=np.uint8))
    assert conf == 0.0
    assert "a b c" in text


@patch("nexus.utils.ocr.pytesseract")
def test_extract_text_grouping_lines_by_y_position(mock_ts):
    """Words at similar y-positions are grouped into lines."""
    mock_ts.image_to_data.return_value = {
        "conf": [80, 85],
        "text": ["Line1Word1", "Line1Word2"],
        "top": [0, 5],
    }

    text, _ = extract_text(np.zeros((100, 100), dtype=np.uint8))
    assert "Line1Word1 Line1Word2" in text


# ── parse_vendor ─────────────────────────────────────────────────────────────


def test_parse_vendor_first_nonempty_line():
    text = "Walmart\n123 Main St\n$42.50"
    assert parse_vendor(text) == "Walmart"


def test_parse_vendor_skips_date_and_amount_lines():
    text = "01/15/2024\n$42.50\nStarbucks"
    assert parse_vendor(text) == "Starbucks"


def test_parse_vendor_returns_none_for_empty_text():
    assert parse_vendor("") is None


def test_parse_vendor_short_line_skipped():
    text = "AB\nTarget"
    assert parse_vendor(text) == "Target"


def test_parse_vendor_all_amounts():
    text = "$10.00\n€20.00\n£5.50"
    assert parse_vendor(text) is None


# ── parse_amount ─────────────────────────────────────────────────────────────


def test_parse_amount_total_pattern():
    text = "Items ...\nTOTAL $42.50"
    assert parse_amount(text) == Decimal("42.50")


def test_parse_amount_amount_due():
    text = "Balance Due $123.45"
    assert parse_amount(text) == Decimal("123.45")


def test_parse_amount_amount_keyword():
    text = "AMOUNT: $99.99"
    assert parse_amount(text) == Decimal("99.99")


def test_parse_amount_number_then_total():
    text = "$55.00 Total"
    assert parse_amount(text) == Decimal("55.00")


def test_parse_amount_none_found():
    text = "No monetary values here"
    assert parse_amount(text) is None


def test_parse_amount_fallback_largest():
    """Fallback: picks the largest monetary amount when no keyword patterns match."""
    # No TOTAL/AMOUNT keyword (patterns 1-2), no amount alone at end of line (pattern 3)
    # Amounts are mid-line to avoid pattern 3 end-of-line match
    text = "item $10.00 each\nitem $25.50 each\nitem $5.00 each"
    assert parse_amount(text) == Decimal("25.50")


def test_parse_amount_decimal_variants():
    text = "SUM: 42.50\n"
    assert parse_amount(text) == Decimal("42.50")


# ── parse_date ───────────────────────────────────────────────────────────────


def test_parse_date_slash_format():
    d = parse_date("Receipt from 01/15/2024")
    assert d == date(2024, 1, 15)


def test_parse_date_iso_format():
    d = parse_date("2024-03-20")
    assert d == date(2024, 3, 20)


def test_parse_date_short_year():
    d = parse_date("12/25/24")
    # dateparser parses short year — just verify it returns a date
    assert d is not None
    assert d.month == 12
    assert d.day == 25


def test_parse_date_dot_format():
    d = parse_date("15.01.2024")
    assert d is not None
    assert d.year == 2024


def test_parse_date_none_found():
    assert parse_date("No date here") is None


def test_parse_date_empty_string():
    assert parse_date("") is None


# ── confidence_score ─────────────────────────────────────────────────────────


def test_confidence_score_base_only():
    assert confidence_score("raw", 0.5, False, False, False) == pytest.approx(0.2)


def test_confidence_score_vendor_bonus():
    score = confidence_score("raw", 0.5, True, False, False)
    assert score == pytest.approx(0.4)  # 0.2 + 0.2


def test_confidence_score_all_fields():
    score = confidence_score("raw", 1.0, True, True, True)
    assert score == pytest.approx(1.0)  # 0.4 + 0.2 + 0.25 + 0.15


def test_confidence_score_capped_at_one():
    score = confidence_score("raw", 2.0, True, True, True)
    assert score == 1.0


# ── process_receipt (full pipeline) ──────────────────────────────────────────


@patch("nexus.utils.ocr.parse_date")
@patch("nexus.utils.ocr.parse_amount")
@patch("nexus.utils.ocr.parse_vendor")
@patch("nexus.utils.ocr.extract_text")
@patch("nexus.utils.ocr.preprocess_image")
def test_process_receipt_full_pipeline(
    mock_preprocess,
    mock_extract,
    mock_vendor,
    mock_amount,
    mock_date,
):
    mock_preprocess.return_value = np.zeros((100, 100), dtype=np.uint8)
    mock_extract.return_value = ("Walmart\nTotal $42.50\n01/15/2024", 0.85)
    mock_vendor.return_value = "Walmart"
    mock_amount.return_value = Decimal("42.50")
    mock_date.return_value = date(2024, 1, 15)

    result = process_receipt("/path/receipt.jpg")

    assert isinstance(result, OCRResult)
    assert result.vendor == "Walmart"
    assert result.amount == Decimal("42.50")
    assert result.tx_date == date(2024, 1, 15)
    assert result.confidence > 0
    assert result.is_reliable()


@patch("nexus.utils.ocr.parse_date")
@patch("nexus.utils.ocr.parse_amount")
@patch("nexus.utils.ocr.parse_vendor")
@patch("nexus.utils.ocr.extract_text")
@patch("nexus.utils.ocr.preprocess_image")
def test_process_receipt_partial_extraction(
    mock_preprocess,
    mock_extract,
    mock_vendor,
    mock_amount,
    mock_date,
):
    """When some fields are missing, confidence is lower."""
    mock_preprocess.return_value = np.zeros((100, 100), dtype=np.uint8)
    mock_extract.return_value = ("garbled text", 0.4)
    mock_vendor.return_value = None
    mock_amount.return_value = None
    mock_date.return_value = None

    result = process_receipt("/path/blurry.jpg")

    assert result.vendor is None
    assert result.amount is None
    assert result.tx_date is None
    assert not result.is_reliable()
