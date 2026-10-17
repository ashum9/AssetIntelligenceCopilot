"""Pydantic models for Phase 1 forensic audit data structures."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DatasetSummary(BaseModel):
    """Fleet-wide entity and record counts."""
    total_areas: int
    total_teams: int
    total_users: int
    total_wells: int
    wells_per_area: Dict[str, int]
    total_inspections: int
    total_maintenance: int
    maintenance_scheduled: int
    maintenance_corrective: int
    total_repair_reports: int
    total_regulatory_events: int
    total_context_notes: int
    total_correction_notes: int
    date_ranges: Dict[str, Dict[str, str]]
    open_repairs_count: int


class FieldSchema(BaseModel):
    """Schema descriptor for a field."""
    field_name: str
    inferred_type: str
    nullable: bool
    sample_value: Optional[Any] = None
    description: Optional[str] = None


class FileSchemaDescriptor(BaseModel):
    """Schema definition for a data file type."""
    file_type: str
    file_format: str
    root_container: str
    fields: List[FieldSchema]
    sample_record: Dict[str, Any]


class CorrectionRecord(BaseModel):
    """A formal correction note paired with its target inspection."""
    asset_id: str
    note_id: str
    author_user_id: str
    created_at: str
    note_type: str
    inspection_id: Optional[str]
    text: str
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None
    target_inspection: Optional[Dict[str, Any]] = None
    correction_category: str = "ai_spill_false_positive"


class MultiNoteInspection(BaseModel):
    """An inspection referenced by multiple context notes."""
    asset_id: str
    inspection_id: str
    notes: List[Dict[str, Any]]


class CalibrationAnchorReport(BaseModel):
    """Audit results for a single calibration anchor."""
    anchor_id: int
    scenario_ref: str
    well_id: Optional[str] = None
    description: str
    passed: bool
    details: Dict[str, Any]


class Phase1AuditReport(BaseModel):
    """Complete machine-readable Phase 1 Audit Manifest."""
    audit_timestamp: str
    reference_today: str
    dataset_summary: DatasetSummary
    schemas: Dict[str, FileSchemaDescriptor]
    enumerations: Dict[str, Dict[str, int]]
    manuals_and_sops_verbatim: Dict[str, str]
    discovered_rules: Dict[str, Any]
    all_correction_notes: List[CorrectionRecord]
    multi_note_inspections: List[MultiNoteInspection]
    repair_report_structure: Dict[str, Any]
    calibration_anchors: List[CalibrationAnchorReport]
