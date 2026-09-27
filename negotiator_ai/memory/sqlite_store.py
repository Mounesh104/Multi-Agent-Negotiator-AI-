"""
sqlite_store.py — Persistent memory for NegotiatorAI using SQLite.

Schema: one table 'negotiations' keyed by business_id.
Functions: save_negotiation(record) / load_history(business_id)

Phase 3 requirement: verify save/load round-trips for a test business_id.
"""

import sqlite3
import json
import os
from datetime import datetime
from typing import List, Optional
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import SQLITE_DB_PATH


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS negotiations (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id         TEXT NOT NULL,
    session_id          TEXT,
    timestamp           TEXT NOT NULL,
    item                TEXT,
    category            TEXT,
    supplier_name       TEXT,
    quoted_price        REAL,
    quoted_price_unit   TEXT,
    counter_offer       REAL,
    counter_offer_pct   REAL,
    final_outcome       TEXT,
    tactics_used        TEXT,
    estimated_savings   REAL,
    overall_score       REAL,
    rag_mode            TEXT,
    llm_model           TEXT,
    retrieval_queries   TEXT,
    web_search_used     INTEGER DEFAULT 0
);
"""

CREATE_INDEX_SQL = "CREATE INDEX IF NOT EXISTS idx_business_id ON negotiations (business_id);"


def _get_connection() -> sqlite3.Connection:
    """Get a SQLite connection, creating the DB and table if needed."""
    os.makedirs(os.path.dirname(SQLITE_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(SQLITE_DB_PATH)
    conn.row_factory = sqlite3.Row  # rows behave like dicts
    conn.execute(CREATE_TABLE_SQL)
    conn.execute(CREATE_INDEX_SQL)
    conn.commit()
    return conn


def save_negotiation(record: dict) -> int:
    """
    Save a negotiation record to SQLite.

    Args:
        record: dict with keys matching the table schema

    Returns:
        The new row's id
    """
    conn = _get_connection()
    try:
        row = {
            "business_id": record.get("business_id", "default"),
            "session_id": record.get("session_id", ""),
            "timestamp": datetime.now().isoformat(),
            "item": record.get("item", ""),
            "category": record.get("category", ""),
            "supplier_name": record.get("supplier_name", ""),
            "quoted_price": record.get("quoted_price", 0),
            "quoted_price_unit": record.get("quoted_price_unit", ""),
            "counter_offer": record.get("counter_offer", 0),
            "counter_offer_pct": record.get("counter_offer_pct", 0),
            "final_outcome": record.get("final_outcome", ""),
            "tactics_used": record.get("tactics_used", "[]"),
            "estimated_savings": record.get("estimated_savings", 0),
            "overall_score": record.get("overall_score", 0),
            "rag_mode": record.get("rag_mode", "agentic_rag"),
            "llm_model": record.get("llm_model", ""),
            "retrieval_queries": record.get("retrieval_queries", "[]"),
            "web_search_used": 1 if record.get("web_search_used", False) else 0,
        }

        cursor = conn.execute(
            """INSERT INTO negotiations
               (business_id, session_id, timestamp, item, category, supplier_name,
                quoted_price, quoted_price_unit, counter_offer, counter_offer_pct,
                final_outcome, tactics_used, estimated_savings, overall_score,
                rag_mode, llm_model, retrieval_queries, web_search_used)
               VALUES
               (:business_id, :session_id, :timestamp, :item, :category, :supplier_name,
                :quoted_price, :quoted_price_unit, :counter_offer, :counter_offer_pct,
                :final_outcome, :tactics_used, :estimated_savings, :overall_score,
                :rag_mode, :llm_model, :retrieval_queries, :web_search_used)""",
            row,
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def load_history(business_id: str, limit: int = 20) -> List[dict]:
    """
    Load past negotiation records for a business_id.

    Args:
        business_id: The business identifier
        limit:       Max number of records to return (most recent first)

    Returns:
        List of record dicts, most recent first
    """
    conn = _get_connection()
    try:
        cursor = conn.execute(
            """SELECT * FROM negotiations
               WHERE business_id = ?
               ORDER BY timestamp DESC
               LIMIT ?""",
            (business_id, limit),
        )
        rows = cursor.fetchall()
        result = []
        for row in rows:
            d = dict(row)
            # Parse JSON fields
            try:
                d["tactics_used"] = json.loads(d.get("tactics_used", "[]"))
            except Exception:
                d["tactics_used"] = []
            try:
                d["retrieval_queries"] = json.loads(d.get("retrieval_queries", "[]"))
            except Exception:
                d["retrieval_queries"] = []
            d["web_search_used"] = bool(d.get("web_search_used", 0))
            result.append(d)
        return result
    finally:
        conn.close()


def get_all_businesses() -> List[str]:
    """Return list of all business_ids in the store."""
    conn = _get_connection()
    try:
        cursor = conn.execute("SELECT DISTINCT business_id FROM negotiations ORDER BY business_id")
        return [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()


def get_summary_stats(business_id: str) -> dict:
    """Return summary statistics for the history dashboard."""
    conn = _get_connection()
    try:
        cursor = conn.execute(
            """SELECT
                COUNT(*) as total_deals,
                SUM(estimated_savings) as total_savings,
                AVG(overall_score) as avg_score,
                AVG(counter_offer_pct) as avg_discount_pct
               FROM negotiations WHERE business_id = ?""",
            (business_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else {}
    finally:
        conn.close()


def update_final_outcome(record_id: int, outcome: str, actual_savings: float = 0) -> None:
    """Update the final outcome of a negotiation after the real conversation."""
    conn = _get_connection()
    try:
        conn.execute(
            "UPDATE negotiations SET final_outcome = ?, estimated_savings = ? WHERE id = ?",
            (outcome, actual_savings, record_id),
        )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# CLI test — verify round-trip
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("Testing SQLite memory store...")

    test_record = {
        "business_id": "test_business_001",
        "session_id": "sess_abc",
        "item": "Corrugated packaging boxes",
        "category": "packaging",
        "supplier_name": "ABC Packaging Co.",
        "quoted_price": 500.0,
        "quoted_price_unit": "per unit",
        "counter_offer": 440.0,
        "counter_offer_pct": 88.0,
        "final_outcome": "settled at 455",
        "tactics_used": json.dumps(["bulk discount", "competing quote", "loyalty"]),
        "estimated_savings": 2250.0,
        "overall_score": 4.0,
        "rag_mode": "agentic_rag",
        "llm_model": "gpt-4o-mini",
        "retrieval_queries": json.dumps(["packaging bulk discount", "loyalty repeat customer"]),
        "web_search_used": False,
    }

    # Save
    new_id = save_negotiation(test_record)
    print(f"  ✅ Saved record with id={new_id}")

    # Load
    history = load_history("test_business_001")
    print(f"  ✅ Loaded {len(history)} records for test_business_001")
    if history:
        r = history[0]
        print(f"  First record: item={r['item']}, counter_pct={r['counter_offer_pct']}%, savings={r['estimated_savings']}")
        print(f"  Tactics: {r['tactics_used']}")

    # Stats
    stats = get_summary_stats("test_business_001")
    print(f"  Stats: {stats}")

    print("\n✅ SQLite memory store round-trip test passed.")
