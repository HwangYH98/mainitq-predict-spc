import json
import sqlite3
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "outputs"
DEFAULT_DB_PATH = OUTPUT_DIR / "operations.db"


def json_dumps(value: Any) -> str:
    """Serialize values consistently for SQLite JSON text columns."""
    return json.dumps(value, ensure_ascii=False, default=str)


def connect(db_path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Open the local PoC operations database."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_db(db_path: str | Path = DEFAULT_DB_PATH) -> None:
    """Create SQLite tables for prediction events, drafts, decisions, and audits."""
    with connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS prediction_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT UNIQUE NOT NULL,
                source TEXT NOT NULL,
                created_at TEXT NOT NULL,
                model_name TEXT NOT NULL,
                probability REAL NOT NULL,
                threshold REAL NOT NULL,
                risk_status TEXT NOT NULL,
                input_json TEXT NOT NULL,
                shap_json TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS work_order_decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                decision_id TEXT UNIQUE NOT NULL,
                draft_id TEXT NOT NULL,
                event_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                operator_id TEXT NOT NULL,
                decision TEXT NOT NULL,
                note TEXT NOT NULL,
                decision_json TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS work_order_drafts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                draft_id TEXT UNIQUE NOT NULL,
                event_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                generation_mode TEXT NOT NULL,
                draft_json TEXT NOT NULL,
                markdown TEXT NOT NULL,
                draft_path TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                audit_id TEXT UNIQUE NOT NULL,
                created_at TEXT NOT NULL,
                actor_id TEXT NOT NULL,
                role TEXT NOT NULL,
                action TEXT NOT NULL,
                status TEXT NOT NULL,
                target_type TEXT NOT NULL,
                target_id TEXT NOT NULL,
                detail_json TEXT NOT NULL,
                error_message TEXT NOT NULL
            )
            """
        )


def insert_prediction_event(event: dict, db_path: str | Path = DEFAULT_DB_PATH) -> None:
    """Save one prediction event into the local operations database."""
    initialize_db(db_path)
    with connect(db_path) as connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO prediction_events (
                event_id, source, created_at, model_name, probability, threshold,
                risk_status, input_json, shap_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event["event_id"],
                event["source"],
                event["created_at"],
                event["model_name"],
                float(event["probability"]),
                float(event["threshold"]),
                event["risk_status"],
                json_dumps(event.get("input", {})),
                json_dumps(event.get("top_shap_factors", [])),
            ),
        )


def insert_work_order_draft(draft: dict, db_path: str | Path = DEFAULT_DB_PATH) -> None:
    """Save one human-approved work-order draft into SQLite."""
    initialize_db(db_path)
    with connect(db_path) as connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO work_order_drafts (
                draft_id, event_id, created_at, generation_mode, draft_json,
                markdown, draft_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                draft["draft_id"],
                draft["event_id"],
                draft["created_at"],
                draft["generation_mode"],
                json_dumps(draft["draft_json"]),
                draft["markdown"],
                draft["draft_path"],
            ),
        )


def insert_work_order_decision(decision: dict, db_path: str | Path = DEFAULT_DB_PATH) -> None:
    """Save one operator decision for a work-order draft into SQLite."""
    initialize_db(db_path)
    with connect(db_path) as connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO work_order_decisions (
                decision_id, draft_id, event_id, created_at, operator_id,
                decision, note, decision_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                decision["decision_id"],
                decision["draft_id"],
                decision["event_id"],
                decision["created_at"],
                decision["operator_id"],
                decision["decision"],
                decision["note"],
                json_dumps(decision),
            ),
        )


def row_to_event(row: sqlite3.Row) -> dict:
    """Convert a SQLite row into a dashboard/API friendly dictionary."""
    return {
        "event_id": row["event_id"],
        "source": row["source"],
        "created_at": row["created_at"],
        "model_name": row["model_name"],
        "probability": float(row["probability"]),
        "threshold": float(row["threshold"]),
        "risk_status": row["risk_status"],
        "input": json.loads(row["input_json"]),
        "top_shap_factors": json.loads(row["shap_json"]),
    }


def list_prediction_events(
    limit: int = 50,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> list[dict]:
    """Return recent prediction events for the operations dashboard/API."""
    initialize_db(db_path)
    with connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT * FROM prediction_events
            ORDER BY id DESC
            LIMIT ?
            """,
            (int(limit),),
        ).fetchall()
    return [row_to_event(row) for row in rows]


