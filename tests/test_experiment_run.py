from __future__ import annotations

import json

from experiment_run import create_experiment_run


def test_experiment_run_writes_manifest_environment_and_artifact_hash(tmp_path) -> None:
    run = create_experiment_run(run_id="unit-run", experiment_root=tmp_path)

    output_path = run.write_json("sample.json", {"ok": True})
    run.append_command("unit", ["python", "-m", "pytest"], exit_code=0)
    run.update_status("passed", {"unit": True})

    manifest = json.loads((run.run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    artifact_manifest = json.loads((run.run_dir / "artifact_manifest.json").read_text(encoding="utf-8"))
    command_lines = (run.run_dir / "command_log.txt").read_text(encoding="utf-8").splitlines()

    assert manifest["run_id"] == "unit-run"
    assert manifest["status"] == "passed"
    assert (run.run_dir / "environment.json").exists()
    assert output_path.exists()
    assert (run.run_dir / "artifact_manifest.csv").exists()
    assert any(item["path"].endswith("sample.json") and item["sha256"] for item in artifact_manifest["artifacts"])
    assert command_lines
