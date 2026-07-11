"""ML categorizer — predict transaction category from vendor name and features."""

import json
import re
from pathlib import Path

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

MODEL_DIR = Path.home() / ".nexus" / "models"
MODEL_PATH = MODEL_DIR / "category_model.joblib"
CORRECTIONS_PATH = Path.home() / ".nexus" / "category_corrections.json"
PREDICTION_LOG_PATH = Path.home() / ".nexus" / "category_prediction_log.json"

# Default training data (bootstrapped seed)
SEED_DATA: list[tuple[str, str]] = [
    # Dining
    ("starbucks", "Dining"),
    ("mc donalds", "Dining"),
    ("mcdonalds", "Dining"),
    ("wendys", "Dining"),
    ("chipotle", "Dining"),
    ("subway", "Dining"),
    ("pizza hut", "Dining"),
    ("dominos", "Dining"),
    ("restaurant", "Dining"),
    ("cafe", "Dining"),
    ("coffee", "Dining"),
    ("diner", "Dining"),
    ("dunkin", "Dining"),
    ("kfc", "Dining"),
    ("taco bell", "Dining"),
    ("burger king", "Dining"),
    ("panera", "Dining"),
    ("olive garden", "Dining"),
    ("chilis", "Dining"),
    ("applebees", "Dining"),
    ("dairy queen", "Dining"),
    ("panda express", "Dining"),
    ("popeyes", "Dining"),
    ("five guys", "Dining"),
    ("wingstop", "Dining"),
    ("jimmy johns", "Dining"),
    ("jersey mikes", "Dining"),
    ("qdobra", "Dining"),
    ("chipotle mexican grill", "Dining"),
    ("the cheesecake factory", "Dining"),
    ("outback steakhouse", "Dining"),
    ("texas roadhouse", "Dining"),
    ("red lobster", "Dining"),
    # Groceries
    ("walmart", "Groceries"),
    ("target", "Groceries"),
    ("kroger", "Groceries"),
    ("whole foods", "Groceries"),
    ("aldi", "Groceries"),
    ("sprouts", "Groceries"),
    ("safeway", "Groceries"),
    ("publix", "Groceries"),
    ("costco", "Groceries"),
    ("grocery", "Groceries"),
    ("supermarket", "Groceries"),
    ("trader joes", "Groceries"),
    ("wegmans", "Groceries"),
    ("hebs", "Groceries"),
    ("food lion", "Groceries"),
    ("giant", "Groceries"),
    ("stop shop", "Groceries"),
    ("meijer", "Groceries"),
    ("winco", "Groceries"),
    ("sam club", "Groceries"),
    ("bj wholesale", "Groceries"),
    # Entertainment
    ("netflix", "Entertainment"),
    ("spotify", "Entertainment"),
    ("hulu", "Entertainment"),
    ("disney", "Entertainment"),
    ("hbo", "Entertainment"),
    ("paramount", "Entertainment"),
    ("peacock", "Entertainment"),
    ("max", "Entertainment"),
    ("amc", "Entertainment"),
    ("cinemark", "Entertainment"),
    ("regal", "Entertainment"),
    ("movie theater", "Entertainment"),
    ("cinema", "Entertainment"),
    ("crunchyroll", "Entertainment"),
    ("youtube premium", "Entertainment"),
    ("apple tv", "Entertainment"),
    ("apple music", "Entertainment"),
    ("twitch", "Entertainment"),
    ("steam", "Entertainment"),
    ("xbox", "Entertainment"),
    ("playstation", "Entertainment"),
    ("nintendo", "Entertainment"),
    ("game stop", "Entertainment"),
    # Transportation
    ("uber", "Transportation"),
    ("lyft", "Transportation"),
    ("gas station", "Transportation"),
    ("shell", "Transportation"),
    ("exxon", "Transportation"),
    ("chevron", "Transportation"),
    ("bp", "Transportation"),
    ("speedway", "Transportation"),
    ("parking", "Transportation"),
    ("toll", "Transportation"),
    ("transit", "Transportation"),
    ("amtrak", "Transportation"),
    ("gas", "Transportation"),
    ("fuel", "Transportation"),
    ("circle k", "Transportation"),
    ("7 eleven", "Transportation"),
    ("delta airlines", "Transportation"),
    ("united airlines", "Transportation"),
    ("southwest", "Transportation"),
    ("american airlines", "Transportation"),
    ("uber eats", "Transportation"),
    ("doordash", "Transportation"),
    ("grubhub", "Transportation"),
    # Shopping
    ("amazon", "Shopping"),
    ("amazon prime", "Shopping"),
    ("amzn", "Shopping"),
    ("etsy", "Shopping"),
    ("ebay", "Shopping"),
    ("walmart.com", "Shopping"),
    ("nordstrom", "Shopping"),
    ("macys", "Shopping"),
    ("best buy", "Shopping"),
    ("home depot", "Shopping"),
    ("lowes", "Shopping"),
    ("ikea", "Shopping"),
    ("target.com", "Shopping"),
    ("shopify", "Shopping"),
    ("zara", "Shopping"),
    ("h m", "Shopping"),
    ("gap", "Shopping"),
    ("nike", "Shopping"),
    ("adidas", "Shopping"),
    ("wish", "Shopping"),
    ("temu", "Shopping"),
    # Bills & Utilities
    ("verizon", "Bills"),
    ("at t", "Bills"),
    ("t mobile", "Bills"),
    ("comcast", "Bills"),
    ("xfinity", "Bills"),
    ("electric", "Bills"),
    ("water bill", "Bills"),
    ("internet", "Bills"),
    ("phone bill", "Bills"),
    ("insurance", "Bills"),
    ("rent", "Bills"),
    ("mortgage", "Bills"),
    ("geico", "Bills"),
    ("state farm", "Bills"),
    ("allstate", "Bills"),
    ("progressive", "Bills"),
    ("liberty mutual", "Bills"),
    ("cable", "Bills"),
    ("utility", "Bills"),
    ("duke energy", "Bills"),
    ("pge", "Bills"),
    # Health
    ("cvs", "Health"),
    ("walgreens", "Health"),
    ("pharmacy", "Health"),
    ("doctor", "Health"),
    ("hospital", "Health"),
    ("dentist", "Health"),
    ("optometrist", "Health"),
    ("copay", "Health"),
    ("prescription", "Health"),
    ("urgent care", "Health"),
    ("clinic", "Health"),
]


