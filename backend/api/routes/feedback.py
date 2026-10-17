"""Runtime overrides and state feedback API routes."""

import time
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import duckdb

from backend.db.connection import get_db
from backend.feedback.override_engine import OverrideEngine, reset_runtime_state


router = APIRouter(prefix="/api/feedback", tags=["Feedback & Overrides"])


class OverrideRequest(BaseModel):
    author_name: str
    target_type: str  # "sensor", "spill", "rule", "claim"
    target_id: str    # e.g. "WELL-0164", "INS-0151-0201", "T350 pump_jack"
    new_value: Any
    reason: Optional[str] = "Operator runtime override via Copilot UI"


@router.post("/reset")
def reset_state(con: duckdb.DuckDBPyConnection = Depends(get_db)) -> Dict[str, Any]:
    """Cleanly purge runtime user overrides and restore baseline state in < 50ms."""
    t0 = time.perf_counter()
    res = reset_runtime_state(con)
    duration_ms = round((time.perf_counter() - t0) * 1000.0, 2)

    return {
        "status": "success",
        "message": "Runtime state reset to baseline.",
        "details": res,
        "duration_ms": duration_ms,
    }


@router.get("/active")
def get_active_overrides(con: duckdb.DuckDBPyConnection = Depends(get_db)) -> Dict[str, Any]:
    """Retrieve all currently active runtime overrides and rules."""
    corr_rows = con.execute(
        """
        SELECT
            correction_id, asset_id, inspection_id, target_field,
            old_numeric_value, new_numeric_value, author_name,
            correction_category, created_at, reason_text,
            has_inspector_note_conflict, conflicting_inspector_note,
            source_origin
        FROM corrections_ledger
        WHERE source_origin = 'runtime_user_chat' AND is_active = TRUE
        ORDER BY created_at DESC
        """
    ).fetchall()

    rule_rows = con.execute(
        """
        SELECT
            rule_instance_id, rule_code, scope_type, scope_value,
            equipment_kind, threshold_value, threshold_unit,
            overridden_by_user_id, override_reason, effective_from
        FROM rules_registry
        WHERE is_user_override = TRUE
        ORDER BY effective_from DESC
        """
    ).fetchall()

    overrides_list = []
    for r in corr_rows:
        overrides_list.append({
            "target_id": r[1],
            "field_name": r[3],
            "old_value": r[4],
            "new_value": r[5],
            "author_name": r[6],
            "source_origin": r[12] if len(r) > 12 else "runtime_user_chat",
        })
    for r in rule_rows:
        overrides_list.append({
            "target_id": f"{r[1]} ({r[3]})",
            "field_name": r[4],
            "old_value": "-",
            "new_value": f"{r[5]} {r[6]}",
            "author_name": r[7] or "Operator",
            "source_origin": "rule_override",
        })

    return {
        "overrides": overrides_list,
        "active_sensor_corrections": [
            {
                "correction_id": r[0],
                "asset_id": r[1],
                "inspection_id": r[2],
                "field": r[3],
                "old_value": r[4],
                "new_value": r[5],
                "author": r[6],
                "category": r[7],
                "created_at": str(r[8]),
                "reason": r[9],
                "has_conflict": bool(r[10]),
                "conflicting_note": r[11],
            }
            for r in corr_rows
        ],
        "active_rule_overrides": [
            {
                "rule_id": r[1],
                "well_type": r[3],
                "equipment_kind": r[4],
                "parameter": r[1],
                "baseline_value": r[5],
                "effective_value": r[5],
                "unit": r[6],
                "overridden_by": r[7],
                "reason": r[8],
                "overridden_at": str(r[9]),
            }
            for r in rule_rows
        ],
    }


@router.post("/override")
def create_override(req: OverrideRequest, con: duckdb.DuckDBPyConnection = Depends(get_db)) -> Dict[str, Any]:
    """Apply a runtime override for sensor readings, spill volumes, or equipment rules."""
    engine = OverrideEngine(con=con)
    try:
        if req.target_type == "sensor":
            # e.g. target_id = WELL-0164, new_value = 41.0
            res = engine.apply_raw_sensor_override(
                asset_id=req.target_id,
                inspection_date_or_id="2026-10-15",
                target_field="wellhead_temp_c",
                new_value=float(req.new_value),
                author_name=req.author_name,
                reason=req.reason or "",
                con=con,
            )
            return {"status": "success", "result": res}
        elif req.target_type == "spill":
            # e.g. target_id = WELL-0151, new_value = 5.4
            res = engine.apply_spill_volume_override(
                asset_id=req.target_id,
                inspection_date_or_id="2026-09-24",
                new_volume_bbl=float(req.new_value),
                author_name=req.author_name,
                reason=req.reason or "",
                con=con,
            )
            return {"status": "success", "result": res}
        elif req.target_type == "rule":
            # e.g. target_id = T350, new_value = 2.0
            res = engine.apply_well_type_rule_override(
                well_type=req.target_id,
                equipment_kind="pump_jack",
                parameter_name="CORRECTIVE_REPAIRS_RCA_THRESHOLD",
                new_value=float(req.new_value),
                author_name=req.author_name,
                reason=req.reason or "",
                con=con,
            )
            return {"status": "success", "result": res}
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported target_type: {req.target_type}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
