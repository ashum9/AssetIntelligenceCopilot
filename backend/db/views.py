"""Phase 6: Semantic Overlay SQL Views for DuckDB.

Creates the 5 Master Semantic Overlay Views:
  1. v_effective_inspections: Single source of truth for all 39,567 inspections,
     applying active corrections, delta T threshold comparisons, and downtime days.
  2. v_well_current_status: Right-now snapshot for all 200 wells, linking latest inspection,
     stale status flags, open maintenance work orders, and active planned shut-in notes.
  3. v_spill_compliance_audit: Comprehensive audit for all detected spills, linking containment
     hours, SR-01 reporting deadlines, SR-02 containment limit (4.0h), SR-03 cleanup verification,
     and RC-04 NOV response deadlines.
  4. v_equipment_rca_tracker: Rolling 12-month corrective repairs per equipment kind and well,
     evaluating baseline and overridden RCA thresholds.
  5. v_well_compliance_summary: 360-degree well compliance summary showing total breaches,
     open fines, pending actions (RCAs, unlogged shut-ins), and met annual integrity tests.
"""

from pathlib import Path
from typing import Optional, Union

import duckdb

from backend.config.settings import get_settings
from backend.db.connection import get_db_connection


SQL_CREATE_V_EFFECTIVE_INSPECTIONS = """
CREATE OR REPLACE VIEW v_effective_inspections AS
WITH active_corrections AS (
    SELECT
        inspection_id,
        MAX(CASE WHEN target_field = 'wellhead_temp_c' THEN new_numeric_value END) AS corr_wellhead,
        MAX(CASE WHEN target_field = 'ambient_temp_c' THEN new_numeric_value END) AS corr_ambient,
        MAX(CASE WHEN target_field = 'spill_detected' THEN new_bool_value END) AS corr_spill_bool,
        MAX(CASE WHEN target_field IN ('spill_volume_bbl', 'spill_est_volume_bbl', 'estimated_spill_volume_bbl', 'volume_bbl') THEN new_numeric_value END) AS corr_spill_vol,
        STRING_AGG(DISTINCT source_note_id, ', ') AS corr_applied_ids,
        STRING_AGG(DISTINCT author_name, ', ') AS corr_author_names,
        STRING_AGG(DISTINCT reason_text, ' | ') AS corr_reasons,
        COUNT(*) AS corr_count,
        BOOL_OR(has_inspector_note_conflict) AS corr_has_conflict,
        MAX(conflicting_inspector_note) AS corr_conflict_note
    FROM corrections_ledger
    WHERE is_active = TRUE
    GROUP BY inspection_id
),
disagreements AS (
    SELECT
        inspection_id,
        BOOL_OR(has_peer_disagreement) AS has_peer_disagreement,
        MAX(peer_disagreement_note_ids_json) AS peer_disagreement_note_ids_json
    FROM enriched_context_notes
    WHERE inspection_id IS NOT NULL
    GROUP BY inspection_id
)
SELECT
    ri.inspection_id,
    ri.asset_id,
    w.well_name,
    w.well_type,
    w.area_id,
    a.area_name,
    w.team_id,
    t.team_name,
    w.lat,
    w.lon,
    w.recorded_status,
    ri.inspected_at,
    ri.inspection_date,
    ri.inspector_user_id,
    u.user_name AS inspector_name,
    ri.method,
    ri.inspector_notes,
    ri.evidence_images_json,
    ri.ambient_temp_c AS raw_ambient_temp_c,
    COALESCE(c.corr_ambient, ri.ambient_temp_c) AS effective_ambient_temp_c,
    ri.wellhead_temp_c AS raw_wellhead_temp_c,
    COALESCE(c.corr_wellhead, ri.wellhead_temp_c) AS effective_wellhead_temp_c,
    ri.raw_temp_delta_c,
    ROUND(COALESCE(c.corr_wellhead, ri.wellhead_temp_c) - COALESCE(c.corr_ambient, ri.ambient_temp_c), 4) AS effective_temp_delta_c,
    COALESCE(rr.threshold_value, CASE WHEN w.well_type = 'T200' THEN 15.0 WHEN w.well_type = 'T350' THEN 20.0 WHEN w.well_type = 'T500' THEN 25.0 ELSE 20.0 END) AS required_temp_delta_c,
    COALESCE(rr.source_file, CASE WHEN w.well_type = 'T200' THEN 'fleet/well-types/T200.md' WHEN w.well_type = 'T350' THEN 'fleet/well-types/T350.md' ELSE 'fleet/well-types/T500.md' END) AS temp_rule_citation,
    CASE
        WHEN ROUND(COALESCE(c.corr_wellhead, ri.wellhead_temp_c) - COALESCE(c.corr_ambient, ri.ambient_temp_c), 4) >= COALESCE(rr.threshold_value, CASE WHEN w.well_type = 'T200' THEN 15.0 WHEN w.well_type = 'T350' THEN 20.0 WHEN w.well_type = 'T500' THEN 25.0 ELSE 20.0 END)
        THEN TRUE
        ELSE FALSE
    END AS is_producing,
    CASE
        WHEN ROUND(COALESCE(c.corr_wellhead, ri.wellhead_temp_c) - COALESCE(c.corr_ambient, ri.ambient_temp_c), 4) < COALESCE(rr.threshold_value, CASE WHEN w.well_type = 'T200' THEN 15.0 WHEN w.well_type = 'T350' THEN 20.0 WHEN w.well_type = 'T500' THEN 25.0 ELSE 20.0 END)
        THEN 7
        ELSE 0
    END AS downtime_days,
    ri.spill_detected AS raw_spill_detected,
    CASE
        WHEN c.corr_spill_bool IS NOT NULL THEN c.corr_spill_bool
        WHEN c.corr_spill_vol IS NOT NULL AND c.corr_spill_vol > 0 THEN TRUE
        ELSE ri.spill_detected
    END AS effective_spill_detected,
    ri.spill_est_volume_bbl AS raw_spill_volume_bbl,
    CASE
        WHEN (CASE WHEN c.corr_spill_bool IS NOT NULL THEN c.corr_spill_bool ELSE ri.spill_detected END) = FALSE THEN 0.0
        ELSE COALESCE(c.corr_spill_vol, ri.spill_est_volume_bbl, 0.0)
    END AS effective_spill_volume_bbl,
    ri.spill_area_pct,
    COALESCE(c.corr_count > 0, FALSE) AS has_active_correction,
    c.corr_applied_ids AS applied_correction_note_ids,
    c.corr_author_names AS corrected_by_user_names,
    c.corr_reasons AS correction_reasons,
    (
        COALESCE(c.corr_has_conflict, FALSE)
        OR (
            COALESCE(c.corr_count > 0, FALSE)
            AND ri.inspector_notes IS NOT NULL
            AND (
                ROUND(COALESCE(c.corr_wellhead, ri.wellhead_temp_c) - COALESCE(c.corr_ambient, ri.ambient_temp_c), 4) >= COALESCE(rr.threshold_value, CASE WHEN w.well_type = 'T200' THEN 15.0 WHEN w.well_type = 'T350' THEN 20.0 WHEN w.well_type = 'T500' THEN 25.0 ELSE 20.0 END)
            )
            AND (
                LOWER(ri.inspector_notes) LIKE '%not moving%'
                OR LOWER(ri.inspector_notes) LIKE '%stopped%'
                OR LOWER(ri.inspector_notes) LIKE '%down%'
            )
        )
    ) AS has_inspector_note_conflict,
    CASE
        WHEN (
            COALESCE(c.corr_has_conflict, FALSE)
            OR (
                COALESCE(c.corr_count > 0, FALSE)
                AND ri.inspector_notes IS NOT NULL
                AND (
                    ROUND(COALESCE(c.corr_wellhead, ri.wellhead_temp_c) - COALESCE(c.corr_ambient, ri.ambient_temp_c), 4) >= COALESCE(rr.threshold_value, CASE WHEN w.well_type = 'T200' THEN 15.0 WHEN w.well_type = 'T350' THEN 20.0 WHEN w.well_type = 'T500' THEN 25.0 ELSE 20.0 END)
                )
                AND (
                    LOWER(ri.inspector_notes) LIKE '%not moving%'
                    OR LOWER(ri.inspector_notes) LIKE '%stopped%'
                    OR LOWER(ri.inspector_notes) LIKE '%down%'
                )
            )
        ) THEN ri.inspector_notes
        ELSE NULL
    END AS conflicting_inspector_note,
    COALESCE(d.has_peer_disagreement, FALSE) AS has_peer_disagreement,
    d.peer_disagreement_note_ids_json
FROM raw_inspections ri
JOIN wells w ON ri.asset_id = w.asset_id
JOIN areas a ON w.area_id = a.area_id
JOIN teams t ON w.team_id = t.team_id
LEFT JOIN users u ON ri.inspector_user_id = u.user_id
LEFT JOIN (
    SELECT scope_value, threshold_value, source_file
    FROM rules_registry
    WHERE rule_code = 'MIN_PRODUCING_TEMP_DELTA_C' AND is_active = TRUE
) rr ON rr.scope_value = w.well_type
LEFT JOIN active_corrections c ON ri.inspection_id = c.inspection_id
LEFT JOIN disagreements d ON ri.inspection_id = d.inspection_id;
"""