def _clean_vendor(vendor: str) -> str:
    """Normalize vendor name: lowercase, remove common suffixes."""
    v = vendor.lower().strip()
    v = re.sub(r"\b(inc|llc|ltd|corp|co|store|online|com|www)\b", "", v)
    v = re.sub(r"[^a-z0-9\s]", "", v)
    v = re.sub(r"\s+", " ", v).strip()
    return v


def _build_pipeline() -> Pipeline:
    return Pipeline(
        [
            ("tfidf", TfidfVectorizer(analyzer="word", ngram_range=(1, 2), max_features=1000)),
            ("clf", LogisticRegression(max_iter=200, C=1.0)),
        ]
    )


def _load_corrections() -> list[tuple[str, str]]:
    if CORRECTIONS_PATH.exists():
        try:
            return json.loads(CORRECTIONS_PATH.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return []


def _save_corrections(data: list[tuple[str, str]]) -> None:
    CORRECTIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    CORRECTIONS_PATH.write_text(json.dumps(data, indent=2))


def _get_model() -> Pipeline:
    """Load or train the category prediction model."""
    if MODEL_PATH.exists():
        try:
            return joblib.load(MODEL_PATH)
        except Exception:
            pass

    # Train a new model from seed data + corrections
    corrections = _load_corrections()
    all_data = SEED_DATA + corrections

    vendors = [_clean_vendor(v) for v, _ in all_data]
    categories = [c for _, c in all_data]

    pipe = _build_pipeline()
    pipe.fit(vendors, categories)

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipe, MODEL_PATH)

    return pipe


def predict_category(vendor: str) -> tuple[str | None, float]:
    """Predict a transaction category from vendor name.

    Returns (category: str | None, confidence: float).
    If confidence < 0.7, returns None.
    """
    if not vendor or not vendor.strip():
        return None, 0.0

    model = _get_model()
    clean = _clean_vendor(vendor)

    if not clean:
        return None, 0.0

    probs = model.predict_proba([clean])[0]
    best_idx = int(np.argmax(probs))
    confidence = float(probs[best_idx])
    category = model.classes_[best_idx]

    _log_prediction(vendor, category, confidence)

    if confidence < 0.3:
        return None, confidence

    return category, confidence


