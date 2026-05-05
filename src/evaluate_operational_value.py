from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
from sklearn.metrics import confusion_matrix, f1_score, precision_score, recall_score


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "outputs"
SPC_TIMESERIES_PATH = OUTPUT_DIR / "spc_timeseries.csv"

SIMULATION_CSV = OUTPUT_DIR / "operational_value_simulation.csv"
SIMULATION_JSON = OUTPUT_DIR / "operational_value_simulation.json"
SIMULATION_PNG = OUTPUT_DIR / "operational_value_simulation.png"
SIMULATION_MD = OUTPUT_DIR / "operational_value_simulation.md"


COST_SCENARIOS = {
    "conservative": {
        "false_alarm_cost": 1.0,
        "missed_failure_cost": 8.0,
        "planned_action_cost": 2.0,
    },
    "balanced": {
        "false_alarm_cost": 1.0,
        "missed_failure_cost": 15.0,
        "planned_action_cost": 2.0,
    },
    "high_downtime": {
        "false_alarm_cost": 1.0,
        "missed_failure_cost": 30.0,
        "planned_action_cost": 3.0,
    },
}


def alert_metrics(y_true: pd.Series, y_pred: pd.Series) -> dict:
    """Calculate alert metrics and confusion-matrix counts."""
    predicted = y_pred.astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, predicted, labels=[0, 1]).ravel()
    return {
        "precision": float(precision_score(y_true, predicted, zero_division=0)),
        "recall": float(recall_score(y_true, predicted, zero_division=0)),
        "f1_score": float(f1_score(y_true, predicted, zero_division=0)),
        "alert_count": int(fp + tp),
        "false_alarm_count": int(fp),
        "missed_failure_count": int(fn),
        "true_positive_count": int(tp),
        "true_negative_count": int(tn),
    }


def build_policy_predictions(spc: pd.DataFrame) -> list[dict]:
    """Return fixed alert policies used in the thesis evidence pack."""
    selected_threshold = float(spc["selected_threshold"].iloc[0])
    return [
        {
            "policy_id": "no_alert_baseline",
            "display_name": "No alert baseline",
            "description": "Never alerts; used only as a cost-simulation reference.",
            "series": pd.Series(False, index=spc.index),
        },
        {
            "policy_id": "spc_only",
            "display_name": "SPC-only torque rule",
            "description": "Single-sensor torque control-limit alert.",
            "series": spc["torque_beyond_control_limit"].astype(bool),
        },
        {
            "policy_id": "xgboost_default",
            "display_name": "XGBoost default threshold",
            "description": "XGBoost probability at default 0.50 threshold.",
            "series": spc["xgboost_probability"] >= 0.50,
        },
        {
            "policy_id": "xgboost_tuned_threshold",
            "display_name": "XGBoost tuned threshold",
            "description": f"XGBoost probability at F1-selected threshold {selected_threshold:.2f}.",
            "series": spc["xgboost_probability"] >= selected_threshold,
        },
        {
            "policy_id": "ml_spc_combined",
            "display_name": "ML + Predictive SPC combined",
            "description": "Probability threshold or predictive SPC risk alert.",
            "series": spc["spc_risk_alert"].astype(bool),
        },
    ]


def calculate_cost(row: dict, scenario: dict) -> float:
    """Return relative operating cost units for one policy and scenario."""
    return (
        row["false_alarm_count"] * scenario["false_alarm_cost"]
        + row["missed_failure_count"] * scenario["missed_failure_cost"]
        + row["true_positive_count"] * scenario["planned_action_cost"]
    )


def build_simulation(spc: pd.DataFrame) -> pd.DataFrame:
    """Build the policy-by-scenario normalized cost simulation table."""
    y_true = spc["actual_machine_failure"].astype(int)
    base_rows = []
    for policy in build_policy_predictions(spc):
        metrics = alert_metrics(y_true, policy["series"])
        metrics.update(
            {
                "policy_id": policy["policy_id"],
                "display_name": policy["display_name"],
                "description": policy["description"],
                "actual_failure_count": int(y_true.sum()),
                "total_rows": int(len(spc)),
            }
        )
        base_rows.append(metrics)

    no_alert = next(row for row in base_rows if row["policy_id"] == "no_alert_baseline")
    rows = []
    for scenario_id, scenario in COST_SCENARIOS.items():
        no_alert_cost = calculate_cost(no_alert, scenario)
        for base_row in base_rows:
            operating_cost = calculate_cost(base_row, scenario)
            normalized_cost = operating_cost / no_alert_cost if no_alert_cost else 0.0
            simulated_delta = 1.0 - normalized_cost
            row = {
                **base_row,
                "scenario_id": scenario_id,
                "false_alarm_cost_unit": scenario["false_alarm_cost"],
                "missed_failure_cost_unit": scenario["missed_failure_cost"],
                "planned_action_cost_unit": scenario["planned_action_cost"],
                "operating_cost_units": round(float(operating_cost), 4),
                "normalized_operating_cost": round(float(normalized_cost), 4),
                "simulated_cost_delta_vs_no_alert": round(float(simulated_delta), 4),
            }
            rows.append(row)

    columns = [
        "scenario_id",
        "policy_id",
        "display_name",
        "description",
        "precision",
        "recall",
        "f1_score",
        "alert_count",
        "false_alarm_count",
        "missed_failure_count",
        "true_positive_count",
        "true_negative_count",
        "actual_failure_count",
        "total_rows",
        "false_alarm_cost_unit",
        "missed_failure_cost_unit",
        "planned_action_cost_unit",
        "operating_cost_units",
        "normalized_operating_cost",
        "simulated_cost_delta_vs_no_alert",
    ]
    simulation = pd.DataFrame(rows)[columns]
    for column in ["precision", "recall", "f1_score"]:
        simulation[column] = simulation[column].round(4)
    return simulation