def get_prediction_event(
    event_id: str,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> dict | None:
    """Find one prediction event by id."""
    initialize_db(db_path)
    with connect(db_path) as connection:
        row = connection.execute(
            "SELECT * FROM prediction_events WHERE event_id = ?",
            (event_id,),
        ).fetchone()
    return row_to_event(row) if row is not None else None


def get_work_order_draft(
    draft_id: str,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> dict | None:
    """Find one work-order draft by id."""
    initialize_db(db_path)
    with connect(db_path) as connection:
        row = connection.execute(
            "SELECT * FROM work_order_drafts WHERE draft_id = ?",
            (draft_id,),
        ).fetchone()
    if row is None:
        return None
    return {
        "draft_id": row["draft_id"],
        "event_id": row["event_id"],
        "created_at": row["created_at"],
        "generation_mode": row["generation_mode"],
        "draft_json": json.loads(row["draft_json"]),
        "markdown": row["markdown"],
        "draft_path": row["draft_path"],
    }


def list_work_order_drafts(
    limit: int = 50,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> list[dict]:
    """Return recent generated work-order drafts."""
    initialize_db(db_path)
    with connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT * FROM work_order_drafts
            ORDER BY id DESC
            LIMIT ?
            """,
            (int(limit),),
        ).fetchall()

    drafts = []
    for row in rows:
        drafts.append(
            {
                "draft_id": row["draft_id"],
                "event_id": row["event_id"],
                "created_at": row["created_at"],
                "generation_mode": row["generation_mode"],
                "draft_json": json.loads(row["draft_json"]),
                "markdown": row["markdown"],
                "draft_path": row["draft_path"],
            }
        )
    return drafts


def row_to_decision(row: sqlite3.Row) -> dict:
    """Convert a SQLite decision row into a dashboard/API friendly dictionary."""
    decision_json = json.loads(row["decision_json"])
    decision_json.update(
        {
            "decision_id": row["decision_id"],
            "draft_id": row["draft_id"],
            "event_id": row["event_id"],
            "created_at": row["created_at"],
            "operator_id": row["operator_id"],
            "decision": row["decision"],
            "note": row["note"],
        }
    )
    return decision_json


def list_work_order_decisions(
    limit: int = 50,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> list[dict]:
    """Return recent operator decisions for work-order drafts."""
    initialize_db(db_path)
    with connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT * FROM work_order_decisions
            ORDER BY id DESC
            LIMIT ?
            """,
            (int(limit),),
        ).fetchall()
    return [row_to_decision(row) for row in rows]


def insert_audit_log(entry: dict, db_path: str | Path = DEFAULT_DB_PATH) -> None:
    """Append one audit log row for product MVP traceability."""
    initialize_db(db_path)
    with connect(db_path) as connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO audit_logs (
                audit_id, created_at, actor_id, role, action, status,
                target_type, target_id, detail_json, error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry["audit_id"],
                entry["created_at"],
                entry.get("actor_id", ""),
                entry.get("role", ""),
                entry["action"],
                entry["status"],
                entry.get("target_type", ""),
                entry.get("target_id", ""),
                json_dumps(entry.get("detail", {})),
                entry.get("error_message", ""),
            ),
        )


def row_to_audit_log(row: sqlite3.Row) -> dict:
    """Convert an audit row into a dashboard/API friendly dictionary."""
    return {
        "audit_id": row["audit_id"],
        "created_at": row["created_at"],
        "actor_id": row["actor_id"],
        "role": row["role"],
        "action": row["action"],
        "status": row["status"],
        "target_type": row["target_type"],
        "target_id": row["target_id"],
        "detail": json.loads(row["detail_json"]),
        "error_message": row["error_message"],
    }


def list_audit_logs(
    limit: int = 100,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> list[dict]:
    """Return recent audit logs for the admin console."""
    initialize_db(db_path)
    with connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT * FROM audit_logs
            ORDER BY id DESC
            LIMIT ?
            """,
            (int(limit),),
        ).fetchall()
    return [row_to_audit_log(row) for row in rows]
