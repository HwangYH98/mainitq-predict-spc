from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"

for path in [PROJECT_ROOT, SRC_DIR]:
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)
