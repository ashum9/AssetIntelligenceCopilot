"""Database schema DDL definitions for Phases 2 through 5."""

import duckdb

# ==============================================================================
# Phase 2: Raw Ingestion Tables
# ==============================================================================

DDL_AREAS = """
CREATE TABLE IF NOT EXISTS areas (
    area_id VARCHAR PRIMARY KEY,
    area_name VARCHAR NOT NULL,
    team_id VARCHAR NOT NULL,
    center_lat DOUBLE NOT NULL,
    center_lon DOUBLE NOT NULL,
    expected_well_count INTEGER NOT NULL
);
"""

DDL_TEAMS = """
CREATE TABLE IF NOT EXISTS teams (
    team_id VARCHAR PRIMARY KEY,
    team_name VARCHAR NOT NULL,
    lead_user_id VARCHAR NOT NULL
);
"""

DDL_USERS = """
CREATE TABLE IF NOT EXISTS users (
    user_id VARCHAR PRIMARY KEY,
    user_name VARCHAR NOT NULL,
    role VARCHAR NOT NULL,
    team_id VARCHAR
);
"""

DDL_WELLS = """
CREATE TABLE IF NOT EXISTS wells (
    asset_id VARCHAR PRIMARY KEY,
    well_name VARCHAR NOT NULL,
    asset_category VARCHAR NOT NULL,
    well_type VARCHAR NOT NULL,
    area_id VARCHAR NOT NULL,
    team_id VARCHAR NOT NULL,
    in_charge_user_id VARCHAR NOT NULL,
    lat DOUBLE NOT NULL,
    lon DOUBLE NOT NULL,
    installed_on DATE NOT NULL,
    recorded_status VARCHAR NOT NULL,
    meta_last_inspection_id VARCHAR,
    meta_last_inspected_at TIMESTAMP,
    meta_last_inspector_user_id VARCHAR,
    status VARCHAR,
    decommissioned_on DATE
);
"""

DDL_WELL_EQUIPMENT = """
CREATE TABLE IF NOT EXISTS well_equipment (
    equipment_id VARCHAR PRIMARY KEY,
    asset_id VARCHAR NOT NULL,
    equipment_kind VARCHAR NOT NULL,
    model VARCHAR NOT NULL
);
"""

DDL_RAW_INSPECTIONS = """
CREATE TABLE IF NOT EXISTS raw_inspections (
    inspection_id VARCHAR PRIMARY KEY,
    asset_id VARCHAR NOT NULL,
    inspected_at TIMESTAMP NOT NULL,
    inspection_date DATE NOT NULL,
    inspector_user_id VARCHAR NOT NULL,
    method VARCHAR NOT NULL,
    ambient_temp_c DOUBLE NOT NULL,
    wellhead_temp_c DOUBLE NOT NULL,
    raw_temp_delta_c DOUBLE NOT NULL,
    spill_detected BOOLEAN NOT NULL,
    spill_area_pct DOUBLE,
    spill_est_volume_bbl DOUBLE,
    evidence_images_json VARCHAR,
    inspector_notes VARCHAR
);
"""

DDL_RAW_MAINTENANCE = """
CREATE TABLE IF NOT EXISTS raw_maintenance (
    maintenance_id VARCHAR PRIMARY KEY,
    asset_id VARCHAR NOT NULL,
    started_at TIMESTAMP NOT NULL,
    started_date DATE NOT NULL,
    completed_at TIMESTAMP,
    completed_date DATE,
    is_open_as_of_today BOOLEAN NOT NULL,
    maintenance_type VARCHAR NOT NULL,
    equipment_kind VARCHAR NOT NULL,
    issue VARCHAR,
    action_taken VARCHAR,
    technician_user_id VARCHAR,
    contractor VARCHAR,
    downtime_hours DOUBLE,
    cost_labor_usd DOUBLE,
    cost_parts_usd DOUBLE,
    cost_total_usd DOUBLE NOT NULL,
    triggered_by_inspection_id VARCHAR,
    report_file VARCHAR,
    resolved_report_path VARCHAR
);
"""

DDL_RAW_REGULATORY_EVENTS = """
CREATE TABLE IF NOT EXISTS raw_regulatory_events (
    event_id VARCHAR PRIMARY KEY,
    asset_id VARCHAR NOT NULL,
    event_date DATE NOT NULL,
    agency VARCHAR NOT NULL,
    event_type VARCHAR NOT NULL,
    protocol_id VARCHAR,
    related_inspection_id VARCHAR,
    hours_to_report DOUBLE,
    detail VARCHAR,
    fine_usd DOUBLE DEFAULT 0.0,
    status VARCHAR NOT NULL
);
"""

