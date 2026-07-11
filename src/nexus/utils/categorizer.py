"""ML categorizer — predict transaction category from vendor name and features."""

import json
import re
from pathlib import Path
from typing import Optional

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

MODEL_DIR = Path.home() / ".nexus" / "models"
MODEL_PATH = MODEL_DIR / "category_model.joblib"
CORRECTIONS_PATH = Path.home() / ".nexus" / "category_corrections.json"

# Default training data (bootstrapped seed)
SEED_DATA: list[tuple[str, str]] = [
    # Dining
    ("starbucks", "Dining"), ("mc donalds", "Dining"), ("mcdonalds", "Dining"),
    ("wendys", "Dining"), ("chipotle", "Dining"), ("subway", "Dining"),
    ("pizza hut", "Dining"), ("dominos", "Dining"), ("restaurant", "Dining"),
    ("cafe", "Dining"), ("coffee", "Dining"), ("diner", "Dining"),
    ("dunkin", "Dining"), ("kfc", "Dining"), ("taco bell", "Dining"),
    ("burger king", "Dining"), ("panera", "Dining"), ("olive garden", "Dining"),
    ("chilis", "Dining"), ("applebees", "Dining"), ("dairy queen", "Dining"),
    ("panda express", "Dining"), ("popeyes", "Dining"), ("five guys", "Dining"),
    ("wingstop", "Dining"), ("jimmy johns", "Dining"), ("jersey mikes", "Dining"),
    ("qdobra", "Dining"), ("chipotle mexican grill", "Dining"),
    ("the cheesecake factory", "Dining"), ("outback steakhouse", "Dining"),
    ("texas roadhouse", "Dining"), ("red lobster", "Dining"),
    
    # Groceries
    ("walmart", "Groceries"), ("target", "Groceries"), ("kroger", "Groceries"),
    ("whole foods", "Groceries"), ("aldi", "Groceries"), ("sprouts", "Groceries"),
    ("safeway", "Groceries"), ("publix", "Groceries"), ("costco", "Groceries"),
    ("grocery", "Groceries"), ("supermarket", "Groceries"),
    ("trader joes", "Groceries"), ("wegmans", "Groceries"),
    ("hebs", "Groceries"), ("food lion", "Groceries"), ("giant", "Groceries"),
    ("stop shop", "Groceries"), ("meijer", "Groceries"), ("winco", "Groceries"),
    ("sam club", "Groceries"), ("bj wholesale", "Groceries"),
    
    # Entertainment
    ("netflix", "Entertainment"), ("spotify", "Entertainment"), ("hulu", "Entertainment"),
    ("disney", "Entertainment"), ("hbo", "Entertainment"), ("paramount", "Entertainment"),
    ("peacock", "Entertainment"), ("max", "Entertainment"),
    ("amc", "Entertainment"), ("cinemark", "Entertainment"), ("regal", "Entertainment"),
    ("movie theater", "Entertainment"), ("cinema", "Entertainment"),
    ("crunchyroll", "Entertainment"), ("youtube premium", "Entertainment"),
    ("apple tv", "Entertainment"), ("apple music", "Entertainment"),
    ("twitch", "Entertainment"), ("steam", "Entertainment"),
    ("xbox", "Entertainment"), ("playstation", "Entertainment"),
    ("nintendo", "Entertainment"), ("game stop", "Entertainment"),
    
    # Transportation
    ("uber", "Transportation"), ("lyft", "Transportation"), ("gas station", "Transportation"),
    ("shell", "Transportation"), ("exxon", "Transportation"), ("chevron", "Transportation"),
    ("bp", "Transportation"), ("speedway", "Transportation"), ("parking", "Transportation"),
    ("toll", "Transportation"), ("transit", "Transportation"), ("amtrak", "Transportation"),
    ("gas", "Transportation"), ("fuel", "Transportation"),
    ("circle k", "Transportation"), ("7 eleven", "Transportation"),
    ("delta airlines", "Transportation"), ("united airlines", "Transportation"),
    ("southwest", "Transportation"), ("american airlines", "Transportation"),
    ("uber eats", "Transportation"), ("doordash", "Transportation"), ("grubhub", "Transportation"),
    
    # Shopping
    ("amazon", "Shopping"), ("amazon prime", "Shopping"), ("amzn", "Shopping"),
    ("etsy", "Shopping"), ("ebay", "Shopping"), ("walmart.com", "Shopping"),
    ("nordstrom", "Shopping"), ("macys", "Shopping"), ("best buy", "Shopping"),
    ("home depot", "Shopping"), ("lowes", "Shopping"), ("ikea", "Shopping"),
    ("target.com", "Shopping"), ("shopify", "Shopping"),
    ("zara", "Shopping"), ("h m", "Shopping"), ("gap", "Shopping"),
    ("nike", "Shopping"), ("adidas", "Shopping"),
    ("wish", "Shopping"), ("temu", "Shopping"),
    
    # Bills & Utilities
    ("verizon", "Bills"), ("at t", "Bills"), ("t mobile", "Bills"),
    ("comcast", "Bills"), ("xfinity", "Bills"), ("electric", "Bills"),
    ("water bill", "Bills"), ("internet", "Bills"), ("phone bill", "Bills"),
    ("insurance", "Bills"), ("rent", "Bills"), ("mortgage", "Bills"),
    ("geico", "Bills"), ("state farm", "Bills"), ("allstate", "Bills"),
    ("progressive", "Bills"), ("liberty mutual", "Bills"),
    ("cable", "Bills"), ("utility", "Bills"),
    ("duke energy", "Bills"), ("pge", "Bills"),
    
    # Health
    ("cvs", "Health"), ("walgreens", "Health"), ("pharmacy", "Health"),
    ("doctor", "Health"), ("hospital", "Health"), ("dentist", "Health"),
    ("optometrist", "Health"), ("copay", "Health"), ("prescription", "Health"),
    ("urgent care", "Health"), ("clinic", "Health"),
]


def _clean_vendor(vendor: str) -> str:
    """Normalize vendor name: lowercase, remove common suffixes."""
    v = vendor.lower().strip()
    v = re.sub(r"\b(inc|llc|ltd|corp|co|store|online|com|www)\b", "", v)
    v = re.sub(r"[^a-z0-9\s]", "", v)
    v = re.sub(r"\s+", " ", v).strip()
    return v


def _build_pipeline() -> Pipeline:
    return Pipeline([
        ("tfidf", TfidfVectorizer(analyzer="word", ngram_range=(1, 2), max_features=1000)),
        ("clf", LogisticRegression(max_iter=200, C=1.0)),
    ])


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


def predict_category(vendor: str) -> tuple[Optional[str], float]:
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

    if confidence < 0.3:
        return None, confidence

    return category, confidence


def record_correction(vendor: str, correct_category: str) -> None:
    """Record a user correction and retrain the model."""
    corrections = _load_corrections()
    corrections.append((vendor, correct_category))
    _save_corrections(corrections)

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
    return sorted(set(c for _, c in SEED_DATA))
