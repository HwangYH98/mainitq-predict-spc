from __future__ import annotations

from pathlib import Path
import os
import shutil
import stat


SRC_FILES = [
    "data.py",
    "evaluate.py",
    "operations_store.py",
    "predictive_spc.py",
    "preprocessing_prediction_engine.py",
    "realtime_ops.py",
    "scania_product_engine.py",
    "train_baseline.py",
]


OUTPUT_FILES = [
    "ai_manager_report.md",
    "ai_report_context.json",
    "baseline_predictions.csv",
    "company_input_quality_report.csv",
    "company_input_quality_report.json",
    "company_prediction_results.csv",
    "company_preprocessing_report.md",
    "company_risk_priority_queue.csv",
    "confusion_matrix.png",
    "metrics.json",
    "operating_policy_simulation.md",
    "operating_policy_thresholds.json",
    "prediction_confidence_report.md",
    "probability_calibration_curve.png",
    "probability_calibration_metrics.json",
    "pr_curve.png",
    "shap_bar.png",
    "shap_summary.png",
    "spc_control_chart.png",
    "spc_risk_chart.png",
    "spc_summary.json",
    "spc_timeseries.csv",
    "scania_cost_optimized_model.joblib",
    "threshold_summary.json",
    "threshold_tuning.png",
]


def reset_dir(path: Path) -> None:
    if path.exists():
        def make_writable_and_retry(function, item_path, _exc_info):
            os.chmod(item_path, stat.S_IWRITE)
            function(item_path)

        shutil.rmtree(path, onexc=make_writable_and_retry)
    path.mkdir(parents=True, exist_ok=True)


def copy_existing_files(root: Path, relative_dir: str, filenames: list[str], dest: Path) -> int:
    copied = 0
    source_dir = root / relative_dir
    for filename in filenames:
        source = source_dir / filename
        if source.exists():
            shutil.copy2(source, dest / filename)
            copied += 1
    return copied


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    app_dir = root / "dist" / "MaintiQ_Predict"
    exe_path = app_dir / "MaintiQ_Predict.exe"
    if not exe_path.exists():
        raise SystemExit(f"Missing desktop executable: {exe_path}")

    src_dest = app_dir / "src"
    data_dest = app_dir / "data"
    outputs_dest = app_dir / "outputs"
    samples_dest = app_dir / "samples"
    reset_dir(src_dest)
    reset_dir(data_dest)
    reset_dir(outputs_dest)
    reset_dir(samples_dest)

    src_count = copy_existing_files(root, "src", SRC_FILES, src_dest)

    data_source = root / "data" / "ai4i2020.csv"
    if not data_source.exists():
        raise SystemExit(f"Missing required data file: {data_source}")
    shutil.copy2(data_source, data_dest / "ai4i2020.csv")

    samples_source = root / "samples"
    sample_count = 0
    if samples_source.exists():
        for sample_file in samples_source.glob("*.csv"):
            shutil.copy2(sample_file, samples_dest / sample_file.name)
            sample_count += 1

    output_count = copy_existing_files(root, "outputs", OUTPUT_FILES, outputs_dest)

    print("MaintiQ Predict runtime snapshot prepared.")
    print(f"src files: {src_count}")
    print("data files: 1")
    print(f"sample files: {sample_count}")
    print(f"output files: {output_count}")
    print("excluded: operations.db, API keys, data_external, admin notes, benchmark raw data")


if __name__ == "__main__":
    main()