def record_correction(vendor: str, correct_category: str) -> None:
    # Record correction for model training
    corrections = _load_corrections()
    corrections.append((vendor, correct_category))
    _save_corrections(corrections)

    # Log to accuracy tracker
    _log_correction(vendor, correct_category)

    # Retrain
    all_data = SEED_DATA + corrections
    vendors = [_clean_vendor(v) for v, _ in all_data]
    categories = [c for _, c in all_data]

    pipe = _build_pipeline()
    pipe.fit(vendors, categories)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipe, MODEL_PATH)


def get_available_categories() -> list[str]:
    """Get the list of categories the model knows about."""
    return sorted({c for _, c in SEED_DATA})


# ── Accuracy tracking ────────────────────────────────────────────────

_MAX_LOG_ENTRIES = 2000


def _load_prediction_log() -> list[dict]:
    if PREDICTION_LOG_PATH.exists():
        try:
            return json.loads(PREDICTION_LOG_PATH.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return []


def _save_prediction_log(log: list[dict]) -> None:
    PREDICTION_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    PREDICTION_LOG_PATH.write_text(json.dumps(log, indent=2))


def _log_prediction(vendor: str, predicted: str | None, confidence: float) -> None:
    """Record a prediction event for later accuracy tracking."""
    log = _load_prediction_log()
    log.append(
        {
            "vendor": vendor,
            "predicted": predicted,
            "confidence": round(confidence, 4),
            "corrected": None,
            "timestamp": _now_iso(),
        }
    )
    if len(log) > _MAX_LOG_ENTRIES:
        log = log[-_MAX_LOG_ENTRIES:]
    _save_prediction_log(log)


def _log_correction(vendor: str, correct_category: str) -> None:
    """Link a correction to the most recent unmatched prediction for this vendor."""
    log = _load_prediction_log()
    # Find the most recent prediction for this vendor that hasn't been corrected yet
    for entry in reversed(log):
        if entry["vendor"] == vendor and entry["corrected"] is None:
            entry["corrected"] = correct_category
            _save_prediction_log(log)
            return
    # No matching prediction found — record as a standalone correction
    log.append(
        {
            "vendor": vendor,
            "predicted": None,
            "confidence": 0.0,
            "corrected": correct_category,
            "timestamp": _now_iso(),
        }
    )
    if len(log) > _MAX_LOG_ENTRIES:
        log = log[-_MAX_LOG_ENTRIES:]
    _save_prediction_log(log)


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def get_accuracy_stats(days: int = 30) -> dict:
    """Compute categorizer accuracy metrics from the prediction log.

    Returns a dict with:
      - total_predictions: total prediction events logged
      - total_corrections: total corrections logged (with or without matching prediction)
      - matched_pairs: prediction-correction pairs where both exist
      - correct: number of pairs where predicted == corrected
      - accuracy: correct / matched_pairs (0.0 if no matched pairs)
      - per_category: {category: {total, correct, accuracy}} for each predicted category
      - recent_days: number of days of history analyzed
    """
    from datetime import datetime, timedelta, timezone

    log = _load_prediction_log()
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    recent = []
    for entry in log:
        try:
            ts = datetime.fromisoformat(entry["timestamp"])
            if ts >= cutoff:
                recent.append(entry)
        except (ValueError, KeyError):
            continue

    total_predictions = sum(1 for e in recent if e.get("predicted") is not None)
    total_corrections = sum(1 for e in recent if e.get("corrected") is not None)

    # Pairs where we have both prediction and correction
    matched = [e for e in recent if e.get("predicted") is not None and e.get("corrected") is not None]
    correct = sum(1 for e in matched if e["predicted"] == e["corrected"])

    # Per-category breakdown
    per_category: dict[str, dict[str, int | float]] = {}
    for e in matched:
        cat = e["predicted"]
        if cat not in per_category:
            per_category[cat] = {"total": 0, "correct": 0, "accuracy": 0.0}
        per_category[cat]["total"] += 1
        if e["predicted"] == e["corrected"]:
            per_category[cat]["correct"] += 1

    for cat, stats in per_category.items():
        stats["accuracy"] = round(stats["correct"] / stats["total"], 3) if stats["total"] > 0 else 0.0

    return {
        "total_predictions": total_predictions,
        "total_corrections": total_corrections,
        "matched_pairs": len(matched),
        "correct": correct,
        "accuracy": round(correct / len(matched), 3) if matched else 0.0,
        "per_category": per_category,
        "recent_days": days,
    }