SQL_CREATE_V_WELL_CURRENT_STATUS = """
CREATE OR REPLACE VIEW v_well_current_status AS
WITH latest_inspections AS (
    SELECT *
    FROM (
        SELECT *,
               ROW_NUMBER() OVER (PARTITION BY asset_id ORDER BY inspected_at DESC) as rn
        FROM v_effective_inspections
        WHERE inspection_date <= DATE '2026-10-17'
    )
    WHERE rn = 1
),
open_repairs AS (
    SELECT *
    FROM (
        SELECT
            asset_id,
            maintenance_id AS open_maintenance_id,
            started_date AS open_maintenance_started_date,
            completed_date AS open_maintenance_completed_date,
            equipment_kind AS open_maintenance_equipment,
            issue AS open_maintenance_issue,
            action_taken AS open_maintenance_action,
            ROW_NUMBER() OVER (PARTITION BY asset_id ORDER BY started_date DESC) as rn
        FROM raw_maintenance
        WHERE is_open_as_of_today = TRUE OR completed_date > DATE '2026-10-17'
    )
    WHERE rn = 1
),
active_shutins AS (
    SELECT *
    FROM (
        SELECT
            asset_id,
            note_id AS active_shutin_note_id,
            author_name AS active_shutin_author_name,
            valid_from AS active_shutin_valid_from,
            valid_to AS active_shutin_valid_to,
            mentioned_equipment_kind AS active_shutin_equipment,
            note_text AS active_shutin_text,
            is_logged_in_maintenance AS is_shutin_logged_in_maintenance,
            ROW_NUMBER() OVER (PARTITION BY asset_id ORDER BY created_at DESC) as rn
        FROM enriched_context_notes
        WHERE is_planned_shutin = TRUE
          AND valid_from <= DATE '2026-10-17'
          AND (valid_to IS NULL OR valid_to >= DATE '2026-10-15')
    )
    WHERE rn = 1
)
SELECT
    li.*,
    (
        (li.recorded_status = 'active' AND li.is_producing = FALSE)
        OR (li.recorded_status = 'down' AND li.is_producing = TRUE)
    ) AS is_recorded_status_stale,
    CASE
        WHEN (li.recorded_status = 'active' AND li.is_producing = FALSE) THEN 'active (out of date)'
        WHEN (li.recorded_status = 'down' AND li.is_producing = TRUE) THEN 'down (out of date)'
        ELSE li.recorded_status
    END AS recorded_status_display,
    m.open_maintenance_id,
    m.open_maintenance_started_date,
    m.open_maintenance_completed_date,
    m.open_maintenance_equipment,
    m.open_maintenance_issue,
    m.open_maintenance_action,
    s.active_shutin_note_id,
    s.active_shutin_author_name,
    s.active_shutin_valid_from,
    s.active_shutin_valid_to,
    s.active_shutin_equipment,
    s.active_shutin_text,
    COALESCE(s.is_shutin_logged_in_maintenance, FALSE) AS is_shutin_logged_in_maintenance,
    CASE
        WHEN li.is_producing = TRUE THEN 'PRODUCING'
        WHEN m.open_maintenance_id IS NOT NULL THEN 'OPEN_REPAIR'
        WHEN s.active_shutin_note_id IS NOT NULL THEN 'PLANNED_SHUTIN_NOTE'
        ELSE 'NO_RECORDED_REASON'
    END AS stop_reason_type,
    CASE
        WHEN li.is_producing = TRUE THEN 'Operating normally'
        WHEN m.open_maintenance_id IS NOT NULL THEN
            'Repair ' || m.open_maintenance_id || ', ' || LOWER(m.open_maintenance_issue) || ', started ' || strftime(m.open_maintenance_started_date, '%d %b') || ', still open'
        WHEN s.active_shutin_note_id IS NOT NULL THEN
            'Planned shut-in from ' || strftime(s.active_shutin_valid_from, '%-d %b') || ' (note ' || s.active_shutin_note_id || ' by ' || s.active_shutin_author_name || ')' ||
            CASE WHEN s.is_shutin_logged_in_maintenance = FALSE THEN '; not yet in maintenance system' ELSE '' END
        ELSE
            CASE
                WHEN li.inspector_notes IS NOT NULL AND length(trim(li.inspector_notes)) > 0
                THEN 'No recorded reason. The inspector noted "' || li.inspector_notes || '"'
                ELSE 'No recorded reason'
            END
    END AS stop_reason_summary
FROM latest_inspections li
LEFT JOIN open_repairs m ON li.asset_id = m.asset_id
LEFT JOIN active_shutins s ON li.asset_id = s.asset_id;
"""

