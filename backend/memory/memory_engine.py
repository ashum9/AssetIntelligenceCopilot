"""Phase 10: Two-Level Memory Engine & Context Window Manager.

Implements Requirement #3:
  1. Private User Memory: Session-isolated conversational memory, coreference resolution,
     and strict privacy guards preventing cross-user conversation leakage (Q11 & Q16).
  2. Shared Fleet Knowledge Store: Fleet-wide runtime operational notes & planned shut-in
     broadcasts persisted into enriched_context_notes with automatic duration parsing (Q16 & Q17).
  3. ContextWindowManager: Head/Tail prompt budget management and large span offloading.
  4. User resolution helper and clean runtime state reset.
"""

import json
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import duckdb

from backend.config.settings import get_settings
from backend.db.connection import get_db_connection


SQL_INIT_MEMORY_TABLES = """
CREATE TABLE IF NOT EXISTS user_sessions (
    session_id VARCHAR PRIMARY KEY,
    user_id VARCHAR NOT NULL,
    user_name VARCHAR NOT NULL,
    session_day_label VARCHAR,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS session_messages (
    message_id VARCHAR PRIMARY KEY,
    session_id VARCHAR NOT NULL,
    user_id VARCHAR NOT NULL,
    turn_index INTEGER NOT NULL,
    role VARCHAR NOT NULL,
    content VARCHAR NOT NULL,
    discussed_asset_ids_json VARCHAR,
    discussed_area_ids_json VARCHAR,
    primary_topic VARCHAR,
    visual_type VARCHAR,
    created_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS private_entity_memory (
    memory_id VARCHAR PRIMARY KEY,
    user_id VARCHAR NOT NULL,
    session_id VARCHAR NOT NULL,
    turn_index INTEGER NOT NULL,
    asset_ids_json VARCHAR NOT NULL,
    entity_count INTEGER NOT NULL,
    topic VARCHAR,
    created_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS tool_output_spans (
    span_id VARCHAR PRIMARY KEY,
    session_id VARCHAR NOT NULL,
    tool_name VARCHAR NOT NULL,
    raw_payload VARCHAR NOT NULL,
    compact_summary VARCHAR,
    created_at TIMESTAMP NOT NULL
);
"""


def init_memory_schema(
    conn: Optional[duckdb.DuckDBPyConnection] = None,
    db_path: Optional[Union[str, Path]] = None,
) -> None:
    """Initialize memory tables in DuckDB."""
    own_conn = False
    if conn is None:
        conn = get_db_connection(db_path, read_only=False)
        own_conn = True

    try:
        conn.execute(SQL_INIT_MEMORY_TABLES)
    finally:
        if own_conn:
            conn.close()


def resolve_user(
    identifier: str,
    conn: Optional[duckdb.DuckDBPyConnection] = None,
    db_path: Optional[Union[str, Path]] = None,
) -> Optional[Dict[str, Any]]:
    """Resolve a user by user_id (e.g. 'U-201') or full user_name (e.g. 'Michael Turner')."""
    own_conn = False
    if conn is None:
        conn = get_db_connection(db_path, read_only=True)
        own_conn = True

    try:
        ident_clean = identifier.strip()
        row = conn.execute("""
            SELECT user_id, user_name, role, team_id
            FROM users
            WHERE LOWER(user_id) = LOWER(?) OR LOWER(user_name) = LOWER(?)
            LIMIT 1
        """, (ident_clean, ident_clean)).fetchone()

        if row:
            return {
                "user_id": row[0],
                "user_name": row[1],
                "role": row[2],
                "team_id": row[3],
            }
        return None
    finally:
        if own_conn:
            conn.close()


def create_session(
    user_identifier: str,
    session_day_label: str = "today",
    session_id: Optional[str] = None,
    conn: Optional[duckdb.DuckDBPyConnection] = None,
    db_path: Optional[Union[str, Path]] = None,
) -> str:
    """Create a new private user session."""
    user = resolve_user(user_identifier, conn=conn, db_path=db_path)
    if not user:
        raise ValueError(f"User '{user_identifier}' not found in registry.")

    sid = session_id or f"sess_{uuid.uuid4().hex[:12]}"
    own_conn = False
    if conn is None:
        conn = get_db_connection(db_path, read_only=False)
        own_conn = True

    try:
        now = datetime.now(timezone.utc)
        conn.execute("""
            INSERT INTO user_sessions VALUES (?, ?, ?, ?, ?, ?)
        """, (
            sid,
            user["user_id"],
            user["user_name"],
            session_day_label,
            now,
            now,
        ))
        return sid
    finally:
        if own_conn:
            conn.close()


