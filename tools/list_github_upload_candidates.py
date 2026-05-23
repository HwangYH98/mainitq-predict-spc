from __future__ import annotations

from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]

ALLOWED_OUTPUT_FILES = {
    "outputs/thesis_evidence_pack.md",
    "outputs/industrial_engineering_evidence.md",
    "outputs/field_validation_protocol.md",
    "outputs/field_data_template.csv",
    "outputs/field_cost_template.csv",
    "outputs/run_to_failure_evidence_summary.md",
}

RELEASE_ARTIFACT_PREFIXES = ("release/",)
IGNORED_LOCAL_PREFIXES = (
    ".venv/",
    ".codex/",
    "build/",
    "dist/",
    "data_external/",
    "local_presentation_notes/",
    "outputs/realtime_stream/",
    "outputs/work_order_drafts/",
)
LOCAL_ONLY_FILES = {
    "outputs/operations.db",
    "outputs/operations_lite.db",
}
LOCAL_ONLY_SUFFIXES = (".key", ".spec")


def run_git(args: list[str]) -> str:
    result = subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True, check=True)
    return result.stdout


def porcelain_entries(include_ignored: bool = False) -> list[tuple[str, str]]:
    args = ["status", "--porcelain"]
    if include_ignored:
        args.append("--ignored=matching")
    entries: list[tuple[str, str]] = []
    for line in run_git(args).splitlines():
        if not line.strip():
            continue
        status = line[:2]
        path = line[3:].replace("\\", "/")
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        entries.append((status, path))
    return entries


def is_allowed_output(path: str) -> bool:
    return path in ALLOWED_OUTPUT_FILES


def is_release_artifact(path: str) -> bool:
    lower = path.lower()
    return lower.startswith(RELEASE_ARTIFACT_PREFIXES) or lower.endswith(".exe")


def is_local_only(path: str) -> bool:
    normalized = path.replace("\\", "/")
    lower = normalized.lower()
    if normalized in LOCAL_ONLY_FILES:
        return True
    if normalized.startswith("outputs/") and not is_allowed_output(normalized):
        return True
    if any(lower.startswith(prefix.lower()) for prefix in IGNORED_LOCAL_PREFIXES):
        return True
    return any(lower.endswith(suffix) for suffix in LOCAL_ONLY_SUFFIXES)


def print_group(title: str, values: list[str], limit: int = 45) -> None:
    print(f"\n[{title}] {len(values)}")
    if not values:
        print("- none")
        return
    for value in values[:limit]:
        print(f"- {value}")
    if len(values) > limit:
        print(f"- ... {len(values) - limit} more")


def main() -> int:
    commit_targets: list[str] = []
    removal_targets: list[str] = []
    release_artifacts: list[str] = []
    local_only_candidates: list[str] = []

    for status, path in porcelain_entries():
        if status[0] == "D":
            removal_targets.append(path)
        elif is_release_artifact(path):
            release_artifacts.append(path)
        elif is_local_only(path):
            local_only_candidates.append(path)
        else:
            commit_targets.append(path)

    ignored_artifacts = [path for status, path in porcelain_entries(include_ignored=True) if status == "!!"]
    ignored_release = [path for path in ignored_artifacts if is_release_artifact(path)]
    ignored_local = [path for path in ignored_artifacts if not is_release_artifact(path)]

    print("GitHub upload scope summary")
    print("Policy: minimal source-first repository.")
    print("Commit source code, tests, samples, templates, and selected evidence files only.")
    print("Do not commit installers, runtime DBs, raw external data, screenshots, or regenerable outputs.")
    print("Suggested commit message: Finalize MaintiQ Predict desktop MVP packaging and validation tooling")
    print_group("commit 대상", commit_targets)
    print_group("repo에서 제거 대상", removal_targets)
    print_group("Release 첨부 대상 - commit 금지", sorted(set(release_artifacts + ignored_release)))
    print_group("로컬 ignored 산출물", sorted(set(local_only_candidates + ignored_local)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