SQL_CREATE_V_SPILL_COMPLIANCE_AUDIT = """
CREATE OR REPLACE VIEW v_spill_compliance_audit AS
WITH reg_summary AS (
    SELECT
        related_inspection_id,
        MAX(CASE WHEN protocol_id = 'SR-01' AND event_type = 'spill_report_filed' THEN event_id END) AS sr01_report_event_id,
        MAX(CASE WHEN protocol_id = 'SR-01' AND event_type = 'spill_report_filed' THEN hours_to_report END) AS hours_to_report,
        MAX(CASE WHEN protocol_id = 'SR-01' AND event_type = 'notice_of_violation' THEN event_id END) AS nov_event_id,
        MAX(CASE WHEN protocol_id = 'SR-01' AND event_type = 'notice_of_violation' THEN event_date END) AS nov_date,
        COALESCE(SUM(CASE WHEN protocol_id = 'SR-01' AND event_type = 'notice_of_violation' THEN fine_usd END), 0.0) AS nov_fine_usd,
        MAX(CASE WHEN protocol_id = 'SR-01' AND event_type = 'notice_of_violation' THEN status END) AS nov_status,
        MAX(CASE WHEN protocol_id = 'RC-04' AND event_type = 'nov_response_filed' THEN event_id END) AS nov_response_event_id,
        MAX(CASE WHEN protocol_id = 'SR-03' AND event_type = 'site_inspection' THEN event_id END) AS sr03_event_id,
        MAX(CASE WHEN protocol_id = 'SR-03' AND event_type = 'site_inspection' THEN status END) AS sr03_status
    FROM raw_regulatory_events
    WHERE related_inspection_id IS NOT NULL
    GROUP BY related_inspection_id
)
SELECT
    vei.inspection_id,
    vei.asset_id,
    vei.well_name,
    vei.well_type,
    vei.area_id,
    vei.area_name,
    vei.lat,
    vei.lon,
    vei.inspected_at,
    vei.inspection_date,
    vei.raw_spill_detected,
    vei.effective_spill_detected,
    vei.raw_spill_volume_bbl,
    vei.effective_spill_volume_bbl,
    vei.spill_area_pct,
    vei.has_active_correction,
    vei.applied_correction_note_ids,
    vei.corrected_by_user_names,
    vei.correction_reasons,
    rm.maintenance_id,
    prr.report_file_path,
    prr.containment_hours,
    4.0 AS sr02_limit_hours,
    (vei.effective_spill_detected = TRUE AND prr.containment_hours IS NOT NULL AND prr.containment_hours > 4.0) AS is_sr02_breach,
    prr.reported_spill_class,
    CASE
        WHEN vei.effective_spill_volume_bbl < 1.0 THEN 'minor'
        WHEN vei.effective_spill_volume_bbl < 5.0 THEN 'moderate'
        ELSE 'reportable'
    END AS effective_spill_class,
    (
        prr.reported_spill_class IS NOT NULL
        AND (
            CASE
                WHEN vei.effective_spill_volume_bbl < 1.0 THEN 'minor'
                WHEN vei.effective_spill_volume_bbl < 5.0 THEN 'moderate'
                ELSE 'reportable'
            END
        ) != prr.reported_spill_class
    ) AS is_report_class_outdated,
    (vei.effective_spill_detected = TRUE AND vei.effective_spill_volume_bbl >= 5.0) AS is_reportable_spill,
    reg.sr01_report_event_id,
    reg.hours_to_report,
    24.0 AS sr01_deadline_hours,
    (
        (vei.effective_spill_detected = TRUE AND vei.effective_spill_volume_bbl >= 5.0)
        AND (
            reg.hours_to_report > 24.0
            OR (
                reg.sr01_report_event_id IS NULL
                AND TIMESTAMP '2026-10-17 23:59:59' > vei.inspected_at + INTERVAL 24 HOUR
            )
        )
    ) AS is_sr01_breach,
    reg.nov_event_id,
    reg.nov_date,
    reg.nov_fine_usd,
    reg.nov_status,
    CASE
        WHEN reg.nov_date IS NOT NULL THEN (reg.nov_date + INTERVAL 30 DAY)::DATE
        ELSE NULL
    END AS rc04_response_due_date,
    reg.nov_response_event_id,
    (
        reg.nov_event_id IS NOT NULL
        AND (reg.nov_date + INTERVAL 30 DAY)::DATE < DATE '2026-10-17'
        AND reg.nov_response_event_id IS NULL
    ) AS is_rc04_breach,
    reg.sr03_event_id,
    CASE
        WHEN (vei.effective_spill_detected = TRUE AND vei.effective_spill_volume_bbl >= 5.0)
        THEN (vei.inspection_date + INTERVAL 60 DAY)::DATE
        ELSE NULL
    END AS sr03_cleanup_due_date,
    reg.sr03_status,
    (
        (vei.effective_spill_detected = TRUE AND vei.effective_spill_volume_bbl >= 5.0)
        AND (vei.inspection_date + INTERVAL 60 DAY)::DATE < DATE '2026-10-17'
        AND (reg.sr03_status IS NULL OR reg.sr03_status != 'closed')
    ) AS is_sr03_breach,
    vei.has_peer_disagreement,
    vei.peer_disagreement_note_ids_json,
    CASE
        WHEN vei.has_peer_disagreement THEN 'Conflicting operator notes present on this inspection'
        ELSE NULL
    END AS peer_disagreement_summary
FROM v_effective_inspections vei
LEFT JOIN raw_maintenance rm ON rm.triggered_by_inspection_id = vei.inspection_id
LEFT JOIN parsed_repair_reports prr ON prr.maintenance_id = rm.maintenance_id
LEFT JOIN reg_summary reg ON reg.related_inspection_id = vei.inspection_id
WHERE vei.raw_spill_detected = TRUE OR vei.effective_spill_detected = TRUE;
"""