def log_turn(
    session_id: str,
    role: str,
    content: str,
    discussed_asset_ids: Optional[List[str]] = None,
    discussed_area_ids: Optional[List[str]] = None,
    primary_topic: Optional[str] = None,
    visual_type: Optional[str] = None,
    conn: Optional[duckdb.DuckDBPyConnection] = None,
    db_path: Optional[Union[str, Path]] = None,
) -> str:
    """Log a conversational turn and index entities in private memory."""
    own_conn = False
    if conn is None:
        conn = get_db_connection(db_path, read_only=False)
        own_conn = True

    try:
        sess = conn.execute("""
            SELECT user_id, user_name FROM user_sessions WHERE session_id = ?
        """, (session_id,)).fetchone()
        if not sess:
            raise ValueError(f"Session '{session_id}' not found.")

        user_id, user_name = sess

        # Compute next turn index
        t_row = conn.execute("""
            SELECT COALESCE(MAX(turn_index), 0) + 1 FROM session_messages WHERE session_id = ?
        """, (session_id,)).fetchone()
        next_turn = t_row[0] if t_row else 1

        msg_id = f"msg_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)
        assets_json = json.dumps(discussed_asset_ids) if discussed_asset_ids else None
        areas_json = json.dumps(discussed_area_ids) if discussed_area_ids else None

        conn.execute("""
            INSERT INTO session_messages VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            msg_id,
            session_id,
            user_id,
            next_turn,
            role,
            content,
            assets_json,
            areas_json,
            primary_topic,
            visual_type,
            now,
        ))

        # If entities were discussed, record in private_entity_memory
        if discussed_asset_ids:
            mem_id = f"mem_{uuid.uuid4().hex[:12]}"
            conn.execute("""
                INSERT INTO private_entity_memory VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                mem_id,
                user_id,
                session_id,
                next_turn,
                json.dumps(discussed_asset_ids),
                len(discussed_asset_ids),
                primary_topic,
                now,
            ))

        return msg_id
    finally:
        if own_conn:
            conn.close()


