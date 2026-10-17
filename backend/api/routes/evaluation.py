"""Evaluation benchmarks API routes."""

import json
from pathlib import Path
from typing import Dict, Any
from fastapi import APIRouter, HTTPException

from backend.evaluation.part_a2_b_runner import run_full_18_evaluation


router = APIRouter(prefix="/api/evaluation", tags=["Evaluation"])


@router.get("/report")
def get_evaluation_report() -> Dict[str, Any]:
    """Retrieve the cached 18-scenario verification report."""
    report_path = Path("artifacts/phase14_full_18_evaluation_report.json")
    if not report_path.exists():
        # Generate it if not present
        return run_full_18_evaluation(report_path=str(report_path))

    try:
        with open(report_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read evaluation report: {e}")


@router.post("/run")
def trigger_evaluation_run() -> Dict[str, Any]:
    """Execute live 18-scenario evaluation benchmark and generate fresh report."""
    report_path = Path("artifacts/phase14_full_18_evaluation_report.json")
    report = run_full_18_evaluation(report_path=str(report_path))
    return {
        "status": "success",
        "summary": report.get("summary", {}),
        "report": report,
    }