DDL_RAW_CONTEXT_NOTES = """
CREATE TABLE IF NOT EXISTS raw_context_notes (
    note_id VARCHAR PRIMARY KEY,
    asset_id VARCHAR NOT NULL,
    created_at TIMESTAMP NOT NULL,
    created_date DATE NOT NULL,
    author_user_id VARCHAR NOT NULL,
    note_type VARCHAR NOT NULL,
    inspection_id VARCHAR,
    note_text VARCHAR NOT NULL,
    valid_from DATE,
    valid_to DATE,
    field VARCHAR,
    original_value DOUBLE,
    corrected_value DOUBLE
);
"""

DDL_INGESTION_MANIFEST = """
CREATE TABLE IF NOT EXISTS ingestion_manifest (
    manifest_id VARCHAR PRIMARY KEY,
    dataset_root VARCHAR NOT NULL,
    ingested_at TIMESTAMP NOT NULL,
    reference_today DATE NOT NULL,
    phase_completed VARCHAR NOT NULL,
    row_counts_json VARCHAR NOT NULL,
    duration_ms DOUBLE NOT NULL
);
"""

# ==============================================================================
# Phase 3: Rule Registry & SOP Protocols
# ==============================================================================

DDL_RULES_REGISTRY = """
CREATE TABLE IF NOT EXISTS rules_registry (
    rule_instance_id VARCHAR PRIMARY KEY,
    rule_code VARCHAR NOT NULL,
    scope_type VARCHAR NOT NULL,
    scope_value VARCHAR NOT NULL,
    equipment_kind VARCHAR NOT NULL,
    comparison_operator VARCHAR NOT NULL,
    threshold_value DOUBLE NOT NULL,
    threshold_unit VARCHAR NOT NULL,
    rolling_window_days INTEGER,
    protocol_or_section VARCHAR NOT NULL,
    source_file VARCHAR NOT NULL,
    raw_excerpt VARCHAR NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_user_override BOOLEAN NOT NULL DEFAULT FALSE,
    overridden_by_user_id VARCHAR,
    overridden_by_user_name VARCHAR,
    override_reason VARCHAR,
    effective_from TIMESTAMP NOT NULL
);
"""

DDL_SOP_PROTOCOLS = """
CREATE TABLE IF NOT EXISTS sop_protocols (
    protocol_id VARCHAR PRIMARY KEY,
    title VARCHAR NOT NULL,
    category VARCHAR NOT NULL,
    applies_to_well_type VARCHAR NOT NULL,
    spill_class_name VARCHAR,
    min_volume_bbl DOUBLE,
    max_volume_bbl DOUBLE,
    deadline_hours DOUBLE,
    deadline_days DOUBLE,
    source_file VARCHAR NOT NULL,
    section_heading VARCHAR NOT NULL,
    full_section_markdown VARCHAR NOT NULL
);
"""

# ==============================================================================
# Phase 4: Parsed Repair Reports
# ==============================================================================

DDL_PARSED_REPAIR_REPORTS = """
CREATE TABLE IF NOT EXISTS parsed_repair_reports (
    maintenance_id VARCHAR PRIMARY KEY,
    asset_id VARCHAR NOT NULL,
    triggered_by_inspection_id VARCHAR,
    report_file_path VARCHAR NOT NULL,
    report_date DATE,
    section_what_happened VARCHAR,
    section_root_cause VARCHAR,
    section_safety_steps VARCHAR,
    section_work_done VARCHAR,
    section_tests VARCHAR,
    section_cleanup VARCHAR,
    section_parts_and_cost VARCHAR,
    section_compliance_check VARCHAR,
    containment_hours DOUBLE,
    containment_excerpt VARCHAR,
    exceeds_sr02_limit BOOLEAN,
    reported_spill_class VARCHAR,
    reporting_duty_statement VARCHAR,
    rca_action_required BOOLEAN NOT NULL DEFAULT FALSE,
    rca_excerpt VARCHAR,
    flowline_annual_test_performed BOOLEAN NOT NULL DEFAULT FALSE,
    referenced_protocol_ids_json VARCHAR,
    installed_parts_model VARCHAR,
    installed_parts_serial VARCHAR,
    installed_parts_lot VARCHAR,
    follow_up_days INTEGER,
    follow_up_text VARCHAR,
    full_markdown_text VARCHAR NOT NULL
);
"""

