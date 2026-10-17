"""Fleet wells API routes."""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
import duckdb

from backend.db.connection import get_db
from backend.agent.tools import CopilotTools


router = APIRouter(prefix="/api/wells", tags=["Wells"])


class WellSummary(BaseModel):
    asset_id: str
    well_name: str
    area_name: str
    well_type: str
    is_producing: bool
    recorded_status: str
    effective_temp_delta_c: float
    latest_inspection_date: str
    inspector_name: str
    lat: float
    lon: float


@router.get("", response_model=List[WellSummary])
def get_wells(
    area: Optional[str] = Query(None, description="Filter by operational area"),
    well_type: Optional[str] = Query(None, description="Filter by well type (T200, T350)"),
    producing_only: Optional[bool] = Query(None, description="Filter by producing status"),
    limit: int = Query(200, ge=1, le=500),
    con: duckdb.DuckDBPyConnection = Depends(get_db),
) -> List[WellSummary]:
    """Retrieve summary status for wells across the fleet."""
    query = """
        SELECT
            asset_id,
            well_name,
            area_name,
            well_type,
            is_producing,
            recorded_status,
            effective_temp_delta_c,
            inspection_date,
            inspector_name,
            lat,
            lon
        FROM v_well_current_status
        WHERE 1=1
    """
    params: List[Any] = []

    if area:
        query += " AND area_name = ?"
        params.append(area)
    if well_type:
        query += " AND well_type = ?"
        params.append(well_type)
    if producing_only is not None:
        query += " AND is_producing = ?"
        params.append(producing_only)

    query += " ORDER BY asset_id ASC LIMIT ?"
    params.append(limit)

    rows = con.execute(query, params).fetchall()

    return [
        WellSummary(
            asset_id=r[0],
            well_name=r[1],
            area_name=r[2],
            well_type=r[3],
            is_producing=bool(r[4]),
            recorded_status=r[5],
            effective_temp_delta_c=round(float(r[6]), 2),
            latest_inspection_date=str(r[7]),
            inspector_name=r[8],
            lat=float(r[9]),
            lon=float(r[10]),
        )
        for r in rows
    ]


@router.get("/{well_id}")
def get_well_dossier(well_id: str) -> Dict[str, Any]:
    """Retrieve the complete 360-degree operational and compliance dossier for a single well."""
    tools = CopilotTools()
    clean_id = well_id.strip().upper()
    res = tools.get_well_360_dossier(clean_id)

    if res.status != "success":
        raise HTTPException(status_code=404, detail=f"Well dossier for '{well_id}' could not be loaded: {res.error_message}")

    return {
        "status": "success",
        "asset_id": clean_id,
        "dossier": res.data,
        "citations": res.citations,
    }
