"""SQLite persistence: schema, seed data, criteria access and run storage."""
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DB = Path(__file__).parent / "rfp.db"

SEED_CRITERIA = [
    ("Technical Capability",
     "Architecture, integrations, scalability, technical fit", 30, 10, 1),
    ("Implementation Plan",
     "Timeline, milestones, staffing, risk plan", 20, 10, 1),
    ("Commercial Value",
     "Pricing clarity, total cost, assumptions", 20, 10, 1),
    ("Security & Compliance",
     "Controls, certifications, privacy, auditability", 20, 10, 1),
    ("Support & Experience",
     "Support model, similar projects, references", 10, 10, 1),
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS evaluation_criteria (
    criterion_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL,
    description  TEXT NOT NULL,
    weight       REAL NOT NULL CHECK (weight >= 0),
    max_score    REAL NOT NULL CHECK (max_score > 0),
    is_active    INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS rfp_runs (
    rfp_run_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    status     TEXT NOT NULL,
    run_json   TEXT
);
CREATE TABLE IF NOT EXISTS supplier_results (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    rfp_run_id        TEXT NOT NULL REFERENCES rfp_runs(rfp_run_id),
    supplier_name     TEXT NOT NULL,
    submission_date   TEXT,
    experience_rating REAL,
    absolute_score    REAL,
    ppi               REAL,
    final_rank        INTEGER,
    result_json       TEXT NOT NULL
);
"""


@contextmanager
def connect(db_path=None):
    """Open a connection, commit on success / roll back on error, and always close it."""
    conn = sqlite3.connect(str(db_path or DEFAULT_DB))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path=None, reset=False):
    """Create tables and seed the sample criteria if the table is empty."""
    path = Path(db_path or DEFAULT_DB)
    if reset and path.exists():
        path.unlink()
    with connect(path) as conn:
        conn.executescript(SCHEMA)
        count = conn.execute("SELECT COUNT(*) FROM evaluation_criteria").fetchone()[0]
        if count == 0:
            conn.executemany(
                "INSERT INTO evaluation_criteria (name, description, weight, max_score, is_active)"
                " VALUES (?, ?, ?, ?, ?)", SEED_CRITERIA)
    return path


def get_criteria(db_path=None, active_only=True):
    sql = "SELECT * FROM evaluation_criteria"
    if active_only:
        sql += " WHERE is_active = 1"
    sql += " ORDER BY criterion_id"
    with connect(db_path) as conn:
        return [dict(r) for r in conn.execute(sql).fetchall()]


def update_criteria(rows, db_path=None):
    """rows: list of dicts with criterion_id, weight, max_score, is_active."""
    with connect(db_path) as conn:
        for r in rows:
            conn.execute(
                "UPDATE evaluation_criteria SET weight=?, max_score=?, is_active=? WHERE criterion_id=?",
                (float(r["weight"]), float(r["max_score"]), 1 if r["is_active"] else 0,
                 int(r["criterion_id"])))


def new_run_id():
    now = datetime.now(timezone.utc)
    return f"RFP-{now:%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6].upper()}"


def create_run(db_path=None):
    run_id = new_run_id()
    created = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with connect(db_path) as conn:
        conn.execute("INSERT INTO rfp_runs (rfp_run_id, created_at, status) VALUES (?, ?, ?)",
                     (run_id, created, "running"))
    return run_id, created


def save_run(payload, db_path=None):
    """Persist the complete result of a run under its single RFP_RUN_ID (one transaction)."""
    run_meta = {k: v for k, v in payload.items() if k != "suppliers"}
    with connect(db_path) as conn:
        conn.execute("UPDATE rfp_runs SET status=?, run_json=? WHERE rfp_run_id=?",
                     (payload["status"], json.dumps(run_meta), payload["rfp_run_id"]))
        conn.execute("DELETE FROM supplier_results WHERE rfp_run_id=?", (payload["rfp_run_id"],))
        for s in payload["suppliers"]:
            conn.execute(
                "INSERT INTO supplier_results (rfp_run_id, supplier_name, submission_date,"
                " experience_rating, absolute_score, ppi, final_rank, result_json)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (payload["rfp_run_id"], s["supplier_name"], s["submission_date"],
                 s["experience_rating"], s["absolute_score"], s["ppi"], s["rank"],
                 json.dumps(s)))


def mark_run_failed(run_id, message, db_path=None):
    with connect(db_path) as conn:
        conn.execute("UPDATE rfp_runs SET status=?, run_json=? WHERE rfp_run_id=?",
                     ("failed", json.dumps({"error": message}), run_id))


def list_runs(db_path=None):
    with connect(db_path) as conn:
        return [dict(r) for r in conn.execute(
            "SELECT rfp_run_id, created_at, status FROM rfp_runs ORDER BY created_at DESC")]


def load_run(run_id, db_path=None):
    with connect(db_path) as conn:
        run = conn.execute("SELECT * FROM rfp_runs WHERE rfp_run_id=?", (run_id,)).fetchone()
        if run is None or not run["run_json"]:
            return None
        payload = json.loads(run["run_json"])
        if "error" in payload:
            return payload
        rows = conn.execute(
            "SELECT result_json FROM supplier_results WHERE rfp_run_id=? ORDER BY final_rank",
            (run_id,)).fetchall()
    payload["suppliers"] = [json.loads(r["result_json"]) for r in rows]
    return payload