# ==============================================================================
# Phase 5: Corrections Ledger & Enriched Context Notes
# ==============================================================================

DDL_CORRECTIONS_LEDGER = """
CREATE TABLE IF NOT EXISTS corrections_ledger (
    correction_id VARCHAR PRIMARY KEY,
    source_origin VARCHAR NOT NULL,
    source_note_id VARCHAR,
    asset_id VARCHAR NOT NULL,
    inspection_id VARCHAR NOT NULL,
    target_field VARCHAR NOT NULL,
    old_bool_value BOOLEAN,
    new_bool_value BOOLEAN,
    old_numeric_value DOUBLE,
    new_numeric_value DOUBLE,
    correction_category VARCHAR NOT NULL,
    author_user_id VARCHAR NOT NULL,
    author_name VARCHAR NOT NULL,
    created_at TIMESTAMP NOT NULL,
    reason_text VARCHAR NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    has_inspector_note_conflict BOOLEAN NOT NULL DEFAULT FALSE,
    conflicting_inspector_note VARCHAR,
    conflicting_inspector_user_id VARCHAR,
    conflicting_inspector_name VARCHAR
);
"""

DDL_ENRICHED_CONTEXT_NOTES = """
CREATE TABLE IF NOT EXISTS enriched_context_notes (
    note_id VARCHAR PRIMARY KEY,
    source_origin VARCHAR NOT NULL,
    asset_id VARCHAR NOT NULL,
    inspection_id VARCHAR,
    author_user_id VARCHAR NOT NULL,
    author_name VARCHAR NOT NULL,
    author_role VARCHAR,
    created_at TIMESTAMP NOT NULL,
    note_type VARCHAR NOT NULL,
    note_text VARCHAR NOT NULL,
    valid_from DATE,
    valid_to DATE,
    is_planned_shutin BOOLEAN NOT NULL DEFAULT FALSE,
    mentioned_equipment_kind VARCHAR,
    is_logged_in_maintenance BOOLEAN,
    has_peer_disagreement BOOLEAN NOT NULL DEFAULT FALSE,
    peer_disagreement_note_ids_json VARCHAR,
    contradicts_sensor_data BOOLEAN NOT NULL DEFAULT FALSE,
    verification_status VARCHAR NOT NULL DEFAULT 'CONFIRMED'
);
"""

PHASE2_TABLES = [
    ("areas", DDL_AREAS),
    ("teams", DDL_TEAMS),
    ("users", DDL_USERS),
    ("wells", DDL_WELLS),
    ("well_equipment", DDL_WELL_EQUIPMENT),
    ("raw_inspections", DDL_RAW_INSPECTIONS),
    ("raw_maintenance", DDL_RAW_MAINTENANCE),
    ("raw_regulatory_events", DDL_RAW_REGULATORY_EVENTS),
    ("raw_context_notes", DDL_RAW_CONTEXT_NOTES),
    ("ingestion_manifest", DDL_INGESTION_MANIFEST),
]

PHASE3_TABLES = [
    ("rules_registry", DDL_RULES_REGISTRY),
    ("sop_protocols", DDL_SOP_PROTOCOLS),
]

PHASE4_TABLES = [
    ("parsed_repair_reports", DDL_PARSED_REPAIR_REPORTS),
]

PHASE5_TABLES = [
    ("corrections_ledger", DDL_CORRECTIONS_LEDGER),
    ("enriched_context_notes", DDL_ENRICHED_CONTEXT_NOTES),
]

ALL_TABLES = PHASE2_TABLES + PHASE3_TABLES + PHASE4_TABLES + PHASE5_TABLES


def init_database_schema(
    con: duckdb.DuckDBPyConnection,
    drop_existing: bool = False,
    phases: Optional[list] = None,
) -> None:
    """Create database tables. If drop_existing is True, drop them first."""
    tables_to_create = []
    if phases is None:
        tables_to_create = ALL_TABLES
    else:
        if 2 in phases:
            tables_to_create.extend(PHASE2_TABLES)
        if 3 in phases:
            tables_to_create.extend(PHASE3_TABLES)
        if 4 in phases:
            tables_to_create.extend(PHASE4_TABLES)
        if 5 in phases:
            tables_to_create.extend(PHASE5_TABLES)

    for table_name, ddl in tables_to_create:
        if drop_existing:
            con.execute(f"DROP TABLE IF EXISTS {table_name}")
        con.execute(ddl)
