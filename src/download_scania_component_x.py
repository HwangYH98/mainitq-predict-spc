from __future__ import annotations

import argparse
from pathlib import Path
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data_external" / "scania_component_x"

BASE_URL = "https://api.researchdata.se/dataset/2024-34/1/file/data?filePath="
DOCUMENTATION_URL = (
    "https://api.researchdata.se/dataset/2024-34/1/file/documentation?filePath="
)

VALIDATION_FILES = [
    ("validation_labels.csv", BASE_URL + "validation_labels.csv", False),
    ("validation_specifications.csv", BASE_URL + "validation_specifications.csv", False),
    ("validation_operational_readouts.csv", BASE_URL + "validation_operational_readouts.csv", True),
]

TRAIN_FILES = [
    ("train_tte.csv", BASE_URL + "train_tte.csv", False),
    ("train_specifications.csv", BASE_URL + "train_specifications.csv", False),
    ("train_operational_readouts.csv", BASE_URL + "train_operational_readouts.csv", True),
]

OPTIONAL_DOCS = [
    (
        "Scania_component_X_PdM.pdf",
        DOCUMENTATION_URL + "Scania_component_X_PdM.pdf",
        False,
    ),
    (
        "2024_IDA_challenge_v2.pdf",
        DOCUMENTATION_URL + "2024_IDA_challenge_v2.pdf",
        False,
    ),
]


def readable_size(byte_count: int | None) -> str:
    """Format bytes for terminal output."""
    if byte_count is None:
        return "unknown"
    if byte_count >= 1024**3:
        return f"{byte_count / 1024 / 1024 / 1024:.2f} GiB"
    return f"{byte_count / 1024 / 1024:.1f} MiB"


def remote_size(url: str) -> int | None:
    """Return remote file size when the server exposes Content-Length."""
    request = Request(url, method="HEAD", headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=45) as response:
        length = response.headers.get("Content-Length")
    return int(length) if length else None


def download_file(url: str, destination: Path) -> None:
    """Download a file with simple progress output."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    size = remote_size(url)
    if destination.exists() and size is not None and destination.stat().st_size == size:
        print(f"[SKIP] {destination.name} already exists ({readable_size(size)}).")
        return

    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    print(f"[GET] {destination.name} ({readable_size(size)})")
    with urlopen(request, timeout=120) as response, destination.open("wb") as file:
        downloaded = 0
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            file.write(chunk)
            downloaded += len(chunk)
            if size and downloaded % (25 * 1024 * 1024) < 1024 * 1024:
                print(f"      {downloaded / size * 100:5.1f}%")


def write_source_note(output_dir: Path) -> None:
    """Record source/license notes next to ignored external files."""
    note = """# SCANIA Component X External Data

Source: https://researchdata.se/en/catalogue/dataset/2024-34/1
DOI: 10.58141/1w9m-yz81
License: Creative Commons Attribution 4.0 International (CC BY 4.0)

These files are stored under data_external/ and are intentionally excluded from Git.
The validation adapter uses them for public industrial benchmark validation only.
This is not this project's own factory deployment or company-data performance proof.
"""
    (output_dir / "README_SOURCE.md").write_text(note, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download the SCANIA Component X validation subset into data_external/."
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Destination folder. It should stay outside Git history.",
    )
    parser.add_argument(
        "--metadata-only",
        action="store_true",
        help="Download labels/specifications/docs only and skip large operational CSV files.",
    )
    parser.add_argument(
        "--include-train",
        action="store_true",
        help="Also download the SCANIA training files, including the large train operational CSV.",
    )
    parser.add_argument(
        "--train-only",
        action="store_true",
        help="Download only the SCANIA training files.",
    )
    parser.add_argument(
        "--skip-docs",
        action="store_true",
        help="Skip PDF documentation downloads.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    selected = []
    if not args.train_only:
        selected.extend(VALIDATION_FILES)
    if args.include_train or args.train_only:
        selected.extend(TRAIN_FILES)

    files = [(name, url) for name, url, is_large in selected if not (args.metadata_only and is_large)]
    if not args.skip_docs:
        files.extend((name, url) for name, url, _ in OPTIONAL_DOCS)

    for name, url in files:
        download_file(url, output_dir / name)

    write_source_note(output_dir)
    print("SCANIA Component X download step finished.")
    print(f"output_dir: {output_dir}")


if __name__ == "__main__":
    main()
