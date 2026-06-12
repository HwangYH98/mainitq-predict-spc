from __future__ import annotations

import hashlib
import csv
import json
import os
import platform
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXPERIMENT_ROOT = PROJECT_ROOT / "outputs" / "experiments"


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def generate_run_id(prefix: str = "run") -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    return f"{prefix}-{stamp}"


def sha256_file(path: str | Path) -> str:
    file_path = Path(path)
    digest = hashlib.sha256()
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative_to_project(path: str | Path) -> str:
    file_path = Path(path).resolve()
    try:
        return str(file_path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(file_path)


def _run_git(args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
    )
    return result.stdout.strip() if result.returncode == 0 else "not_available"


def git_info() -> dict[str, Any]:
    status = _run_git(["status", "--porcelain=v1"])
    return {
        "commit": _run_git(["rev-parse", "HEAD"]),
        "branch": _run_git(["branch", "--show-current"]),
        "dirty": bool(status),
        "status_porcelain": status.splitlines(),
    }


def environment_snapshot() -> dict[str, Any]:
    packages = {}
    for distribution in metadata.distributions():
        name = distribution.metadata.get("Name")
        if name:
            packages[name] = distribution.version

    lock_path = PROJECT_ROOT / "requirements-lock.txt"
    return {
        "created_at_utc": utc_now(),
        "python": sys.version.replace("\n", " "),
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cwd": str(PROJECT_ROOT),
        "packages": dict(sorted(packages.items(), key=lambda item: item[0].lower())),
        "requirements_lock": {
            "path": relative_to_project(lock_path),
            "exists": lock_path.exists(),
            "sha256": sha256_file(lock_path) if lock_path.exists() else None,
        },
    }


@dataclass
class ExperimentRun:
    run_id: str
    run_dir: Path

    @property
    def manifest_path(self) -> Path:
        return self.run_dir / "run_manifest.json"

    @property
    def command_log_path(self) -> Path:
        return self.run_dir / "command_log.txt"

    @property
    def artifact_manifest_path(self) -> Path:
        return self.run_dir / "artifact_manifest.json"

    @property
    def artifact_manifest_csv_path(self) -> Path:
        return self.run_dir / "artifact_manifest.csv"

    def write_json(self, name: str, payload: dict[str, Any]) -> Path:
        path = self.run_dir / name
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        self.record_artifact(path, artifact_type="json")
        return path

    def append_command(
        self,
        phase: str,
        command: list[str] | str,
        exit_code: int | None = None,
        note: str | None = None,
    ) -> None:
        record = {
            "timestamp_utc": utc_now(),
            "phase": phase,
            "command": command,
            "cwd": str(PROJECT_ROOT),
            "exit_code": exit_code,
        }
        if note:
            record["note"] = note
        with self.command_log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    def update_status(self, status: str, details: dict[str, Any] | None = None) -> None:
        manifest = _read_json(self.manifest_path)
        manifest["status"] = status
        manifest["updated_at_utc"] = utc_now()
        if details:
            manifest.setdefault("status_details", {}).update(details)
        self.manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    def record_artifact(
        self,
        path: str | Path,
        artifact_type: str,
        description: str | None = None,
    ) -> None:
        file_path = Path(path)
        if not file_path.exists() or file_path == self.artifact_manifest_path:
            return
        manifest = _read_json(self.artifact_manifest_path, default={"artifacts": []})
        artifacts = [item for item in manifest.get("artifacts", []) if item.get("path") != relative_to_project(file_path)]
        record = {
            "path": relative_to_project(file_path),
            "sha256": sha256_file(file_path),
            "size_bytes": file_path.stat().st_size,
            "type": artifact_type,
            "recorded_at_utc": utc_now(),
        }
        if description:
            record["description"] = description
        artifacts.append(record)
        manifest["artifacts"] = sorted(artifacts, key=lambda item: item["path"])
        self.artifact_manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        _write_artifact_manifest_csv(self.artifact_manifest_csv_path, manifest["artifacts"])


def _read_json(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return dict(default or {})
    return json.loads(path.read_text(encoding="utf-8"))


def create_experiment_run(
    run_id: str | None = None,
    experiment_root: str | Path = DEFAULT_EXPERIMENT_ROOT,
    prefix: str = "run",
) -> ExperimentRun:
    actual_run_id = run_id or generate_run_id(prefix)
    root = Path(experiment_root)
    run_dir = root / actual_run_id

    initial_git = git_info()
    run_dir.mkdir(parents=True, exist_ok=True)
    run = ExperimentRun(run_id=actual_run_id, run_dir=run_dir)

    if not run.manifest_path.exists():
        run.manifest_path.write_text(
            json.dumps(
                {
                    "run_id": actual_run_id,
                    "created_at_utc": utc_now(),
                    "project_root": str(PROJECT_ROOT),
                    "status": "started",
                    "git": initial_git,
                    "policy": {
                        "accepted_top_level_outputs": "read-only for reproduction scripts",
                        "new_artifact_root": relative_to_project(run_dir),
                        "secret_policy": "Do not write API keys or credentials to artifacts.",
                    },
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    if not (run.run_dir / "environment.json").exists():
        run.write_json("environment.json", environment_snapshot())
    if not run.command_log_path.exists():
        run.command_log_path.write_text("", encoding="utf-8")
    if not run.artifact_manifest_path.exists():
        run.artifact_manifest_path.write_text(json.dumps({"artifacts": []}, indent=2), encoding="utf-8")
    if not run.artifact_manifest_csv_path.exists():
        _write_artifact_manifest_csv(run.artifact_manifest_csv_path, [])

    return run


def record_current_process(run: ExperimentRun, phase: str) -> None:
    run.append_command(
        phase=phase,
        command=[sys.executable, *sys.argv],
        exit_code=None,
        note=f"pid={os.getpid()}",
    )


def _write_artifact_manifest_csv(path: Path, artifacts: list[dict[str, Any]]) -> None:
    fieldnames = ["path", "sha256", "size_bytes", "type", "description", "recorded_at_utc"]
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for artifact in artifacts:
            writer.writerow({field: artifact.get(field, "") for field in fieldnames})
