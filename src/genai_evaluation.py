from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from experiment_run import DEFAULT_EXPERIMENT_ROOT, create_experiment_run, record_current_process
from genai_response_checks import check_response
from predictive_spc import build_llm_prompt, genai_ai_report


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASE_PATH = PROJECT_ROOT / "data" / "genai_eval_cases.jsonl"
DEFAULT_HUMAN_FORM_TEMPLATE = PROJECT_ROOT / "docs" / "genai_human_review_form.csv"
DEFAULT_RUN_PREFIX = "genai-eval"
DEFAULT_PROVIDER = "gemini"
FROZEN_MODEL_METADATA = {
    "provider": DEFAULT_PROVIDER,
    "model": "offline-replay-via-existing-genai-ai-report-fallback",
    "deterministic_temperature": 0,
    "repeat_temperature": 0.2,
    "prompt_builder": "src.predictive_spc.build_llm_prompt",
    "generation_function": "src.predictive_spc.genai_ai_report",
}


def load_cases(path: str | Path = DEFAULT_CASE_PATH) -> list[dict[str, Any]]:
    case_path = Path(path)
    if not case_path.exists():
        raise FileNotFoundError(f"Missing GenAI evaluation case file: {case_path}")

    cases = []
    with case_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                case = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"Invalid JSONL at {case_path}:{line_number}: {error}") from error
            required = {
                "case_id",
                "risk_level",
                "context",
                "allowed_facts",
                "forbidden_facts",
                "required_approval_language",
                "expected_probability",
                "expected_threshold",
            }
            missing = sorted(required - set(case))
            if missing:
                raise ValueError(f"Case {line_number} is missing required keys: {missing}")
            cases.append(case)

    _validate_case_mix(cases)
    return cases


def _validate_case_mix(cases: list[dict[str, Any]]) -> None:
    counts: dict[str, int] = {}
    for case in cases:
        counts[str(case["risk_level"])] = counts.get(str(case["risk_level"]), 0) + 1

    requirements = {
        "low": 5,
        "boundary": 5,
        "high": 5,
        "incomplete": 3,
    }
    missing = {
        risk_level: minimum
        for risk_level, minimum in requirements.items()
        if counts.get(risk_level, 0) < minimum
    }
    if missing:
        raise ValueError(f"GenAI case mix does not meet Workstream 3 minimums: {missing}")


def prompt_hash(context: dict[str, Any]) -> str:
    prompt = build_llm_prompt(context)
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


@contextmanager
def offline_provider_environment(provider: str = DEFAULT_PROVIDER):
    """Force the existing generator down its no-API fallback path without storing secrets."""
    saved = {
        "AI_REPORT_PROVIDER": os.environ.get("AI_REPORT_PROVIDER"),
        "GEMINI_API_KEY": os.environ.get("GEMINI_API_KEY"),
        "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY"),
    }
    os.environ["AI_REPORT_PROVIDER"] = provider
    os.environ.pop("GEMINI_API_KEY", None)
    os.environ.pop("OPENAI_API_KEY", None)
    try:
        yield
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def generate_response(
    case: dict[str, Any],
    *,
    provider: str = DEFAULT_PROVIDER,
    offline_replay: bool = True,
) -> tuple[str, str]:
    context = case["context"]
    if offline_replay:
        with offline_provider_environment(provider):
            return genai_ai_report(context, require_genai=False)
    os.environ["AI_REPORT_PROVIDER"] = provider
    return genai_ai_report(context, require_genai=False)


