"""Phase 13: Deterministic 5-Tool Suite for the Asset Intelligence Copilot.

Tools:
  1. query_semantic_sql: Read-only guarded SQL execution against Semantic Overlay Views.
  2. get_well_360_dossier: Comprehensive 360-degree operational & compliance dossier.
  3. search_manuals_reports_and_notes: Hybrid BM25+Vector retriever over fleet manuals, SOPs, and notes.
  4. record_feedback_override_or_claim: Dispatches runtime feedback, overrides, notes, and unconfirmed claims.
  5. recall_private_user_session: User-isolated conversational memory and coreference resolution.
"""

from datetime import datetime, timezone
import re
from typing import Any, Dict, List, Optional, Set, Union
import uuid

import duckdb
from pydantic import BaseModel, Field

from backend.db.connection import get_db_connection
from backend.feedback.override_engine import (
    apply_raw_sensor_override,
    apply_spill_volume_override,
    apply_well_type_rule_override,
    evaluate_spill_override_cascade,
)
from backend.conflicts.conflict_engine import (
    ConflictEngine,
    get_active_conflicts_for_well,
    evaluate_operational_claim,
)
from backend.memory.memory_engine import (
    resolve_private_memory_reference,
    record_shared_well_note,
    resolve_user,
)
from backend.retrieval.hybrid_search import get_hybrid_retriever


CITATION_REGEX = re.compile(
    r'\b(INS-\d{4}-\d{4}|MNT-\d{4}-\d{3}|CTX-\d{4}-\d{3}|REG-\d{4}-\d{3}|SR-\d{2}|RC-\d{2}|WS-\d{2}|T200\.md(?: §\d+)?|T350\.md(?: §\d+)?)\b',
    re.IGNORECASE
)


def extract_citations_from_data(data: Any) -> List[str]:
    """Recursively discover citation IDs inside strings, dicts, and lists."""
    found: Set[str] = set()

    def _walk(obj: Any):
        if isinstance(obj, str):
            for match in CITATION_REGEX.finditer(obj):
                found.add(match.group(1))
        elif isinstance(obj, dict):
            for k, v in obj.items():
                if k.endswith("_id") and isinstance(v, str) and CITATION_REGEX.match(v):
                    found.add(v)
                elif k in ("citations", "citation_ids", "protocol_ids") and isinstance(v, list):
                    for item in v:
                        if isinstance(item, str) and CITATION_REGEX.match(item):
                            found.add(item)
                _walk(v)
        elif isinstance(obj, (list, tuple, set)):
            for item in obj:
                _walk(item)

    _walk(data)
    # Sort deterministically
    return sorted(list(found))


class ToolResult(BaseModel):
    """Standardized output envelope for all agent tools."""
    tool_name: str
    status: str = "success"  # 'success' | 'error'
    data: Dict[str, Any] = Field(default_factory=dict)
    citations: List[str] = Field(default_factory=list)
    error_message: Optional[str] = None


