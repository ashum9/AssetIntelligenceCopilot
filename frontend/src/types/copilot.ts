/**
 * Declarative Generative UI & Copilot API TypeScript Interfaces
 */

export interface CitationPill {
  citation_id: string;
  label?: string;
  uri_or_source?: string;
  snippet?: string;
}

export interface OverrideDiffBadge {
  target_id: string;
  field_label: string;
  old_value_display: string;
  new_value_display: string;
  author_name: string;
  citation_id?: string;
  reason?: string;
}

export interface ConflictAlertCard {
  severity: "CONTRADICTION" | "UNCONFIRMED_CLAIM" | "WARNING";
  title: string;
  claim_a_source: string;
  claim_a_text: string;
  claim_b_source: string;
  claim_b_text: string;
  resolution_summary: string;
  requires_confirmation: boolean;
}

export interface StatusCardSpec {
  visual_type: "status_card";
  asset_id: string;
  well_name: string;
  well_type: string;
  area_name: string;
  effective_wellhead_temp_c?: number;
  wellhead_temp_c?: number;
  effective_ambient_temp_c?: number;
  ambient_temp_c?: number;
  effective_temp_delta_c?: number;
  temp_delta_c?: number;
  required_temp_delta_c: number;
  is_producing: boolean;
  recorded_status?: string;
  recorded_status_display?: string;
  is_recorded_status_stale: boolean;
  status_badge_label: string;
  stop_reason_summary?: string;
  latest_inspection_id?: string;
  latest_inspection_date?: string;
  inspector_name?: string;
  downtime_days?: number;
}

export interface TableColumnSpec {
  key: string;
  label: string;
  align?: "left" | "center" | "right";
  format?: "text" | "number" | "currency" | "temp_c" | "badge";
}

export interface TableSpec {
  visual_type: "table";
  title: string;
  subtitle?: string;
  columns: TableColumnSpec[];
  rows: Record<string, any>[];
  footer_summary?: string;
}

export interface LineChartPoint {
  date_str?: string;
  inspection_date?: string;
  wellhead_temp_c: number;
  ambient_temp_c: number;
  temp_delta_c: number;
  is_producing: boolean;
  inspection_id?: string;
}

export interface LineChartSpec {
  visual_type: "line_chart";
  title: string;
  subtitle?: string;
  x_axis_label: string;
  y_axis_label: string;
  data_points: LineChartPoint[];
  threshold_line?: {
    label: string;
    value: number;
    color: string;
  };
  non_producing_markers: string[];
}

export interface BarSpec {
  asset_id: string;
  category: string;
  value: number;
  color?: string;
  label?: string;
}

export interface BarChartSpec {
  visual_type: "bar_chart";
  title: string;
  subtitle?: string;
  x_axis_label: string;
  y_axis_label: string;
  bars: BarSpec[];
}

export interface MapPinSpec {
  asset_id: string;
  well_name: string;
  lat: number;
  lon: number;
  date_str: string;
  volume_bbl: number;
  inspection_id: string;
  badge_color: "red" | "orange" | "yellow";
  popup_summary: string;
}

export interface MapSpec {
  visual_type: "map";
  title: string;
  subtitle?: string;
  center_lat: number;
  center_lon: number;
  zoom_level: number;
  pins: MapPinSpec[];
}

export interface HeatmapSpec {
  visual_type: "heatmap";
  title: string;
  subtitle?: string;
  rows?: string[];
  y_labels?: string[];
  columns?: string[];
  x_labels?: string[];
  data?: number[][];
  matrix?: number[][];
  row_totals?: number[];
  column_totals?: number[];
  grand_total: number;
  note?: string;
}

export interface ShortAnswerSpec {
  visual_type: "none";
  message: string;
}

export type VisualPayload =
  | StatusCardSpec
  | TableSpec
  | LineChartSpec
  | BarChartSpec
  | MapSpec
  | HeatmapSpec
  | ShortAnswerSpec;

export interface CopilotResponseEnvelope {
  markdown_answer: string;
  citations: CitationPill[];
  override_badges: OverrideDiffBadge[];
  conflict_cards: ConflictAlertCard[];
  visual_payload: VisualPayload;
  user_context: {
    user_id: string;
    user_name: string;
    session_id: string;
  };
  telemetry: {
    duration_ms: number;
  };
}

export interface UserProfile {
  user_id: string;
  user_name: string;
  role: string;
  role_display: string;
  team_id?: string;
  team_name?: string;
  initials: string;
  color_hue: number;
}