def evaluate_cases(
    cases: list[dict[str, Any]],
    *,
    provider: str = DEFAULT_PROVIDER,
    repetitions: int = 5,
    offline_replay: bool = True,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    raw_responses: list[dict[str, Any]] = []
    check_rows: list[dict[str, Any]] = []

    for case in cases:
        case_hash = prompt_hash(case["context"])
        response_text, mode = generate_response(
            case,
            provider=provider,
            offline_replay=offline_replay,
        )
        raw_responses.append(
            {
                "case_id": case["case_id"],
                "risk_level": case["risk_level"],
                "run_type": "deterministic",
                "repetition": 0,
                "provider": provider,
                "mode": mode,
                "temperature": 0,
                "prompt_sha256": case_hash,
                "response": response_text,
            }
        )
        check_rows.append(check_response(case, response_text).as_dict())

        for repetition in range(1, repetitions + 1):
            repeat_text, repeat_mode = generate_response(
                case,
                provider=provider,
                offline_replay=offline_replay,
            )
            raw_responses.append(
                {
                    "case_id": case["case_id"],
                    "risk_level": case["risk_level"],
                    "run_type": "repeat",
                    "repetition": repetition,
                    "provider": provider,
                    "mode": repeat_mode,
                    "temperature": 0.2,
                    "prompt_sha256": case_hash,
                    "response": repeat_text,
                }
            )

    repeat_rows = build_repeat_consistency(raw_responses)
    return raw_responses, check_rows, repeat_rows


def build_repeat_consistency(raw_responses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_case: dict[str, list[dict[str, Any]]] = {}
    for response in raw_responses:
        if response["run_type"] != "repeat":
            continue
        by_case.setdefault(str(response["case_id"]), []).append(response)

    rows = []
    for case_id, responses in sorted(by_case.items()):
        normalized = {normalize_response(item["response"]) for item in responses}
        rows.append(
            {
                "case_id": case_id,
                "repeat_count": len(responses),
                "distinct_response_count": len(normalized),
                "all_repeats_identical": len(normalized) <= 1,
            }
        )
    return rows


def normalize_response(text: str) -> str:
    return " ".join(text.split())


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def automatic_check_summary(check_rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(check_rows)
    if total == 0:
        return {"case_count": 0, "status": "failed", "reason": "no checks"}

    boolean_fields = [
        "probability_match",
        "threshold_match",
        "sensor_names_supported",
        "shap_factor_match",
        "unsupported_cause_absent",
        "autonomous_command_absent",
        "human_approval_explicit",
        "invented_history_absent",
        "boundary_uncertainty_present",
        "overall_pass",
    ]
    rates = {}
    for field in boolean_fields:
        passed = sum(1 for row in check_rows if bool(row.get(field)))
        rates[field] = {
            "passed": passed,
            "failed": total - passed,
            "pass_rate": round(passed / total, 6),
        }

    preregistered_targets = {
        "numeric_mismatch_count": sum(
            1
            for row in check_rows
            if not bool(row.get("probability_match")) or not bool(row.get("threshold_match"))
        ),
        "unsupported_sensor_name_count": sum(
            1 for row in check_rows if not bool(row.get("sensor_names_supported"))
        ),
        "autonomous_command_count": sum(
            1 for row in check_rows if not bool(row.get("autonomous_command_absent"))
        ),
        "approval_boundary_failure_count": sum(
            1 for row in check_rows if not bool(row.get("human_approval_explicit"))
        ),
        "invented_history_count": sum(
            1 for row in check_rows if not bool(row.get("invented_history_absent"))
        ),
    }
    return {
        "case_count": total,
        "overall_pass_count": rates["overall_pass"]["passed"],
        "overall_fail_count": rates["overall_pass"]["failed"],
        "rates": rates,
        "preregistered_targets": preregistered_targets,
        "status": "passed" if rates["overall_pass"]["failed"] == 0 else "completed_with_findings",
    }


def write_blank_human_review_form(path: Path, cases: list[dict[str, Any]]) -> None:
    fieldnames = [
        "case_id",
        "risk_level",
        "reviewer_id",
        "factual_consistency_1_to_5",
        "usefulness_1_to_5",
        "clarity_1_to_5",
        "uncertainty_1_to_5",
        "unsafe_recommendation_yes_no",
        "missing_approval_boundary_yes_no",
        "reviewer_notes",
    ]
    rows = [
        {
            "case_id": case["case_id"],
            "risk_level": case["risk_level"],
            "reviewer_id": "",
            "factual_consistency_1_to_5": "",
            "usefulness_1_to_5": "",
            "clarity_1_to_5": "",
            "uncertainty_1_to_5": "",
            "unsafe_recommendation_yes_no": "",
            "missing_approval_boundary_yes_no": "",
            "reviewer_notes": "",
        }
        for case in cases
    ]
    _write_csv(path, rows, fieldnames)


def write_report(
    path: Path,
    *,
    run_id: str,
    summary: dict[str, Any],
    repeat_rows: list[dict[str, Any]],
    provider: str,
    offline_replay: bool,
) -> None:
    target = summary["preregistered_targets"]
    lines = [
        "# Workstream 3 GenAI Multi-Case Evaluation",
        "",
        f"- Run ID: `{run_id}`",
        f"- Provider setting: `{provider}`",
        f"- Offline replay: `{offline_replay}`",
        "- Generation function: `src.predictive_spc.genai_ai_report`",
        "- Expert scores: not generated; blank reviewer form only.",
        "",
        "## Automatic Check Summary",
        "",
        f"- Cases evaluated: {summary['case_count']}",
        f"- Overall pass: {summary['overall_pass_count']}",
        f"- Overall fail: {summary['overall_fail_count']}",
        f"- Numeric mismatch count: {target['numeric_mismatch_count']}",
        f"- Unsupported sensor name count: {target['unsupported_sensor_name_count']}",
        f"- Autonomous command count: {target['autonomous_command_count']}",
        f"- Approval boundary failure count: {target['approval_boundary_failure_count']}",
        f"- Invented maintenance history/cost count: {target['invented_history_count']}",
        "",
        "## Repeat Consistency",
        "",
    ]
    if repeat_rows:
        identical = sum(1 for row in repeat_rows if row["all_repeats_identical"])
        lines.append(f"- Cases with identical repeats: {identical}/{len(repeat_rows)}")
    else:
        lines.append("- Repetition runs were not requested.")

    lines.extend(
        [
            "",
            "## Interpretation Boundary",
            "",
            "This run is a functional and factuality screen for generated manager-reference reports.",
            "It is not an expert validation, not a field usability study, and not evidence of real maintenance effectiveness.",
            "Failures are retained in the CSV outputs and should not be hidden or rerun away.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _record_artifacts(run, paths: list[Path]) -> None:
    for path in paths:
        suffix = path.suffix.lower().lstrip(".") or "file"
        run.record_artifact(path, artifact_type=suffix)


def run_evaluation(
    *,
    case_path: str | Path = DEFAULT_CASE_PATH,
    run_id: str | None = None,
    repetitions: int = 5,
    provider: str = DEFAULT_PROVIDER,
    offline_replay: bool = True,
    experiment_root: str | Path = DEFAULT_EXPERIMENT_ROOT,
) -> Path:
    if run_id:
        requested_dir = Path(experiment_root) / run_id
        if requested_dir.exists() and any(requested_dir.iterdir()):
            raise FileExistsError(f"Refusing to reuse non-empty run directory: {requested_dir}")

    cases = load_cases(case_path)
    run = create_experiment_run(run_id=run_id, experiment_root=experiment_root, prefix=DEFAULT_RUN_PREFIX)
    record_current_process(run, "genai_evaluation")
    run.append_command(
        phase="genai_evaluation_settings",
        command={
            "case_path": str(case_path),
            "repetitions": repetitions,
            "provider": provider,
            "offline_replay": offline_replay,
        },
        exit_code=0,
    )

    raw_responses, check_rows, repeat_rows = evaluate_cases(
        cases,
        provider=provider,
        repetitions=repetitions,
        offline_replay=offline_replay,
    )
    summary = automatic_check_summary(check_rows)

    outputs = {
        "manifest": run.run_dir / "genai_evaluation_manifest.json",
        "case_manifest": run.run_dir / "case_manifest.json",
        "prompt_metadata": run.run_dir / "prompt_metadata.json",
        "raw_responses": run.run_dir / "raw_responses" / "genai_raw_responses.jsonl",
        "automatic_checks": run.run_dir / "checks" / "genai_automatic_checks.csv",
        "case_summary": run.run_dir / "checks" / "genai_case_summary.csv",
        "repeat_consistency": run.run_dir / "checks" / "genai_repeat_consistency.csv",
        "human_form": run.run_dir / "review" / "genai_human_review_form.csv",
        "report": run.run_dir / "reports" / "genai_evaluation_report.md",
        "verification": run.run_dir / "verification_report.json",
    }

    case_counts: dict[str, int] = {}
    for case in cases:
        case_counts[str(case["risk_level"])] = case_counts.get(str(case["risk_level"]), 0) + 1

    _write_json(
        outputs["manifest"],
        {
            "run_id": run.run_id,
            "workstream": 3,
            "case_path": str(Path(case_path).resolve()),
            "case_count": len(cases),
            "case_counts": case_counts,
            "offline_replay": offline_replay,
            "expert_scores_generated": False,
            "model_metadata": FROZEN_MODEL_METADATA | {"provider": provider},
        },
    )
    _write_json(
        outputs["case_manifest"],
        {
            "case_ids": [case["case_id"] for case in cases],
            "case_counts": case_counts,
        },
    )
    _write_json(
        outputs["prompt_metadata"],
        {
            "prompt_hashes": {
                case["case_id"]: prompt_hash(case["context"])
                for case in cases
            },
            "prompt_builder": "src.predictive_spc.build_llm_prompt",
        },
    )
    _write_jsonl(outputs["raw_responses"], raw_responses)
    _write_csv(outputs["automatic_checks"], check_rows)
    _write_csv(outputs["case_summary"], check_rows)
    _write_csv(outputs["repeat_consistency"], repeat_rows)
    write_blank_human_review_form(outputs["human_form"], cases)
    if DEFAULT_HUMAN_FORM_TEMPLATE.exists():
        shutil.copyfile(DEFAULT_HUMAN_FORM_TEMPLATE, run.run_dir / "review" / "genai_human_review_form_template.csv")
    write_report(
        outputs["report"],
        run_id=run.run_id,
        summary=summary,
        repeat_rows=repeat_rows,
        provider=provider,
        offline_replay=offline_replay,
    )
    _write_json(outputs["verification"], {"status": summary["status"], "summary": summary})
    _record_artifacts(run, list(outputs.values()))
    copied_template = run.run_dir / "review" / "genai_human_review_form_template.csv"
    if copied_template.exists():
        run.record_artifact(copied_template, artifact_type="csv")
    run.update_status(summary["status"], {"workstream_3": summary})
    return run.run_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Workstream 3 GenAI multi-case evaluation.")
    parser.add_argument("--case-path", default=str(DEFAULT_CASE_PATH), help="JSONL case file.")
    parser.add_argument("--run-id", default=None, help="Optional explicit run id.")
    parser.add_argument("--repetitions", type=int, default=5, help="Repeat generations per case.")
    parser.add_argument("--provider", default=DEFAULT_PROVIDER, choices=["gemini", "openai"], help="Provider setting.")
    parser.add_argument(
        "--allow-api",
        action="store_true",
        help="Allow configured API keys. Default forces offline no-key replay through fallback.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        run_dir = run_evaluation(
            case_path=args.case_path,
            run_id=args.run_id,
            repetitions=args.repetitions,
            provider=args.provider,
            offline_replay=not args.allow_api,
        )
    except Exception as error:
        print(json.dumps({"status": "failed", "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        raise
    print(json.dumps({"status": "completed", "run_dir": str(run_dir)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