SQL_CREATE_V_EQUIPMENT_RCA_TRACKER = """
CREATE OR REPLACE VIEW v_equipment_rca_tracker AS
WITH active_repairs_12m AS (
    SELECT
        rm.asset_id,
        rm.equipment_kind,
        COUNT(*) AS corrective_repairs_12m,
        STRING_AGG(rm.maintenance_id, ', ' ORDER BY rm.started_date) AS maintenance_ids_list,
        MAX(rm.maintenance_id) AS latest_maintenance_id,
        MAX(rm.started_date) AS latest_started_date,
        BOOL_OR(COALESCE(prr.rca_action_required, FALSE)) AS any_report_flags_action_required
    FROM raw_maintenance rm
    LEFT JOIN parsed_repair_reports prr ON rm.maintenance_id = prr.maintenance_id
    WHERE rm.maintenance_type = 'corrective'
      AND rm.started_date > DATE '2026-10-17' - INTERVAL 12 MONTH
      AND rm.started_date <= DATE '2026-10-17'
    GROUP BY rm.asset_id, rm.equipment_kind
),
matched_rules AS (
    SELECT
        ar.asset_id,
        ar.equipment_kind,
        rr.threshold_value,
        rr.source_file,
        rr.protocol_or_section,
        rr.is_user_override,
        rr.overridden_by_user_name,
        ROW_NUMBER() OVER (
            PARTITION BY ar.asset_id, ar.equipment_kind
            ORDER BY rr.is_user_override DESC, (CASE WHEN rr.equipment_kind != 'ALL' THEN 1 ELSE 2 END) ASC
        ) as rn
    FROM active_repairs_12m ar
    JOIN wells w ON ar.asset_id = w.asset_id
    LEFT JOIN rules_registry rr ON rr.rule_code = 'CORRECTIVE_REPAIRS_RCA_THRESHOLD'
                               AND rr.is_active = TRUE
                               AND rr.scope_value = w.well_type
                               AND (rr.equipment_kind = ar.equipment_kind OR rr.equipment_kind = 'ALL')
)
SELECT
    ar.asset_id,
    w.well_name,
    w.well_type,
    w.area_id,
    a.area_name,
    ar.equipment_kind,
    ar.corrective_repairs_12m,
    ar.maintenance_ids_list,
    ar.latest_maintenance_id,
    ar.latest_started_date,
    ar.any_report_flags_action_required,
    CAST(COALESCE(r.threshold_value, 3.0) AS INTEGER) AS required_rca_threshold,
    CASE
        WHEN r.is_user_override THEN 'User Override by ' || COALESCE(r.overridden_by_user_name, 'User')
        WHEN w.well_type = 'T200' THEN 'T200 manual section 10'
        ELSE 'T200 manual section 10 (referenced by T350 manual)'
    END AS rule_source_citation,
    COALESCE(r.is_user_override, FALSE) AS is_user_override_rule,
    r.overridden_by_user_name,
    (ar.corrective_repairs_12m >= COALESCE(r.threshold_value, 3.0) OR ar.any_report_flags_action_required = TRUE) AS needs_rca
FROM active_repairs_12m ar
JOIN wells w ON ar.asset_id = w.asset_id
JOIN areas a ON w.area_id = a.area_id
LEFT JOIN (
    SELECT * FROM matched_rules WHERE rn = 1
) r ON r.asset_id = ar.asset_id AND r.equipment_kind = ar.equipment_kind;
"""

