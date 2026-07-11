"""Tests for categorization accuracy tracking."""

import json
import tempfile
from pathlib import Path

import pytest
from fastapi import status

from nexus.utils.categorizer import (
    CORRECTIONS_PATH,
    MODEL_PATH,
    PREDICTION_LOG_PATH,
    _load_prediction_log,
    _log_correction,
    _log_prediction,
    _save_prediction_log,
    get_accuracy_stats,
    predict_category,
    record_correction,
)


@pytest.fixture
def clean_categorizer_state():
    """Ensure prediction log, corrections, and model are clean; restore after test."""
    old_log = _load_prediction_log()
    old_model = None
    old_corrections = None
    if MODEL_PATH.exists():
        old_model = MODEL_PATH.read_bytes()
        MODEL_PATH.unlink()
    if CORRECTIONS_PATH.exists():
        old_corrections = CORRECTIONS_PATH.read_text()
        CORRECTIONS_PATH.unlink()
    _save_prediction_log([])
    yield
    _save_prediction_log(old_log)
    if old_model is not None:
        MODEL_PATH.write_bytes(old_model)
    elif MODEL_PATH.exists():
        MODEL_PATH.unlink()
    if old_corrections is not None:
        CORRECTIONS_PATH.write_text(old_corrections)
    elif CORRECTIONS_PATH.exists():
        CORRECTIONS_PATH.unlink()


# ── Unit tests for logging functions ────────────────────────────────────────


def test_empty_log_returns_zero_accuracy(clean_categorizer_state):
    stats = get_accuracy_stats()
    assert stats["total_predictions"] == 0
    assert stats["total_corrections"] == 0
    assert stats["matched_pairs"] == 0
    assert stats["accuracy"] == 0.0
    assert stats["recent_days"] == 30


def test_log_prediction_writes_entry(clean_categorizer_state):
    _log_prediction("starbucks", "Dining", 0.95)
    log = _load_prediction_log()
    assert len(log) == 1
    assert log[0]["vendor"] == "starbucks"
    assert log[0]["predicted"] == "Dining"
    assert log[0]["confidence"] == 0.95
    assert log[0]["corrected"] is None
    assert "timestamp" in log[0]


def test_log_correction_links_to_latest_unmatched_prediction(clean_categorizer_state):
    _log_prediction("starbucks", "Dining", 0.85)
    _log_prediction("starbucks", "Groceries", 0.60)
    _log_correction("starbucks", "Dining")

    log = _load_prediction_log()
    assert len(log) == 2
    # The second prediction (most recent unmatched) should be corrected
    assert log[1]["predicted"] == "Groceries"
    assert log[1]["corrected"] == "Dining"
    # The first one should still be uncorrected
    assert log[0]["corrected"] is None


def test_log_correction_with_no_prediction_creates_standalone(clean_categorizer_state):
    _log_correction("unknown_vendor", "Shopping")
    log = _load_prediction_log()
    assert len(log) == 1
    assert log[0]["vendor"] == "unknown_vendor"
    assert log[0]["predicted"] is None
    assert log[0]["corrected"] == "Shopping"


def test_accuracy_calculation_correct_matches(clean_categorizer_state):
    _log_prediction("starbucks", "Dining", 0.9)
    _log_prediction("chevron", "Transportation", 0.8)
    _log_prediction("amazon", "Shopping", 0.7)

    # Correct two correctly, one incorrectly
    _log_correction("starbucks", "Dining")  # match
    _log_correction("chevron", "Groceries")  # mismatch
    _log_correction("amazon", "Shopping")  # match

    stats = get_accuracy_stats()
    assert stats["total_predictions"] == 3
    assert stats["total_corrections"] == 3
    assert stats["matched_pairs"] == 3
    assert stats["correct"] == 2
    assert stats["accuracy"] == pytest.approx(2 / 3, abs=0.01)

    # Per-category check
    assert "Dining" in stats["per_category"]
    assert stats["per_category"]["Dining"]["total"] == 1
    assert stats["per_category"]["Dining"]["correct"] == 1
    assert stats["per_category"]["Dining"]["accuracy"] == 1.0

    assert "Transportation" in stats["per_category"]
    assert stats["per_category"]["Transportation"]["correct"] == 0


def test_accuracy_ignores_results_outside_window(clean_categorizer_state):
    # Add an old entry by faking the timestamp
    _log_prediction("ancient_vendor", "Bills", 0.99)
    log = _load_prediction_log()
    log[0]["timestamp"] = "2020-01-01T00:00:00+00:00"
    _save_prediction_log(log)

    stats = get_accuracy_stats(days=30)
    # The old prediction should be filtered out
    assert stats["total_predictions"] == 0


def test_max_log_size_enforced(clean_categorizer_state):
    for i in range(2500):
        _log_prediction(f"vendor_{i}", "Dining", 0.9)
    log = _load_prediction_log()
    assert len(log) <= 2000


# ── Integration: categorizer records predictions and corrections ────────────


def test_predict_category_logs_prediction(clean_categorizer_state):
    cat, conf = predict_category("starbucks")
    assert cat == "Dining"
    assert conf > 0.0

    log = _load_prediction_log()
    assert len(log) >= 1
    last = log[-1]
    assert last["vendor"] == "starbucks"
    assert last["predicted"] == "Dining"


def test_record_correction_logs_and_links(clean_categorizer_state):
    # Predict first
    predict_category("starbucks")
    # Then correct
    record_correction("starbucks", "Groceries")

    log = _load_prediction_log()
    corrected_entry = next((e for e in log if e["corrected"] is not None), None)
    assert corrected_entry is not None
    assert corrected_entry["predicted"] == "Dining"
    assert corrected_entry["corrected"] == "Groceries"


# ── API Endpoint tests ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_accuracy_endpoint_requires_auth(client):
    response = await client.get("/api/v1/finance/analytics/categorizer-accuracy")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