def save_cost_plot(simulation: pd.DataFrame, output_path: Path) -> None:
    """Save a compact normalized-cost chart for thesis figures."""
    pivot = simulation.pivot(
        index="display_name",
        columns="scenario_id",
        values="normalized_operating_cost",
    )
    pivot = pivot[["conservative", "balanced", "high_downtime"]]
    ax = pivot.plot(kind="bar", figsize=(10.5, 6.0), width=0.78)
    ax.axhline(1.0, color="#444444", linestyle="--", linewidth=1.0)
    ax.set_ylabel("Normalized operating cost vs no-alert baseline")
    ax.set_xlabel("")
    ax.set_title("Operational Value Simulation by Alert Policy")
    ax.legend(title="Cost scenario")
    plt.xticks(rotation=25, ha="right")
    plt.tight_layout()
    plt.savefig(output_path, dpi=160)
    plt.close()


def write_summary(simulation: pd.DataFrame, output_path: Path) -> None:
    """Write a thesis-safe operational-value summary."""
    balanced = simulation[simulation["scenario_id"] == "balanced"].sort_values(
        ["normalized_operating_cost", "f1_score"], ascending=[True, False]
    )
    best = balanced.iloc[0]
    rows = [
        "# Operational Value Simulation",
        "",
        "## Scope",
        "",
        "This is a normalized cost simulation, not a real factory cost-reduction proof.",
        "The units are relative weights for false alarms, missed failures, and planned actions.",
        "",
        "## Balanced Scenario Result",
        "",
        "| Policy | Precision | Recall | F1 | Alerts | False alarms | Missed failures | Normalized cost |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for _, row in balanced.iterrows():
        rows.append(
            f"| {row['display_name']} | {row['precision']:.4f} | {row['recall']:.4f} | "
            f"{row['f1_score']:.4f} | {int(row['alert_count'])} | "
            f"{int(row['false_alarm_count'])} | {int(row['missed_failure_count'])} | "
            f"{row['normalized_operating_cost']:.4f} |"
        )
    rows.extend(
        [
            "",
            "## Presentation-Safe Conclusion",
            "",
            (
                f"In the balanced simulation, `{best['display_name']}` has the lowest normalized "
                f"operating cost ({best['normalized_operating_cost']:.4f}). This supports comparing "
                "alert-policy trade-offs, but it does not prove real downtime reduction or real "
                "maintenance-cost savings."
            ),
            "",
            "## Guardrail",
            "",
            "Do not describe this as 85% faster detection, 30% cost reduction, or validated factory ROI.",
            "",
        ]
    )
    output_path.write_text("\n".join(rows), encoding="utf-8")


def main() -> None:
    """Create thesis-safe operating-value simulation artifacts."""
    if not SPC_TIMESERIES_PATH.exists():
        raise FileNotFoundError(
            f"Missing {SPC_TIMESERIES_PATH}. Run src\\predictive_spc.py first."
        )
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    spc = pd.read_csv(SPC_TIMESERIES_PATH)
    simulation = build_simulation(spc)

    simulation.to_csv(SIMULATION_CSV, index=False, encoding="utf-8-sig")
    SIMULATION_JSON.write_text(
        json.dumps(
            {
                "scope": "normalized cost simulation only; not real factory ROI proof",
                "scenarios": COST_SCENARIOS,
                "rows": simulation.to_dict(orient="records"),
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    save_cost_plot(simulation, SIMULATION_PNG)
    write_summary(simulation, SIMULATION_MD)

    print("Operational value simulation finished successfully.")
    print(f"simulation_csv: {SIMULATION_CSV}")
    print(f"simulation_json: {SIMULATION_JSON}")
    print(f"simulation_png: {SIMULATION_PNG}")
    print(f"simulation_summary: {SIMULATION_MD}")


if __name__ == "__main__":
    main()
