from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _dashboard_functions() -> tuple[str, dict[str, str]]:
    source = (ROOT / "app" / "dashboard.py").read_text(encoding="utf-8-sig")
    tree = ast.parse(source)
    functions = {
        node.name: ast.get_source_segment(source, node) or ""
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }
    return source, functions


def test_research_validation_tab_is_admin_only_and_read_only() -> None:
    source, functions = _dashboard_functions()

    assert "연구 검증" in functions["render_admin_app"]
    assert "연구 검증" not in functions["render_user_app"]

    research_source = (
        functions["accepted_research_run_paths"]
        + functions["render_research_validation_tab"]
    )
    assert "검증 결과 없음" in research_source
    assert "ACCEPTED_RESEARCH_RUN_MANIFEST" in source
    assert "EXPERIMENTS_DIR / accepted_run_id" in research_source

    forbidden_execution_terms = [
        "reproduce_all.ps1",
        "reproduce_quick.ps1",
        "subprocess",
        "os.system",
        "create_experiment_run",
        "write_robust_validation_files",
    ]
    found_terms = [term for term in forbidden_execution_terms if term in research_source]
    assert not found_terms


def test_accepted_research_run_manifest_selects_explicit_run_id() -> None:
    manifest_path = ROOT / "app" / "accepted_research_run.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["accepted_run_id"] == "all-20260612-234825"
    assert "/" not in manifest["accepted_run_id"]
    assert "\\" not in manifest["accepted_run_id"]
    assert manifest["accepted_status"] == "ACCEPTED WITH LIMITATIONS"