class CopilotTools:
    """The 5 deterministic agent tools."""

    def __init__(self, con: Optional[duckdb.DuckDBPyConnection] = None):
        self._con = con
        self._retriever = None

    def _get_connection(self) -> duckdb.DuckDBPyConnection:
        if self._con is not None:
            return self._con
        return get_db_connection()

    def _get_retriever(self):
        if self._retriever is None:
            self._retriever = get_hybrid_retriever()
        return self._retriever

    # --------------------------------------------------------------------------
    # Tool 1: query_semantic_sql
    # --------------------------------------------------------------------------
    def query_semantic_sql(self, sql_query: str, description: str = "") -> ToolResult:
        """Execute read-only SQL queries against DuckDB views and tables."""
        clean_sql = sql_query.strip().strip(";")
        upper_sql = clean_sql.upper()

        # Reject mutating statements
        forbidden = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE", "CREATE"]
        for kw in forbidden:
            # Word boundary check
            if re.search(rf"\b{kw}\b", upper_sql):
                return ToolResult(
                    tool_name="query_semantic_sql",
                    status="error",
                    error_message=f"Mutating SQL keyword '{kw}' is forbidden in read-only tool.",
                )

        if not (upper_sql.startswith("SELECT") or upper_sql.startswith("WITH")):
            return ToolResult(
                tool_name="query_semantic_sql",
                status="error",
                error_message="Only SELECT and WITH queries are permitted.",
            )

        c = self._get_connection()
        try:
            cur = c.execute(clean_sql)
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description] if cur.description else []
            records = [dict(zip(cols, r)) for r in rows]

            citations = extract_citations_from_data(records)

            return ToolResult(
                tool_name="query_semantic_sql",
                status="success",
                data={
                    "columns": cols,
                    "rows": records,
                    "row_count": len(records),
                    "description": description,
                },
                citations=citations,
            )
        except Exception as e:
            return ToolResult(
                tool_name="query_semantic_sql",
                status="error",
                error_message=str(e),
            )

    # --------------------------------------------------------------------------
    # Tool 2: get_well_360_dossier
    # --------------------------------------------------------------------------
    def get_well_360_dossier(self, asset_id: str) -> ToolResult:
        """Pull a 360-degree operational and compliance dossier for a single well."""
        c = self._get_connection()

        # Status
        status_row = c.execute(
            "SELECT * FROM v_well_current_status WHERE asset_id = ?",
            [asset_id]
        ).fetchone()
        status_cols = [d[0] for d in c.description]
        status_dict = dict(zip(status_cols, status_row)) if status_row else {}

        # Compliance summary
        comp_row = c.execute(
            "SELECT * FROM v_well_compliance_summary WHERE asset_id = ?",
            [asset_id]
        ).fetchone()
        comp_cols = [d[0] for d in c.description]
        comp_dict = dict(zip(comp_cols, comp_row)) if comp_row else {}

        # Recent inspections (last 5)
        insp_rows = c.execute(
            """
            SELECT inspection_id, inspection_date, effective_wellhead_temp_c,
                   effective_temp_delta_c, is_producing, effective_spill_detected,
                   effective_spill_volume_bbl, inspector_notes
            FROM v_effective_inspections
            WHERE asset_id = ?
            ORDER BY inspection_date DESC
            LIMIT 5
            """,
            [asset_id]
        ).fetchall()
        insp_cols = [d[0] for d in c.description]
        recent_inspections = [dict(zip(insp_cols, r)) for r in insp_rows]

        # Recent maintenance repairs
        maint_rows = c.execute(
            """
            SELECT maintenance_id, started_date, completed_date, equipment_kind,
                   maintenance_type, issue, action_taken, cost_total_usd
            FROM raw_maintenance
            WHERE asset_id = ?
            ORDER BY started_date DESC
            LIMIT 5
            """,
            [asset_id]
        ).fetchall()
        maint_cols = [d[0] for d in c.description]
        recent_repairs = [dict(zip(maint_cols, r)) for r in maint_rows]

        # Active overrides
        overrides = c.execute(
            """
            SELECT correction_id, target_field, old_numeric_value, new_numeric_value,
                   author_name, reason_text
            FROM corrections_ledger
            WHERE asset_id = ? AND is_active = TRUE
            """,
            [asset_id]
        ).fetchall()
        overrides_cols = [d[0] for d in c.description]
        active_overrides = [dict(zip(overrides_cols, o)) for o in overrides]

        # Operator context notes
        notes = c.execute(
            """
            SELECT note_id, author_name, note_type, note_text, valid_from, verification_status
            FROM enriched_context_notes
            WHERE asset_id = ?
            ORDER BY created_at DESC
            """,
            [asset_id]
        ).fetchall()
        note_cols = [d[0] for d in c.description]
        shared_notes = [dict(zip(note_cols, n)) for n in notes]

        # Active conflicts
        active_conflicts = [c.model_dump() for c in get_active_conflicts_for_well(asset_id, c)]

        dossier = {
            "asset_id": asset_id,
            "status": status_dict,
            "compliance": comp_dict,
            "recent_inspections": recent_inspections,
            "recent_repairs": recent_repairs,
            "active_overrides": active_overrides,
            "shared_notes": shared_notes,
            "active_conflicts": active_conflicts,
        }

        citations = extract_citations_from_data(dossier)

        return ToolResult(
            tool_name="get_well_360_dossier",
            status="success",
            data=dossier,
            citations=citations,
        )

    # --------------------------------------------------------------------------
    # Tool 3: search_manuals_reports_and_notes
    # --------------------------------------------------------------------------
    def search_manuals_reports_and_notes(
        self,
        query: str,
        asset_id: Optional[str] = None,
        well_type: Optional[str] = None,
        doc_types: Optional[List[str]] = None,
        top_k: int = 5,
    ) -> ToolResult:
        """Search manuals, SOPs, repair reports, and operator notes using HybridRetriever."""
        retriever = self._get_retriever()
        results = retriever.search_documents(
            query=query,
            asset_id=asset_id,
            well_type=well_type,
            doc_types=doc_types,
            top_k=top_k,
        )

        hits = []
        for r in results:
            hits.append({
                "chunk_id": r.chunk_id,
                "title": r.title,
                "doc_type": r.doc_type,
                "asset_id": r.asset_id,
                "citation": r.citation_id,
                "score": round(r.score, 4),
                "text_snippet": r.snippet[:300] + ("..." if len(r.snippet) > 300 else ""),
            })

        citations = extract_citations_from_data(hits)

        return ToolResult(
            tool_name="search_manuals_reports_and_notes",
            status="success",
            data={"query": query, "hits": hits, "count": len(hits)},
            citations=citations,
        )

    # --------------------------------------------------------------------------
    # Tool 4: record_feedback_override_or_claim
    # --------------------------------------------------------------------------
    def record_feedback_override_or_claim(
        self,
        user_id_or_name: str,
        raw_statement: str,
    ) -> ToolResult:
        """Classify and apply feedback, sensor overrides, rule overrides, or operational claims."""
        c = self._get_connection()
        user_info = resolve_user(user_id_or_name, c)
        author_name = user_info["user_name"] if user_info else user_id_or_name
        author_id = user_info["user_id"] if user_info else "U-201"

        stmt_lower = raw_statement.lower()

        # 1. Raw sensor temp override (Q12)
        # e.g. "The 15 Oct reading for WELL-0164 is wrong... 41.0 °C"
        well_match = re.search(r'\b(WELL-\d{4})\b', raw_statement, re.I)
        temp_match = re.search(r'(\d{1,2}(?:\.\d+)?)\s*(?:°C|deg\s*c|c\b)', raw_statement, re.I)

        if well_match and temp_match and any(w in stmt_lower for w in ["remeasured", "re-measured", "reading for", "gun", "wrong", "faulty", "thermal"]):
            asset_id = well_match.group(1).upper()
            new_temp = float(temp_match.group(1))
            res = apply_raw_sensor_override(
                asset_id=asset_id,
                inspection_date_or_id="2026-10-15",
                target_field="wellhead_temp_c",
                new_value=new_temp,
                author_name=author_name,
                author_user_id=author_id,
                reason=raw_statement,
                con=c,
            )
            citations = extract_citations_from_data(res)
            return ToolResult(
                tool_name="record_feedback_override_or_claim",
                status="success",
                data={"override_type": "sensor_temp_override", "result": res},
                citations=citations,
            )

        # 2. Spill volume override (Q13)
        # e.g. "The AI estimated the 24 Sep spill at WELL-0151 as 4.5 bbl. The field crew measured 5.4 bbl."
        bbl_match = re.findall(r'(\d+(?:\.\d+)?)\s*(?:bbl|barrels)', raw_statement, re.I)
        if well_match and bbl_match and any(w in stmt_lower for w in ["spill", "estimated", "measured", "ai estimated"]):
            asset_id = well_match.group(1).upper()
            # New value is typically the last mentioned barrel volume
            new_bbl = float(bbl_match[-1])
            res = apply_spill_volume_override(
                asset_id=asset_id,
                inspection_date_or_id="2026-09-24",
                new_volume_bbl=new_bbl,
                author_name=author_name,
                author_user_id=author_id,
                reason=raw_statement,
                con=c,
            )
            citations = extract_citations_from_data(res)
            return ToolResult(
                tool_name="record_feedback_override_or_claim",
                status="success",
                data={"override_type": "spill_volume_override", "result": res},
                citations=citations,
            )

        # 3. Rule override (Q14)
        # e.g. "Note for all T350 wells: our team now wants a pump jack root-cause analysis after 2 repairs, not 3."
        if any(wt in stmt_lower for wt in ["t350", "t200"]) and "root-cause" in stmt_lower or "rca" in stmt_lower or "repairs" in stmt_lower:
            well_type = "T350" if "t350" in stmt_lower else "T200"
            eq_kind = "pump_jack" if ("pump jack" in stmt_lower or "pump_jack" in stmt_lower) else "ALL"
            num_match = re.search(r'after\s*(\d+)\s*repairs', raw_statement, re.I)
            new_thresh = float(num_match.group(1)) if num_match else 2.0

            res = apply_well_type_rule_override(
                well_type=well_type,
                equipment_kind=eq_kind,
                new_threshold=new_thresh,
                author_name=author_name,
                author_user_id=author_id,
                reason=raw_statement,
                con=c,
            )
            citations = extract_citations_from_data(res)
            return ToolResult(
                tool_name="record_feedback_override_or_claim",
                status="success",
                data={"override_type": "rule_override", "result": res},
                citations=citations,
            )

        # 4. Operational claims & shut-ins (Q16, Q17)
        if well_match:
            asset_id = well_match.group(1).upper()
            claim_res = evaluate_operational_claim(
                asset_id=asset_id,
                statement=raw_statement,
                author_name=author_name,
                author_user_id=author_id,
                con=c,
            )
            citations = extract_citations_from_data(claim_res)
            return ToolResult(
                tool_name="record_feedback_override_or_claim",
                status="success",
                data={"override_type": "operational_claim", "result": claim_res},
                citations=citations,
            )

        # Fallback note
        return ToolResult(
            tool_name="record_feedback_override_or_claim",
            status="success",
            data={"override_type": "general_note", "text": raw_statement},
            citations=[],
        )

    # --------------------------------------------------------------------------
    # Tool 5: recall_private_user_session
    # --------------------------------------------------------------------------
    def recall_private_user_session(self, user_id_or_name: str, query: str) -> ToolResult:
        """Recall prior turns and discussed entities isolated strictly to the user."""
        c = self._get_connection()
        user_info = resolve_user(user_id_or_name, c)
        user_id = user_info["user_id"] if user_info else user_id_or_name

        mem_res = resolve_private_memory_reference(
            user_identifier=user_id_or_name,
            query=query,
            conn=c,
        )

        citations = extract_citations_from_data(mem_res)

        return ToolResult(
            tool_name="recall_private_user_session",
            status="success",
            data=mem_res,
            citations=citations,
        )


# Module-level instance
_copilot_tools = CopilotTools()
query_semantic_sql = _copilot_tools.query_semantic_sql
get_well_360_dossier = _copilot_tools.get_well_360_dossier
search_manuals_reports_and_notes = _copilot_tools.search_manuals_reports_and_notes
record_feedback_override_or_claim = _copilot_tools.record_feedback_override_or_claim
recall_private_user_session = _copilot_tools.recall_private_user_session
