import json
from pathlib import Path

import matplotlib

# This backend allows matplotlib to save images without opening a window.
matplotlib.use("Agg")

import matplotlib.pyplot as plt
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)


def calculate_metrics(y_true, y_pred, y_proba) -> dict:
    """Calculate metrics that are useful for imbalanced failure prediction."""
    return {
        "precision": round(float(precision_score(y_true, y_pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y_true, y_pred, zero_division=0)), 4),
        "f1_score": round(float(f1_score(y_true, y_pred, zero_division=0)), 4),
        "roc_auc": round(float(roc_auc_score(y_true, y_proba)), 4),
        "pr_auc": round(float(average_precision_score(y_true, y_proba)), 4),
    }


def save_metrics(metrics: dict, output_path: str | Path) -> None:
    """Save model scores as a JSON file."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(metrics, file, indent=2, ensure_ascii=False)


def save_confusion_matrix(results: dict, output_path: str | Path) -> None:
    """Save confusion matrices for all baseline models in one image."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    figure, axes = plt.subplots(1, len(results), figsize=(12, 5))

    if len(results) == 1:
        axes = [axes]

    for axis, (model_name, model_result) in zip(axes, results.items()):
        matrix = confusion_matrix(model_result["y_true"], model_result["y_pred"])
        display = ConfusionMatrixDisplay(confusion_matrix=matrix)
        display.plot(ax=axis, colorbar=False)
        axis.set_title(model_name.replace("_", " ").title())

    figure.suptitle("Confusion Matrix Comparison", fontsize=14)
    figure.tight_layout()
    figure.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(figure)


def save_pr_curve(results: dict, output_path: str | Path) -> None:
    """Save precision-recall curves for all baseline models in one image."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    plt.figure(figsize=(8, 6))

    for model_name, model_result in results.items():
        precision, recall, _ = precision_recall_curve(
            model_result["y_true"],
            model_result["y_proba"],
        )
        pr_auc = average_precision_score(model_result["y_true"], model_result["y_proba"])
        label = f"{model_name.replace('_', ' ').title()} (PR-AUC={pr_auc:.3f})"
        plt.plot(recall, precision, linewidth=2, label=label)

    # This dashed line shows how rare machine failures are in the test set.
    first_result = results[next(iter(results))]
    positive_rate = sum(first_result["y_true"]) / len(first_result["y_true"])
    plt.hlines(
        y=positive_rate,
        xmin=0,
        xmax=1,
        colors="gray",
        linestyles="--",
        label=f"Positive rate ({positive_rate:.3f})",
    )

    plt.xlabel("Recall")
    plt.ylabel("Precision")
    plt.title("Precision-Recall Curve Comparison")
    plt.legend()
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()
