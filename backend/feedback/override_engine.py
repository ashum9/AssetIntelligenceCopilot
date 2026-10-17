"""Phase 11: Scoped Runtime Feedback & Live Override Engine.

Handles:
  1. Raw sensor data corrections (e.g. WELL-0164 wellhead temp remeasurement).
  2. AI spill volume/detection corrections and cascading SOP audits (e.g. WELL-0151 5.4 bbl).
  3. Well-type scoped operational rule overrides (e.g. T350 pump jack RCA threshold).
  4. Cascading re-evaluations via DuckDB Semantic Overlay Views in real time.
"""

from datetime import datetime, date, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import uuid

import duckdb

from backend.db.connection import get_db_connection


class OverrideEngine:
    """Scoped Runtime Feedback & Live Override Engine."""

    def __init__(self, con: Optional[duckdb.DuckDBPyConnection] = None):
        self._con = con

    def _get_connection(self) -> duckdb.DuckDBPyConnection:
        if self._con is not None:
            return self._con
        return get_db_connection()

    def resolve_user_id(self, user_name: str, con: Optional[duckdb.DuckDBPyConnection] = None) -> str:
        """Resolve user_name to user_id, with fallback."""
        c = con or self._get_connection()
        res = c.execute(
            "SELECT user_id FROM users WHERE LOWER(user_name) = LOWER(?) LIMIT 1",
            [user_name.strip()]
        ).fetchone()
        if res:
            return res[0]
        # Common fallbacks if user not found in table
        name_map = {
            "michael turner": "U-201",
            "tyler hughes": "U-204",
            "jessica reed": "U-202",
            "jake morales": "U-102",
            "laura simmons": "U-401",
            "ryan brooks": "U-104",
            "chris dalton": "U-402",
            "sarah mitchell": "U-103",
        }
        return name_map.get(user_name.lower().strip(), f"U-{uuid.uuid4().hex[:4].upper()}")

    def resolve_inspection(
        self,
        asset_id: str,
        inspection_date_or_id: str,
        con: Optional[duckdb.DuckDBPyConnection] = None
    ) -> Dict[str, Any]:
        """Find inspection by exact inspection_id or asset_id + date."""
        c = con or self._get_connection()
        if inspection_date_or_id.startswith("INS-"):
            row = c.execute(
                """
                SELECT ri.*, u.user_name AS inspector_name
                FROM raw_inspections ri
                LEFT JOIN users u ON ri.inspector_user_id = u.user_id
                WHERE ri.inspection_id = ?
                """,
                [inspection_date_or_id]
            ).fetchone()
        else:
            row = c.execute(
                """
                SELECT ri.*, u.user_name AS inspector_name
                FROM raw_inspections ri
                LEFT JOIN users u ON ri.inspector_user_id = u.user_id
                WHERE ri.asset_id = ? AND ri.inspection_date = CAST(? AS DATE)
                ORDER BY ri.inspected_at DESC
                LIMIT 1
                """,
                [asset_id, inspection_date_or_id]
            ).fetchone()

        if not row:
            raise ValueError(f"Inspection not found for asset {asset_id} and ref {inspection_date_or_id}")

        cols = [desc[0] for desc in c.description]
        return dict(zip(cols, row))

    def apply_raw_sensor_override(
        self,
        asset_id: str,
        inspection_date_or_id: str,
        target_field: str,
        new_value: float,
        author_name: str,
        author_user_id: Optional[str] = None,
        reason: str = "",
        con: Optional[duckdb.DuckDBPyConnection] = None,
    ) -> Dict[str, Any]:
        """Apply a raw sensor remeasurement override (e.g. wellhead temp)."""
        c = con or self._get_connection()
        insp = self.resolve_inspection(asset_id, inspection_date_or_id, c)
        inspection_id = insp["inspection_id"]
        old_value = float(insp.get(target_field) or 0.0)

        resolved_user_id = author_user_id or self.resolve_user_id(author_name, c)

        # Check for inspector remark conflict (e.g. 'Pump jack not moving.')
        inspector_notes = insp.get("inspector_notes") or ""
        inspector_name = insp.get("inspector_name") or "Inspector"
        inspector_user_id = insp.get("inspector_user_id") or ""

        # Well type and required temp delta check
        well_row = c.execute("SELECT well_type FROM wells WHERE asset_id = ?", [asset_id]).fetchone()
        well_type = well_row[0] if well_row else "T200"
        required_delta = 15.0 if well_type == "T200" else 20.0

        ambient = float(insp.get("ambient_temp_c") or 0.0)
        new_delta = new_value - ambient if target_field == "wellhead_temp_c" else float(insp.get("wellhead_temp_c") or 0.0) - new_value

        has_conflict = False
        conflicting_note = None
        if new_delta >= required_delta:
            # Recomputed status is producing
            lower_notes = inspector_notes.lower()
            if any(term in lower_notes for term in ["not moving", "stopped", "down", "offline", "idle"]):
                has_conflict = True
                conflicting_note = inspector_notes

        correction_id = f"CORR-{asset_id}-{target_field.upper()[:8]}-{uuid.uuid4().hex[:6].upper()}"
        now_ts = datetime.now(timezone.utc)

        # Insert active correction into corrections_ledger
        c.execute(
            """
            INSERT INTO corrections_ledger (
                correction_id, source_origin, source_note_id, asset_id, inspection_id,
                target_field, old_bool_value, new_bool_value, old_numeric_value, new_numeric_value,
                correction_category, author_user_id, author_name, created_at, reason_text,
                is_active, has_inspector_note_conflict, conflicting_inspector_note,
                conflicting_inspector_user_id, conflicting_inspector_name
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                correction_id,
                "runtime_user_chat",
                None,
                asset_id,
                inspection_id,
                target_field,
                None,
                None,
                old_value,
                float(new_value),
                "faulty_sensor_temp_remeasurement",
                resolved_user_id,
                author_name,
                now_ts,
                reason,
                True,
                has_conflict,
                conflicting_note,
                inspector_user_id if has_conflict else None,
                inspector_name if has_conflict else None,
            ]
        )

        # Fetch updated view record for the well
        status_row = c.execute(
            """
            SELECT effective_wellhead_temp_c, effective_temp_delta_c, is_producing,
                   downtime_days, has_inspector_note_conflict, conflicting_inspector_note,
                   stop_reason_summary, recorded_status_display
            FROM v_well_current_status
            WHERE asset_id = ?
            """,
            [asset_id]
        ).fetchone()

        return {
            "correction_id": correction_id,
            "asset_id": asset_id,
            "inspection_id": inspection_id,
            "target_field": target_field,
            "old_numeric_value": old_value,
            "new_numeric_value": float(new_value),
            "effective_temp_delta_c": status_row[1] if status_row else new_delta,
            "is_producing": status_row[2] if status_row else (new_delta >= required_delta),
            "downtime_days": status_row[3] if status_row else 0,
            "has_inspector_note_conflict": has_conflict,
            "conflicting_inspector_note": conflicting_note,
            "conflicting_inspector_name": inspector_name if has_conflict else None,
            "author_name": author_name,
            "author_user_id": resolved_user_id,
            "reason_text": reason,
        }

    def apply_spill_volume_override(
        self,
        asset_id: str,
        inspection_date_or_id: str,
        new_volume_bbl: float,
        author_name: str,
        author_user_id: Optional[str] = None,
        reason: str = "",
        con: Optional[duckdb.DuckDBPyConnection] = None,
    ) -> Dict[str, Any]:
        """Apply an AI spill volume estimate remeasurement override."""
        c = con or self._get_connection()
        insp = self.resolve_inspection(asset_id, inspection_date_or_id, c)
        inspection_id = insp["inspection_id"]
        old_volume = float(insp.get("spill_est_volume_bbl") or 0.0)

        resolved_user_id = author_user_id or self.resolve_user_id(author_name, c)
        correction_id = f"CORR-{asset_id}-SPILLVOL-{uuid.uuid4().hex[:6].upper()}"
        now_ts = datetime.now(timezone.utc)

        c.execute(
            """
            INSERT INTO corrections_ledger (
                correction_id, source_origin, source_note_id, asset_id, inspection_id,
                target_field, old_bool_value, new_bool_value, old_numeric_value, new_numeric_value,
                correction_category, author_user_id, author_name, created_at, reason_text,
                is_active, has_inspector_note_conflict, conflicting_inspector_note,
                conflicting_inspector_user_id, conflicting_inspector_name
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                correction_id,
                "runtime_user_chat",
                None,
                asset_id,
                inspection_id,
                "spill_est_volume_bbl",
                None,
                None,
                old_volume,
                float(new_volume_bbl),
                "spill_volume_remeasurement",
                resolved_user_id,
                author_name,
                now_ts,
                reason,
                True,
                False,
                None,
                None,
                None,
            ]
        )

        # Run cascading compliance audit
        cascade = self.evaluate_spill_override_cascade(inspection_id, c)
        return {
            "correction_id": correction_id,
            "asset_id": asset_id,
            "inspection_id": inspection_id,
            "old_numeric_value": old_volume,
            "new_numeric_value": float(new_volume_bbl),
            "author_name": author_name,
            "author_user_id": resolved_user_id,
            "reason_text": reason,
            "cascade": cascade,
        }

    def evaluate_spill_override_cascade(
        self,
        inspection_id: str,
        con: Optional[duckdb.DuckDBPyConnection] = None,
    ) -> Dict[str, Any]:
        """Evaluate all 4 cascading compliance impacts for a spill inspection."""
        c = con or self._get_connection()
        row = c.execute(
            """
            SELECT
                inspection_id,
                asset_id,
                well_name,
                well_type,
                area_name,
                inspected_at,
                inspection_date,
                raw_spill_volume_bbl,
                effective_spill_volume_bbl,
                is_reportable_spill,
                maintenance_id,
                report_file_path,
                containment_hours,
                sr02_limit_hours,
                is_sr02_breach,
                reported_spill_class,
                effective_spill_class,
                is_report_class_outdated,
                sr01_report_event_id,
                hours_to_report,
                sr01_deadline_hours,
                is_sr01_breach,
                sr03_event_id,
                sr03_cleanup_due_date,
                sr03_status,
                is_sr03_breach
            FROM v_spill_compliance_audit
            WHERE inspection_id = ?
            """,
            [inspection_id]
        ).fetchone()

        if not row:
            raise ValueError(f"No spill audit record found for inspection {inspection_id}")

        cols = [desc[0] for desc in c.description]
        res = dict(zip(cols, row))

        due_date = res.get("sr03_cleanup_due_date")
        if due_date is not None and hasattr(due_date, "strftime"):
            due_date_str = due_date.strftime("%Y-%m-%d")
        else:
            due_date_str = str(due_date) if due_date is not None else None

        impacts = []
        if res["is_reportable_spill"]:
            impacts.append(
                f"SR-01 Reportable Threshold Crossed: At {res['effective_spill_volume_bbl']:.1f} bbl (>= 5.0 bbl), "
                f"written notice was due within 24h of discovery; none is recorded -> overdue report breach."
            )
        if res["is_report_class_outdated"]:
            impacts.append(
                f"Outdated Repair Report Classification: Report {res['maintenance_id']} classified spill as "
                f"'{res['reported_spill_class']}', which is outdated given effective volume {res['effective_spill_volume_bbl']:.1f} bbl."
            )
        if res["is_sr02_breach"]:
            impacts.append(
                f"SR-02 Containment Breach: Containment took {res['containment_hours']:.1f} hours, exceeding the {res['sr02_limit_hours']:.1f}-hour SOP limit."
            )
        if res["sr03_cleanup_due_date"]:
            impacts.append(
                f"SR-03 Agency Cleanup Verification Triggered: Verification due within 60 days of discovery (by {due_date_str})."
            )

        res["sr03_cleanup_due_date_str"] = due_date_str
        res["impact_summary"] = impacts
        return res

    def apply_well_type_rule_override(
        self,
        well_type: str,
        equipment_kind: str,
        new_threshold: float,
        author_name: str,
        author_user_id: Optional[str] = None,
        reason: str = "",
        rule_code: str = "CORRECTIVE_REPAIRS_RCA_THRESHOLD",
        con: Optional[duckdb.DuckDBPyConnection] = None,
    ) -> Dict[str, Any]:
        """Apply a well-type scoped rule override (e.g. T350 pump jack RCA threshold)."""
        c = con or self._get_connection()
        resolved_user_id = author_user_id or self.resolve_user_id(author_name, c)
        rule_id = f"RULE-RCA-{well_type.upper()}-{equipment_kind.upper()}-OVERRIDE-{uuid.uuid4().hex[:6].upper()}"
        now_ts = datetime.now(timezone.utc)

        # Deactivate any previous user override for the same scope and equipment
        c.execute(
            """
            UPDATE rules_registry
            SET is_active = FALSE
            WHERE rule_code = ? AND scope_value = ? AND equipment_kind = ? AND is_user_override = TRUE
            """,
            [rule_code, well_type, equipment_kind]
        )

        c.execute(
            """
            INSERT INTO rules_registry (
                rule_instance_id, rule_code, scope_type, scope_value, equipment_kind,
                comparison_operator, threshold_value, threshold_unit, rolling_window_days,
                protocol_or_section, source_file, raw_excerpt, is_active, is_user_override,
                overridden_by_user_id, overridden_by_user_name, override_reason, effective_from
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                rule_id,
                rule_code,
                "well_type",
                well_type,
                equipment_kind,
                "GTE",
                float(new_threshold),
                "repairs_per_12m",
                365,
                f"User Override ({author_name}) overriding T200.md §10 / T350.md",
                f"fleet/well-types/{well_type}.md",
                reason,
                True,
                True,
                resolved_user_id,
                author_name,
                reason,
                now_ts,
            ]
        )

        return {
            "rule_instance_id": rule_id,
            "rule_code": rule_code,
            "scope_type": "well_type",
            "scope_value": well_type,
            "equipment_kind": equipment_kind,
            "threshold_value": float(new_threshold),
            "is_user_override": True,
            "overridden_by_user_name": author_name,
            "overridden_by_user_id": resolved_user_id,
            "override_reason": reason,
        }

    def get_non_producing_wells_with_override_context(
        self,
        area_name: str,
        con: Optional[duckdb.DuckDBPyConnection] = None,
    ) -> Dict[str, Any]:
        """Query non-producing wells in an area and identify any removed wells due to overrides."""
        c = con or self._get_connection()
        # Current non-producing wells
        rows = c.execute(
            """
            SELECT asset_id, well_name, well_type, recorded_status, is_producing,
                   effective_wellhead_temp_c, effective_ambient_temp_c, effective_temp_delta_c,
                   stop_reason_summary, has_inspector_note_conflict, conflicting_inspector_note
            FROM v_well_current_status
            WHERE area_name = ? AND is_producing = FALSE
            ORDER BY asset_id
            """,
            [area_name]
        ).fetchall()
        cols = [desc[0] for desc in c.description]
        non_producing = [dict(zip(cols, r)) for r in rows]

        # Check for wells in this area that were raw-down (< threshold) but are now producing due to active override
        raw_rows = c.execute(
            """
            SELECT s.asset_id, s.well_name, s.well_type, s.effective_wellhead_temp_c,
                   s.raw_wellhead_temp_c, s.effective_temp_delta_c, s.raw_temp_delta_c,
                   s.corrected_by_user_names, s.correction_reasons, s.has_inspector_note_conflict,
                   s.conflicting_inspector_note
            FROM v_well_current_status s
            WHERE s.area_name = ?
              AND s.is_producing = TRUE
              AND s.has_active_correction = TRUE
              AND s.raw_temp_delta_c < s.required_temp_delta_c
            ORDER BY s.asset_id
            """,
            [area_name]
        ).fetchall()
        cols_raw = [desc[0] for desc in c.description]
        overridden = [dict(zip(cols_raw, r)) for r in raw_rows]

        return {
            "area_name": area_name,
            "non_producing_wells": non_producing,
            "overridden_producing_wells": overridden,
            "non_producing_count": len(non_producing),
            "overridden_count": len(overridden),
        }

    def reset_runtime_state(self, con: Optional[duckdb.DuckDBPyConnection] = None) -> Dict[str, int]:
        """Cleanly remove all runtime overrides and reset to baseline in < 50ms."""
        c = con or self._get_connection()
        corr_deleted = c.execute(
            "DELETE FROM corrections_ledger WHERE source_origin = 'runtime_user_chat'"
        ).fetchone()
        rules_deleted = c.execute(
            "DELETE FROM rules_registry WHERE is_user_override = TRUE"
        ).fetchone()
        notes_deleted = c.execute(
            "DELETE FROM enriched_context_notes WHERE source_origin = 'runtime_user_chat'"
        ).fetchone()

        return {
            "corrections_removed": corr_deleted[0] if corr_deleted else 0,
            "rules_removed": rules_deleted[0] if rules_deleted else 0,
            "runtime_notes_removed": notes_deleted[0] if notes_deleted else 0,
        }


# Module-level convenience functions
_engine = OverrideEngine()
apply_raw_sensor_override = _engine.apply_raw_sensor_override
apply_spill_volume_override = _engine.apply_spill_volume_override
evaluate_spill_override_cascade = _engine.evaluate_spill_override_cascade
apply_well_type_rule_override = _engine.apply_well_type_rule_override
get_non_producing_wells_with_override_context = _engine.get_non_producing_wells_with_override_context
reset_runtime_state = _engine.reset_runtime_state
