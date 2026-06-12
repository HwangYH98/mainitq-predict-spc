from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ACCEPTED_RUN_ID = "all-20260613-002448"


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

    assert "render_research_validation_tab()" in functions["render_admin_app"]
    assert "render_research_validation_tab()" not in functions["render_user_app"]
    assert "st.sidebar.radio" in functions["render_admin_app"]
    assert "Admin 화면" in functions["render_admin_app"]

    research_source = "\n".join(
        functions[name]
        for name in [
            "accepted_research_run_paths",
            "research_validation_issues",
            "render_research_validation_tab",
            "render_research_downloads",
        ]
    )
    assert "ACCEPTED_RESEARCH_RUN_MANIFEST" in source
    assert "EXPERIMENTS_DIR / accepted_run_id" in functions["accepted_research_run_paths"]

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


def test_accepted_research_run_manifest_selects_final_explicit_run_id() -> None:
    manifest_path = ROOT / "app" / "accepted_research_run.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["accepted_run_id"] == ACCEPTED_RUN_ID
    assert "/" not in manifest["accepted_run_id"]
    assert "\\" not in manifest["accepted_run_id"]
    assert manifest["accepted_status"] == "ACCEPTED WITH LIMITATIONS"


def test_research_run_policy_does_not_auto_select_latest_folder() -> None:
    _, functions = _dashboard_functions()
    selector = functions["accepted_research_run_paths"]

    assert "accepted_run_id" in selector
    assert "EXPERIMENTS_DIR / accepted_run_id" in selector
    assert ".iterdir(" not in selector
    assert ".glob(" not in selector
    assert "max(" not in selector
    assert "sorted(" not in selector


def test_research_downloads_are_limited_to_accepted_artifacts() -> None:
    _, functions = _dashboard_functions()
    source = functions["accepted_research_run_paths"] + functions["render_research_downloads"]

    expected_keys = [
        "baseline_report",
        "data_manifest",
        "summary",
        "fold_metrics",
        "bootstrap",
        "oof_predictions",
        "metric_figure",
        "threshold_figure",
        "report",
    ]
    for key in expected_keys:
        assert key in source

    assert "outputs/experiments" not in functions["render_research_downloads"]
    assert "EXPERIMENTS_DIR.iterdir" not in source


def test_research_validation_surfaces_actionable_issues() -> None:
    _, functions = _dashboard_functions()
    issues_source = functions["research_validation_issues"]
    tab_source = functions["render_research_validation_tab"]

    assert "commit 불일치" in issues_source
    assert "dirty worktree run" in issues_source
    assert "필수 산출물 없음" in issues_source
    assert "st.dataframe(pd.DataFrame(issues)" in tab_source
