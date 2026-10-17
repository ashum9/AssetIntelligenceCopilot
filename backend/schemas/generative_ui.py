"""Phase 15: Declarative Generative UI Component Schemas.

Implements Requirement #1: A copilot chat UI with generative UI (OpenUI / A2UI pattern).
Defines schemas for:
  - StatusCardSpec (visual_type = "status_card")
  - TableSpec (visual_type = "table")
  - LineChartSpec (visual_type = "line_chart")
  - BarChartSpec (visual_type = "bar_chart")
  - MapSpec (visual_type = "map")
  - HeatmapSpec (visual_type = "heatmap")
  - ShortAnswerSpec (visual_type = "none")
Along with first-class primitives:
  - OverrideDiffBadge (data provenance)
  - ConflictAlertCard (conflict / dispute notification)
  - CitationPill (clickable evidence citation)
"""

from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field


class CitationPill(BaseModel):
    """Clickable evidence citation pill."""
    citation_id: str
    source_type: str = "document"  # inspection, maintenance, note, rule, sop
    source_file: Optional[str] = None
    label: str = ""
    excerpt: Optional[str] = None


class OverrideDiffBadge(BaseModel):
    """Data provenance diff badge showing original vs corrected values."""
    target_id: str
    field_label: str
    old_value_display: str
    new_value_display: str
    author_name: str
    citation_id: str
    reason: str


class ConflictAlertCard(BaseModel):
    """Visual conflict / contradiction card in the chat interface."""
    severity: Literal["WARNING", "DISPUTE", "UNCONFIRMED_CLAIM"] = "WARNING"
    title: str
    claim_a_source: str
    claim_a_text: str
    claim_b_source: str
    claim_b_text: str
    resolution_summary: str
    requires_confirmation: bool = False


class StatusCardSpec(BaseModel):
    """Visual status card for a single well."""
    visual_type: Literal["status_card"] = "status_card"
    asset_id: str
    well_name: str
    well_type: str
    area_name: str
    team_name: Optional[str] = None
    is_producing: bool
    status_badge_label: Literal["PRODUCING", "SHUT-IN (PLANNED)", "DOWN (OPEN REPAIR)", "DOWN (UNEXPLAINED)"]
    recorded_status_display: str
    is_recorded_status_stale: bool
    latest_inspection_id: Optional[str] = None
    latest_inspection_date: Optional[str] = None
    inspector_name: Optional[str] = None
    inspection_method: Optional[str] = None
    wellhead_temp_c: Optional[float] = None
    ambient_temp_c: Optional[float] = None
    temp_delta_c: Optional[float] = None
    required_temp_delta_c: float = 15.0
    temp_rule_citation: Optional[str] = None
    stop_reason_summary: Optional[str] = None
    active_note_or_repair_id: Optional[str] = None
    thermal_preview_meta: Dict[str, Any] = Field(default_factory=dict)


class TableColumnSpec(BaseModel):
    """Column definition for interactive table."""
    key: str
    label: str
    align: Literal["left", "center", "right"] = "left"
    format: Optional[str] = None  # currency, number, date, badge


class TableSpec(BaseModel):
    """Interactive table for multi-entity lists."""
    visual_type: Literal["table"] = "table"
    title: str
    subtitle: Optional[str] = None
    columns: List[TableColumnSpec]
    rows: List[Dict[str, Any]]
    footer_summary: Optional[str] = None


class LineChartSpec(BaseModel):
    """Line chart for temporal change over time."""
    visual_type: Literal["line_chart"] = "line_chart"
    title: str
    subtitle: Optional[str] = None
    x_axis_key: str = "inspection_date"
    y_axis_unit: str = "°C"
    series: List[str] = Field(default_factory=lambda: ["wellhead_temp_c", "ambient_temp_c", "temp_delta_c"])
    threshold_line: Optional[Dict[str, Any]] = None
    non_producing_markers: List[str] = Field(default_factory=list)
    data_points: List[Dict[str, Any]] = Field(default_factory=list)


class BarChartBarSpec(BaseModel):
    """Individual bar item in a bar chart."""
    asset_id: str
    well_type: Optional[str] = None
    value: float
    label: str
    highlight: bool = False


class BarChartSpec(BaseModel):
    """Bar chart for comparing metrics across wells or areas."""
    visual_type: Literal["bar_chart"] = "bar_chart"
    title: str
    subtitle: Optional[str] = None
    x_axis_key: str = "asset_id"
    y_axis_key: str = "value"
    y_axis_unit: str = "days"
    bars: List[BarChartBarSpec] = Field(default_factory=list)


class MapPinSpec(BaseModel):
    """Pin on the geographic map."""
    asset_id: str
    well_name: str
    lat: float
    lon: float
    date_str: str
    volume_bbl: float
    inspection_id: str
    badge_color: str = "red"
    popup_summary: str = ""


class MapSpec(BaseModel):
    """Geographic map showing well locations and spill pins."""
    visual_type: Literal["map"] = "map"
    title: str
    subtitle: Optional[str] = None
    center_lat: float
    center_lon: float
    zoom_level: int = 12
    pins: List[MapPinSpec] = Field(default_factory=list)


class HeatmapSpec(BaseModel):
    """Two-dimensional matrix heatmap (e.g. Area x Month)."""
    visual_type: Literal["heatmap"] = "heatmap"
    title: str
    subtitle: Optional[str] = None
    x_labels: List[str] = Field(default_factory=list)
    y_labels: List[str] = Field(default_factory=list)
    matrix: List[List[int]] = Field(default_factory=list)
    row_totals: List[int] = Field(default_factory=list)
    grand_total: int = 0
    note: Optional[str] = None


class ShortAnswerSpec(BaseModel):
    """Lightweight response when no visual is requested or needed."""
    visual_type: Literal["none"] = "none"
    message: str = ""


GenerativeUIPayload = Union[
    StatusCardSpec,
    TableSpec,
    LineChartSpec,
    BarChartSpec,
    MapSpec,
    HeatmapSpec,
    ShortAnswerSpec,
]


class CopilotResponseEnvelope(BaseModel):
    """Unified response envelope returned by CopilotOrchestrator."""
    markdown_answer: str
    citations: List[CitationPill] = Field(default_factory=list)
    override_badges: List[OverrideDiffBadge] = Field(default_factory=list)
    conflict_cards: List[ConflictAlertCard] = Field(default_factory=list)
    visual_payload: GenerativeUIPayload = Field(default_factory=ShortAnswerSpec)
    user_context: Dict[str, Any] = Field(default_factory=dict)
    telemetry: Dict[str, Any] = Field(default_factory=dict)
