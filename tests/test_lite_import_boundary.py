from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LITE_FILES = [
    ROOT / "desktop_app" / "lite_engine.py",
    ROOT / "desktop_app" / "lite_main.py",
    ROOT / "desktop_app" / "lite_widgets.py",
]

FORBIDDEN_IMPORTS = [
    "import pandas",
    "import matplotlib",
    "import xgboost",
    "import shap",
    "import numba",
    "import pyarrow",
    "from pandas",
    "from matplotlib",
    "from xgboost",
    "from shap",
]

FORBIDDEN_VISIBLE_WORDS = ["capstone", "presentation", "PoC", "Demo", "Stage"]
FORBIDDEN_INTERNAL_PRODUCT_PHRASES = [
    "Lite runtime",
    "Full runtime",
    "Risk rule",
    "Running Lite scoring",
    "Lightweight deterministic scoring",
]


def test_lite_runtime_does_not_import_research_packages() -> None:
    combined = "\n".join(path.read_text(encoding="utf-8") for path in LITE_FILES)
    for forbidden in FORBIDDEN_IMPORTS:
        assert forbidden not in combined


def test_lite_visible_text_avoids_research_terms() -> None:
    combined = "\n".join(path.read_text(encoding="utf-8") for path in LITE_FILES)
    for forbidden in FORBIDDEN_VISIBLE_WORDS:
        assert forbidden not in combined


def test_lite_visible_text_uses_product_labels_for_runtime() -> None:
    combined = "\n".join(path.read_text(encoding="utf-8") for path in LITE_FILES)
    assert "경량 운영 점수" in combined
    for forbidden in FORBIDDEN_INTERNAL_PRODUCT_PHRASES:
        assert forbidden not in combined