def resolve_private_memory_reference(
    user_identifier: str,
    query: str,
    conn: Optional[duckdb.DuckDBPyConnection] = None,
    db_path: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """Resolve an ambiguous conversational back-reference strictly within the caller's private history.

    Never queries rows belonging to any other user_id.
    """
    user = resolve_user(user_identifier, conn=conn, db_path=db_path)
    if not user:
        return {
            "resolved": False,
            "privacy_guard_triggered": True,
            "asset_ids": [],
            "source_session_id": None,
            "memory_citation": None,
            "explanation": f"Unknown user '{user_identifier}'.",
        }

    caller_user_id = user["user_id"]
    caller_name = user["user_name"]

    q_lower = query.lower()
    is_back_reference = any(
        k in q_lower
        for k in [
            "discussed yesterday",
            "earlier chat",
            "past conversation",
            "three wells",
            "those wells",
            "that well",
            "we discussed",
            "last conversation",
        ]
    )

    if not is_back_reference:
        return {
            "resolved": False,
            "privacy_guard_triggered": False,
            "asset_ids": [],
            "source_session_id": None,
            "memory_citation": None,
            "explanation": "No conversational back-reference detected.",
        }

    own_conn = False
    if conn is None:
        conn = get_db_connection(db_path, read_only=True)
        own_conn = True

    try:
        # Strictly query private_entity_memory for caller_user_id ONLY
        rows = conn.execute("""
            SELECT session_id, asset_ids_json, entity_count, topic, created_at
            FROM private_entity_memory
            WHERE user_id = ?
            ORDER BY created_at DESC
        """, (caller_user_id,)).fetchall()

        if not rows:
            return {
                "resolved": False,
                "privacy_guard_triggered": True,
                "asset_ids": [],
                "source_session_id": None,
                "memory_citation": None,
                "explanation": f"No prior conversation discussing those wells was found for user {caller_name}.",
            }

        # Look for entity count match (e.g. 'three wells' -> entity_count = 3)
        target_count = None
        if "three wells" in q_lower or "3 wells" in q_lower:
            target_count = 3

        selected_row = None
        if target_count:
            for r in rows:
                if r[2] == target_count:
                    selected_row = r
                    break
            if not selected_row:
                return {
                    "resolved": False,
                    "privacy_guard_triggered": True,
                    "asset_ids": [],
                    "source_session_id": None,
                    "memory_citation": None,
                    "explanation": f"No prior conversation discussing {target_count} wells was found for user {caller_name}.",
                }

        if not selected_row:
            selected_row = rows[0]

        session_id, assets_json, cnt, topic, dt = selected_row
        asset_ids = json.loads(assets_json)

        return {
            "resolved": True,
            "privacy_guard_triggered": False,
            "asset_ids": asset_ids,
            "source_session_id": session_id,
            "memory_citation": f"Recalled from {caller_name}'s prior session ({session_id})",
            "explanation": f"Found {len(asset_ids)} wells ({', '.join(asset_ids)}) previously discussed by {caller_name}.",
        }
    finally:
        if own_conn:
            conn.close()


def calculate_ytd_repair_costs(
    asset_ids: List[str],
    year: int = 2026,
    conn: Optional[duckdb.DuckDBPyConnection] = None,
    db_path: Optional[Union[str, Path]] = None,
) -> Dict[str, float]:
    """Compute year-to-date total maintenance costs for a given list of wells."""
    if not asset_ids:
        return {}

    own_conn = False
    if conn is None:
        conn = get_db_connection(db_path, read_only=True)
        own_conn = True

    try:
        placeholders = ", ".join(["?"] * len(asset_ids))
        start_date = f"{year}-01-01"
        end_date = f"{year}-10-17"

        q = f"""
            SELECT asset_id, COALESCE(SUM(cost_total_usd), 0.0) AS total_cost
            FROM raw_maintenance
            WHERE asset_id IN ({placeholders})
              AND started_date >= DATE '{start_date}'
              AND started_date <= DATE '{end_date}'
            GROUP BY asset_id
        """
        rows = conn.execute(q, asset_ids).fetchall()
        costs = {r[0]: float(r[1]) for r in rows}
        for aid in asset_ids:
            if aid not in costs:
                costs[aid] = 0.0
        return costs
    finally:
        if own_conn:
            conn.close()


def record_shared_well_note(
    author_identifier: str,
    asset_id: str,
    note_text: str,
    valid_from: Optional[date] = None,
    valid_to: Optional[date] = None,
    is_planned_shutin: bool = False,
    conn: Optional[duckdb.DuckDBPyConnection] = None,
    db_path: Optional[Union[str, Path]] = None,
) -> str:
    """Record a fleet-wide operational note or planned shut-in broadcast into enriched_context_notes."""
    user = resolve_user(author_identifier, conn=conn, db_path=db_path)
    author_id = user["user_id"] if user else "UNKNOWN"
    author_name = user["user_name"] if user else author_identifier
    author_role = user["role"] if user else "operator"

    # Automatic parsing for dates and durations if not provided
    # e.g., "from 17 Oct for a 10-day planned workover"
    if valid_from is None:
        m_from = re.search(r"from\s+(\d{1,2})\s+([A-Za-z]{3})", note_text, re.IGNORECASE)
        if m_from:
            day = int(m_from.group(1))
            month_str = m_from.group(2).lower()
            months = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
                      "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}
            m_num = months.get(month_str[:3], 10)
            valid_from = date(2026, m_num, day)

    if valid_to is None and valid_from is not None:
        m_dur = re.search(r"(\d+)[-\s]day", note_text, re.IGNORECASE)
        if m_dur:
            days = int(m_dur.group(1))
            valid_to = valid_from + timedelta(days=days)

    if "shut in" in note_text.lower() or "workover" in note_text.lower() or "planned" in note_text.lower():
        is_planned_shutin = True

    note_id = f"CTX-RUNTIME-{uuid.uuid4().hex[:8].upper()}"
    now = datetime.now(timezone.utc)

    own_conn = False
    if conn is None:
        conn = get_db_connection(db_path, read_only=False)
        own_conn = True

    try:
        conn.execute("""
            INSERT INTO enriched_context_notes (
                note_id, source_origin, asset_id, inspection_id, author_user_id,
                author_name, author_role, created_at, note_type, note_text,
                valid_from, valid_to, is_planned_shutin, mentioned_equipment_kind,
                is_logged_in_maintenance, has_peer_disagreement, peer_disagreement_note_ids_json,
                contradicts_sensor_data, verification_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            note_id,
            "runtime_user_chat",
            asset_id,
            None,
            author_id,
            author_name,
            author_role,
            now,
            "runtime_shared_note",
            note_text,
            valid_from,
            valid_to,
            is_planned_shutin,
            "wellhead",
            False,
            False,
            None,
            False,
            "active",
        ))
        return note_id
    finally:
        if own_conn:
            conn.close()


def get_shared_well_knowledge(
    asset_id: str,
    conn: Optional[duckdb.DuckDBPyConnection] = None,
    db_path: Optional[Union[str, Path]] = None,
) -> List[Dict[str, Any]]:
    """Retrieve all shared operational notes for an asset."""
    own_conn = False
    if conn is None:
        conn = get_db_connection(db_path, read_only=True)
        own_conn = True

    try:
        rows = conn.execute("""
            SELECT
                note_id, author_name, note_type, note_text, valid_from, valid_to, is_planned_shutin, created_at
            FROM enriched_context_notes
            WHERE asset_id = ?
            ORDER BY created_at DESC
        """, (asset_id,)).fetchall()

        cols = ["note_id", "author_name", "note_type", "note_text", "valid_from", "valid_to", "is_planned_shutin", "created_at"]
        return [dict(zip(cols, r)) for r in rows]
    finally:
        if own_conn:
            conn.close()


class ContextWindowManager:
    """Manages conversational token budget using Head + Tail preservation and span offloading."""

    def __init__(self, head_turns: int = 2, tail_turns: int = 6, max_tokens: int = 4000):
        self.head_turns = head_turns
        self.tail_turns = tail_turns
        self.max_tokens = max_tokens

    def estimate_tokens(self, text: str) -> int:
        """Heuristic token estimator (words * 1.3)."""
        return int(len(text.split()) * 1.3)

    def truncate_history(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Preserve system prompt + first N head turns + last M tail turns."""
        if not messages:
            return []

        system_msgs = [m for m in messages if m.get("role") == "system"]
        chat_msgs = [m for m in messages if m.get("role") != "system"]

        if len(chat_msgs) <= (self.head_turns + self.tail_turns):
            return messages

        head = chat_msgs[:self.head_turns]
        tail = chat_msgs[-self.tail_turns:]

        separator = {
            "role": "system",
            "content": f"[... conversation truncated: {len(chat_msgs) - (self.head_turns + self.tail_turns)} turns omitted ...]",
        }
        return system_msgs + head + [separator] + tail

    def offload_tool_span(
        self,
        session_id: str,
        tool_name: str,
        payload: Any,
        conn: Optional[duckdb.DuckDBPyConnection] = None,
        db_path: Optional[Union[str, Path]] = None,
    ) -> str:
        """Store large structured SQL/retrieval spans in DuckDB and return span ID."""
        span_id = f"span_{uuid.uuid4().hex[:12]}"
        raw_json = json.dumps(payload, default=str)
        summary = f"{tool_name} returned payload with {len(raw_json)} characters."

        own_conn = False
        if conn is None:
            conn = get_db_connection(db_path, read_only=False)
            own_conn = True

        try:
            now = datetime.now(timezone.utc)
            conn.execute("""
                INSERT INTO tool_output_spans VALUES (?, ?, ?, ?, ?, ?)
            """, (
                span_id,
                session_id,
                tool_name,
                raw_json,
                summary,
                now,
            ))
            return span_id
        finally:
            if own_conn:
                conn.close()


def reset_runtime_state(
    conn: Optional[duckdb.DuckDBPyConnection] = None,
    db_path: Optional[Union[str, Path]] = None,
) -> None:
    """Cleanly purge runtime notes and sessions while preserving baseline data."""
    own_conn = False
    if conn is None:
        conn = get_db_connection(db_path, read_only=False)
        own_conn = True

    try:
        conn.execute("DELETE FROM enriched_context_notes WHERE source_origin = 'runtime_user_chat'")
        conn.execute("DELETE FROM user_sessions")
        conn.execute("DELETE FROM session_messages")
        conn.execute("DELETE FROM private_entity_memory")
        conn.execute("DELETE FROM tool_output_spans")
    finally:
        if own_conn:
            conn.close()
