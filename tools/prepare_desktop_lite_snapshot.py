from __future__ import annotations

from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = ROOT / "dist" / "MaintiQ_Predict_Lite"


def copy_tree(source: Path, target: Path) -> None:
    if not source.exists():
        return
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)


def main() -> int:
    if not DIST_DIR.exists():
        raise FileNotFoundError(f"Lite distribution folder was not found: {DIST_DIR}")
    samples_dir = ROOT / "samples"
    if not (samples_dir / "company_sensor_sample.csv").exists():
        raise FileNotFoundError("samples/company_sensor_sample.csv is required for Lite distribution")
    copy_tree(samples_dir, DIST_DIR / "samples")
    copy_tree(samples_dir, DIST_DIR / "_internal" / "samples")
    shutil.copyfile(samples_dir / "company_sensor_sample.csv", DIST_DIR / "_internal" / "sample_company_sensor.csv")
    outputs_dir = DIST_DIR / "outputs"
    if outputs_dir.exists():
        shutil.rmtree(outputs_dir)
    outputs_dir.mkdir(parents=True, exist_ok=True)
    print("Lite runtime snapshot copied.")
    print(f"samples={DIST_DIR / 'samples'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