SQL_CREATE_V_WELL_COMPLIANCE_SUMMARY = """
CREATE OR REPLACE VIEW v_well_compliance_summary AS
WITH spill_summary_12m AS (
    SELECT
        asset_id,
        COUNT(CASE WHEN is_sr01_breach THEN 1 END) AS sr01_breaches_cnt,
        COUNT(CASE WHEN is_sr02_breach THEN 1 END) AS sr02_breaches_cnt,
        COUNT(CASE WHEN is_sr03_breach THEN 1 END) AS sr03_breaches_cnt,
        COUNT(CASE WHEN is_rc04_breach THEN 1 END) AS rc04_breaches_cnt,
        (
            COUNT(CASE WHEN is_sr01_breach THEN 1 END) +
            COUNT(CASE WHEN is_sr02_breach THEN 1 END) +
            COUNT(CASE WHEN is_sr03_breach THEN 1 END) +
            COUNT(CASE WHEN is_rc04_breach THEN 1 END)
        ) AS total_breaches_12m,
        COALESCE(SUM(CASE WHEN nov_status = 'open' THEN nov_fine_usd ELSE 0.0 END), 0.0) AS open_fines_usd,
        COALESCE(SUM(nov_fine_usd), 0.0) AS total_fines_usd,
        STRING_AGG(
            CASE
                WHEN is_sr01_breach THEN 'SR-01: reported after ' || CAST(ROUND(hours_to_report, 1) AS VARCHAR) || 'h (>24h limit)'
                ELSE NULL
            END, '; '
        ) AS sr01_detail,
        STRING_AGG(
            CASE
                WHEN is_sr02_breach THEN 'SR-02: contained after ' || CAST(ROUND(containment_hours, 1) AS VARCHAR) || 'h (>4h limit)'
                ELSE NULL
            END, '; '
        ) AS sr02_detail,
        STRING_AGG(
            CASE
                WHEN is_sr03_breach THEN 'SR-03: cleanup verification due by ' || strftime(sr03_cleanup_due_date, '%d %b %Y') || ' is still open'
                ELSE NULL
            END, '; '
        ) AS sr03_detail,
        STRING_AGG(
            CASE
                WHEN is_rc04_breach THEN 'RC-04: NOV response due by ' || strftime(rc04_response_due_date, '%d %b %Y') || ' has no recorded response'
                ELSE NULL
            END, '; '
        ) AS rc04_detail
    FROM v_spill_compliance_audit
    WHERE inspection_date > DATE '2026-10-17' - INTERVAL 12 MONTH
      AND inspection_date <= DATE '2026-10-17'
    GROUP BY asset_id
),
rca_summary AS (
    SELECT
        asset_id,
        BOOL_OR(needs_rca) AS has_pending_rca,
        STRING_AGG(CASE WHEN needs_rca THEN equipment_kind END, ', ') AS pending_rca_equipment_list,
        STRING_AGG(
            CASE
                WHEN needs_rca THEN
                    'RCA due on ' || equipment_kind || ' (' || CAST(corrective_repairs_12m AS VARCHAR) || ' repairs in last 12m' ||
                    CASE WHEN any_report_flags_action_required THEN '; report marks Action required' ELSE '' END || ')'
                ELSE NULL
            END, '; '
        ) AS pending_rca_details
    FROM v_equipment_rca_tracker
    GROUP BY asset_id
),
flowline_test AS (
    SELECT
        asset_id,
        MAX(started_date) AS last_annual_flowline_test_date
    FROM raw_maintenance
    WHERE (issue ILIKE '%annual%flowline%' OR action_taken ILIKE '%annual%flowline%')
      AND started_date > DATE '2026-10-17' - INTERVAL 12 MONTH
      AND started_date <= DATE '2026-10-17'
    GROUP BY asset_id
)
SELECT
    w.asset_id,
    w.well_name,
    w.well_type,
    w.area_id,
    a.area_name,
    COALESCE(s.sr01_breaches_cnt, 0) AS sr01_breaches_cnt,
    COALESCE(s.sr02_breaches_cnt, 0) AS sr02_breaches_cnt,
    COALESCE(s.sr03_breaches_cnt, 0) AS sr03_breaches_cnt,
    COALESCE(s.rc04_breaches_cnt, 0) AS rc04_breaches_cnt,
    COALESCE(s.total_breaches_12m, 0) AS total_breaches_12m,
    COALESCE(s.open_fines_usd, 0.0) AS open_fines_usd,
    COALESCE(s.total_fines_usd, 0.0) AS total_fines_usd,
    s.sr01_detail,
    s.sr02_detail,
    s.sr03_detail,
    s.rc04_detail,
    COALESCE(r.has_pending_rca, FALSE) AS has_pending_rca,
    r.pending_rca_equipment_list,
    r.pending_rca_details,
    (cs.active_shutin_note_id IS NOT NULL AND cs.is_shutin_logged_in_maintenance = FALSE) AS has_unlogged_planned_shutin,
    cs.active_shutin_note_id AS unlogged_shutin_note_id,
    cs.active_shutin_text AS unlogged_shutin_summary,
    ft.last_annual_flowline_test_date,
    (ft.last_annual_flowline_test_date IS NOT NULL) AS is_annual_flowline_test_met
FROM wells w
JOIN areas a ON w.area_id = a.area_id
LEFT JOIN spill_summary_12m s ON w.asset_id = s.asset_id
LEFT JOIN rca_summary r ON w.asset_id = r.asset_id
LEFT JOIN v_well_current_status cs ON w.asset_id = cs.asset_id
LEFT JOIN flowline_test ft ON w.asset_id = ft.asset_id;
"""


def init_views(
    conn: Optional[duckdb.DuckDBPyConnection] = None,
    db_path: Optional[Union[str, Path]] = None,
    ref_date: Optional[str] = None,
) -> None:
    """Initialize or recreate the 5 Master Semantic Overlay Views in DuckDB."""
    settings = get_settings()
    today_str = ref_date or settings.REFERENCE_TODAY
    own_conn = False
    if conn is None:
        conn = get_db_connection(db_path, read_only=False)
        own_conn = True

    try:
        conn.execute(SQL_CREATE_V_EFFECTIVE_INSPECTIONS)
        conn.execute(
            SQL_CREATE_V_WELL_CURRENT_STATUS.replace("2026-10-17", today_str).replace(
                "2026-10-15", today_str
            )
        )
        conn.execute(SQL_CREATE_V_SPILL_COMPLIANCE_AUDIT.replace("2026-10-17", today_str))
        conn.execute(SQL_CREATE_V_EQUIPMENT_RCA_TRACKER.replace("2026-10-17", today_str))
        conn.execute(SQL_CREATE_V_WELL_COMPLIANCE_SUMMARY.replace("2026-10-17", today_str))
    finally:
        if own_conn:
            conn.close()
