from __future__ import annotations

import hashlib
from pathlib import Path
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
RELEASE_DIR = ROOT / "release"
CHECKSUM_PATH = RELEASE_DIR / "checksums.txt"
INSTALLERS = [
    RELEASE_DIR / "MaintiQ_Predict_Setup.exe",
    RELEASE_DIR / "MaintiQ_Predict_Lite_Setup.exe",
]


def sha256_file(path: Path, attempts: int = 8, delay_seconds: float = 1.0) -> str:
    digest = hashlib.sha256()
    last_error: OSError | None = None
    for attempt in range(1, attempts + 1):
        try:
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
            return digest.hexdigest()
        except PermissionError as error:
            last_error = error
            if attempt == attempts:
                break
            time.sleep(delay_seconds)
            digest = hashlib.sha256()
    if last_error is not None:
        raise last_error
    return digest.hexdigest()


def main() -> int:
    missing = [str(path.relative_to(ROOT)) for path in INSTALLERS if not path.exists()]
    if missing:
        print("Checksum generation skipped. Missing installer(s):")
        for item in missing:
            print(f"- {item}")
        return 2

    RELEASE_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    for installer in INSTALLERS:
        size_mb = installer.stat().st_size / (1024 * 1024)
        rows.append(f"{sha256_file(installer)}  {installer.name}  {size_mb:.1f} MB")
    CHECKSUM_PATH.write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(f"Release checksums written: {CHECKSUM_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
