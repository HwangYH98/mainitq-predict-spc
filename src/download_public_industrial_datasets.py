from __future__ import annotations

import argparse
import zipfile
from pathlib import Path
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "data_external"

DATASETS = {
    "metropt3": {
        "folder": "metropt3",
        "url": "https://archive.ics.uci.edu/static/public/791/metropt+3+dataset.zip",
        "filename": "metropt3_dataset.zip",
        "note": "UCI MetroPT-3 compressor dataset. Check UCI terms before redistribution.",
    },
    "cmapss": {
        "folder": "cmapss",
        "url": "https://phm-datasets.s3.amazonaws.com/NASA/6.+Turbofan+Engine+Degradation+Simulation+Data+Set.zip",
        "filename": "cmapss_turbofan.zip",
        "note": "NASA PCoE C-MAPSS turbofan degradation dataset.",
    },
    "ims": {
        "folder": "ims",
        "url": "https://phm-datasets.s3.amazonaws.com/NASA/4.+Bearings.zip",
        "filename": "ims_bearings.zip",
        "note": "NASA PCoE IMS bearing run-to-failure dataset.",
    },
}


def readable_size(byte_count: int | None) -> str:
    """Format bytes for terminal output."""
    if byte_count is None:
        return "unknown size"
    if byte_count >= 1024**3:
        return f"{byte_count / 1024 / 1024 / 1024:.2f} GiB"
    return f"{byte_count / 1024 / 1024:.1f} MiB"


def remote_size(url: str) -> int | None:
    """Return remote content length when available."""
    request = Request(url, method="HEAD", headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urlopen(request, timeout=45) as response:
            length = response.headers.get("Content-Length")
    except Exception:
        return None
    return int(length) if length else None


def download(url: str, destination: Path) -> None:
    """Download one public dataset archive without extracting it."""
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
            if size and downloaded % (50 * 1024 * 1024) < 1024 * 1024:
                print(f"      {downloaded / size * 100:5.1f}%")


def write_source_note(folder: Path, dataset_id: str, note: str, url: str) -> None:
    """Record source notes next to ignored public dataset archives."""
    text = f"""# Public Industrial Dataset: {dataset_id}

Source URL: {url}
Note: {note}

This folder is under data_external/ and is intentionally excluded from Git.
Use this data only for public benchmark validation. It is not this project's
own factory deployment or company-specific cost-reduction proof.
"""
    (folder / "README_SOURCE.md").write_text(text, encoding="utf-8")


def extract_zip(archive_path: Path) -> None:
    """Extract a downloaded archive next to itself when the user asks for it."""
    extract_dir = archive_path.parent / "extracted"
    extract_dir.mkdir(parents=True, exist_ok=True)
    print(f"[EXTRACT] {archive_path.name} -> {extract_dir}")
    with zipfile.ZipFile(archive_path) as archive:
        archive.extractall(extract_dir)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download optional public industrial benchmark archives.")
    parser.add_argument(
        "--dataset",
        choices=[*DATASETS.keys(), "all"],
        default="all",
        help="Dataset archive to download. FEMTO/PRONOSTIA is local-folder only in this helper.",
    )
    parser.add_argument(
        "--output-root",
        default=str(DEFAULT_OUTPUT_ROOT),
        help="Destination root. Keep it outside Git history.",
    )
    parser.add_argument(
        "--extract",
        action="store_true",
        help="Extract downloaded ZIP files under data_external/<dataset>/extracted.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_root = Path(args.output_root)
    selected = DATASETS.keys() if args.dataset == "all" else [args.dataset]
    for dataset_id in selected:
        config = DATASETS[dataset_id]
        folder = output_root / config["folder"]
        destination = folder / config["filename"]
        download(config["url"], destination)
        if args.extract:
            extract_zip(destination)
        write_source_note(folder, dataset_id, config["note"], config["url"])
    femto_folder = output_root / "femto"
    femto_folder.mkdir(parents=True, exist_ok=True)
    (femto_folder / "README_SOURCE.md").write_text(
        "# FEMTO/PRONOSTIA Local Adapter\n\n"
        "Place extracted PRONOSTIA/FEMTO bearing files here when license terms allow local use.\n"
        "The benchmark runner will read .txt/.csv snapshots in folder order and create run-to-failure labels.\n",
        encoding="utf-8",
    )
    print("Public industrial dataset download helper finished.")
    print(f"output_root: {output_root}")


if __name__ == "__main__":
    main()
