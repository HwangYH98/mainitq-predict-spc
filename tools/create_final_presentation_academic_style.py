"""Compatibility wrapper for the thesis-aligned final presentation generator."""

from __future__ import annotations

import sys
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from create_final_thesis_and_presentation import main  # noqa: E402


if __name__ == "__main__":
    main()
