# Phase 1 Forensic Audit Manifest & System Blueprint

- **Generated:** `2026-10-17T11:49:57.437380+00:00`
- **Reference 'Today':** `2026-10-17`
- **Dataset Root:** `/Users/ashum9/flyt/dataset-repo/test-data/dataset`

## 1. Executive Fleet Summary

| Entity / Metric | Count | Details |
| :--- | :--- | :--- |
| **Geographic Areas** | `7` | SW-23, SW-24, NE-07, NE-08 (50 wells each) |
| **Production Teams** | `6` | TEAM-SW, TEAM-NE, TEAM-MX, TEAM-HSE |
| **Users / Operators** | `27` | 14 users across supervisors, operators, inspectors, maintenance, HSE |
| **Total Oil Wells** | `600` | 119 T200 wells, 81 T350 wells (190 active, 10 down monthly recorded) |
| **Inspections** | `125,198` | 33,737 drone flights, 5,830 manual inspections |
| **Maintenance Records** | `17,415` | 4,156 scheduled maintenance, 1,509 corrective repairs |
| **Repair Reports (.md)** | `4,428` | 1,509 Markdown reports (100.0% path resolution with 0 broken links) |
| **Regulatory Events** | `328` | 36 spill reports, 34 site inspections, 11 NOVs, 9 NOV responses (3 open) |
| **Context Notes** | `1887` | 82 operator notes, 56 formal corrections, 3 operator feedback |
| **Open Repairs Right Now** | `976` | Planned completion after `2026-10-17` |

## 2. Discovered Domain Laws, Manuals & SOP Thresholds

### 2.1 Operating Manual Rules (`T200.md` & `T350.md`)

| Well Type | Min Production Delta T (Wellhead - Air) | Max Temp Alarm | Alarm Action | Source |
| :--- | :--- | :--- | :--- | :--- |
| **T200** | **`>= 15.0 °C`** | `<= 85.0 °C` | Shut in & inspect within 24h | `T200.md` §9.3 & §9.4 |
| **T350** | **`>= 20.0 °C`** | `<= 95.0 °C` | Shut in & inspect within 24h | `T350.md` §3 & §4 |

> **Hot-Day Trap:** On a hot day, an idle wellhead can read > 50 °C (e.g. 51.6 °C vs 43.1 °C ambient = 8.5 °C delta). Never evaluate wellhead temperature in isolation.

### 2.2 Maintenance Escalation & Shut-In Rules

- **RCA Trigger:** `3 or more corrective maintenance events on the same equipment kind within 12 months require Root-Cause Analysis (RCA) before next repair is closed`.
- **Downtime Escalation:** `Report to area production supervisor` after `14` consecutive days.
- **Planned Shut-In Requirement:** `Must record shut-in in maintenance system before work starts` (`T200.md` §4.4).
- **Pad Area Spill Shut-In:** `If spill covers > 5% of pad area, shut in immediately until source repaired`.

### 2.3 Spill Response Classes & Protocols (`spill-response-sop.md`)

| Class | Crude Volume Boundary | Action & Reporting Obligation |
| :--- | :--- | :--- |
| **Minor** | `below 1.0 bbl` | Record and clean up; no external report |
| **Moderate** | `1.0 bbl to below 5.0 bbl` | Record, clean up, notify HSE within 72 hours |
| **Reportable** | `5.0 bbl to below 25.0 bbl` | External report required under SR-01 within 24 hours |
| **Major** | `25.0 bbl or more` | External report within 2 hours, incident command |

### 2.4 Complete Protocol Dictionary (`SR`, `RC`, `WS`)

| Protocol ID | Title | Key Numeric Deadline / Limit | Source |
| :--- | :--- | :--- | :--- |
| **SR-01** | Spill Reporting Limit | `Within 24 hours` | `spill-response-sop.md §4` |
| **SR-02** | Spill Containment Limit | `Within 4.0 hours` | `spill-response-sop.md §4` |
| **SR-03** | Cleanup & Agency Verification | `Verification within 60 days` | `spill-response-sop.md §4` |
| **SR-04** | Spill Record Duty | `Spill Record Duty` | `spill-response-sop.md §4` |
| **RC-01** | Inspection Frequency | `Every 14 days` | `regulatory-compliance-sop.md §2` |
| **RC-02** | Annual Flowline Integrity Test | `Once per calendar year` | `regulatory-compliance-sop.md §2` |
| **RC-03** | Downtime Reporting | `Downtime Reporting` | `regulatory-compliance-sop.md §2` |
| **RC-04** | Notice of Violation (NOV) Response | `Within 30 days` | `regulatory-compliance-sop.md §2` |
| **RC-05** | Flowline Maintenance Program | `Flowline Maintenance Program` | `regulatory-compliance-sop.md §2` |
| **WS-01** | Pre-job safety meeting (JSA) | `Pre-job safety meeting (JSA)` | `field-work-sop.md §3` |
| **WS-02** | Energy isolation (LOTO) | `Energy isolation (LOTO)` | `field-work-sop.md §3` |
| **WS-03** | H2S monitor bump-tested, 10 ppm stop-work limit | `H2S monitor bump-tested, 10 ppm stop-work limit` | `field-work-sop.md §3` |
| **WS-04** | Hot work permit + gas test (< 10% LEL) | `Hot work permit + gas test (< 10% LEL)` | `field-work-sop.md §3` |
| **WS-05** | Pressure-test repaired flowline at 1.25x MOP for 4 hours | `Pressure-test repaired flowline at 1.25x MOP for 4 hours` | `field-work-sop.md §3` |
| **WS-06** | Waste manifest for oily waste to approved disposal site | `Waste manifest for oily waste to approved disposal site` | `field-work-sop.md §3` |
| **WS-07** | Maintenance report written within 3 days with compliance check | `Maintenance report written within 3 days with compliance check` | `field-work-sop.md §3` |

## 3. Data File Schema Profiling & Nested Key Census

### 3.1 `areas.json` (JSON)
- **Root Structure:** `object`

| Field Name | Inferred Type | Nullable | Sample Value |
| :--- | :--- | :--- | :--- |
| `area_id` | `string` | `No` | `SW-23` |
| `name` | `string` | `No` | `Southwest Block 23` |
| `team_id` | `string` | `No` | `TEAM-SW` |
| `center` | `object` | `No` | `{'lat': 31.842, 'lon': -102.512}` |
| `asset_ids` | `list[string]` | `No` | `['WELL-0001', 'WELL-0002', 'WELL-0003', 'WELL-0004', 'WEL...` |

### 3.2 `users.json` (JSON)
- **Root Structure:** `object`

| Field Name | Inferred Type | Nullable | Sample Value |
| :--- | :--- | :--- | :--- |
| `user_id` | `string` | `No` | `U-101` |
| `name` | `string` | `No` | `Emily Carter` |
| `role` | `string` | `No` | `production_supervisor` |
| `team_id` | `string` | `No` | `TEAM-SW` |

### 3.3 `metadata.json` (JSON)
- **Root Structure:** `object`

| Field Name | Inferred Type | Nullable | Sample Value |
| :--- | :--- | :--- | :--- |
| `asset_id` | `string` | `No` | `WELL-0001` |
| `name` | `string` | `No` | `SW-23 Well 001` |
| `asset_category` | `string` | `No` | `oil_well` |
| `well_type` | `string` | `No` | `T200` |
| `area_id` | `string` | `No` | `SW-23` |
| `team_id` | `string` | `No` | `TEAM-SW` |
| `in_charge_user_id` | `string` | `No` | `U-101` |
| `location` | `object` | `No` | `{'lat': 31.85425, 'lon': -102.50232}` |
| `installed_on` | `string` | `No` | `2013-03-25` |
| `equipment` | `list[object]` | `No` | `[{'equipment_id': 'WELL-0001-WH', 'kind': 'wellhead', 'mo...` |
| `last_inspection` | `object` | `No` | `{'inspection_id': 'INS-0001-0216', 'inspected_at': '2027-...` |
| `recorded_status` | `string` | `No` | `active` |

### 3.4 `inspections.jsonl` (JSONL)
- **Root Structure:** `line-delimited object`

| Field Name | Inferred Type | Nullable | Sample Value |
| :--- | :--- | :--- | :--- |
| `inspection_id` | `string` | `No` | `INS-0001-0001` |
| `asset_id` | `string` | `No` | `WELL-0001` |
| `inspected_at` | `string` | `No` | `2022-10-20T07:15:00Z` |
| `inspector_user_id` | `string` | `No` | `U-104` |
| `method` | `string` | `No` | `drone` |
| `ambient_temp_c` | `float` | `No` | `20.1` |
| `wellhead_temp_c` | `float` | `No` | `41.9` |
| `spill_detected` | `bool` | `No` | `False` |
| `spill_area_pct` | `float | null` | `Yes` | `None` |
| `spill_est_volume_bbl` | `float | null` | `Yes` | `None` |
| `evidence_images` | `list[string]` | `No` | `['evidence/WELL-0001/2022-10-20_rgb.jpg', 'evidence/WELL-...` |
| `notes` | `string` | `No` | `` |

### 3.5 `maintenance.jsonl` (JSONL)
- **Root Structure:** `line-delimited object`

| Field Name | Inferred Type | Nullable | Sample Value |
| :--- | :--- | :--- | :--- |
| `maintenance_id` | `string` | `No` | `MNT-0001-001` |
| `asset_id` | `string` | `No` | `WELL-0001` |
| `started_at` | `string` | `No` | `2023-01-23T08:00:00Z` |
| `completed_at` | `string` | `No` | `2023-01-23T11:00:00Z` |
| `maintenance_type` | `string` | `No` | `scheduled` |
| `equipment_kind` | `string` | `No` | `pump_jack` |
| `issue` | `string` | `No` | `Scheduled lubrication and belt inspection` |
| `action_taken` | `string` | `No` | `Lubricated, belts tensioned` |
| `technician_user_id` | `string` | `No` | `U-302` |
| `contractor` | `null | string` | `Yes` | `Coyote Ridge Well Services` |
| `downtime_hours` | `int` | `No` | `3` |
| `cost_usd` | `object` | `No` | `{'labor': 265, 'parts': 226, 'total': 491}` |
| `triggered_by_inspection_id` | `null | string` | `Yes` | `None` |
| `report_file` | `null | string` | `Yes` | `None` |

### 3.6 `regulatory-events.jsonl` (JSONL)
- **Root Structure:** `line-delimited object`

| Field Name | Inferred Type | Nullable | Sample Value |
| :--- | :--- | :--- | :--- |
| `asset_id` | `string` | `No` | `WELL-0001` |
| `date` | `string` | `No` | `2026-06-13` |
| `agency` | `string` | `No` | `State Oil & Gas Commission` |
| `event_type` | `string` | `No` | `spill_report_filed` |
| `protocol_id` | `string` | `No` | `SR-01` |
| `related_inspection_id` | `string` | `No` | `INS-0001-0185` |
| `detail` | `string` | `No` | `Operator filed spill report 41 h after detection; est. 6....` |
| `hours_to_report` | `int | null` | `Yes` | `41` |
| `fine_usd` | `int` | `No` | `0` |
| `status` | `string` | `No` | `closed` |
| `event_id` | `string` | `No` | `REG-0001-001` |

### 3.7 `context.jsonl` (JSONL)
- **Root Structure:** `line-delimited object`

| Field Name | Inferred Type | Nullable | Sample Value |
| :--- | :--- | :--- | :--- |
| `asset_id` | `string` | `No` | `WELL-0001` |
| `created_at` | `string` | `No` | `2024-03-07T16:05:00Z` |
| `author_user_id` | `string` | `No` | `U-401` |
| `note_type` | `string` | `No` | `correction` |
| `inspection_id` | `string` | `No` | `INS-0001-0070` |
| `text` | `string` | `No` | `Inspection INS-0001-0070: dark patch is rainwater mixed w...` |
| `valid_from` | `string` | `No` | `2024-03-07` |
| `valid_to` | `null | string` | `Yes` | `None` |
| `note_id` | `string` | `No` | `CTX-0001-001` |

## 4. Distinct Categorical Enumerations

- **`well_type`:** `T200` (293), `T350` (201), `T500` (106)
- **`recorded_status`:** `active` (545), `down` (52), `plugged` (3)
- **`equipment_kind`:** `wellhead` (600), `pump_jack` (494), `rod_string` (494), `downhole_pump` (494), `flowline` (600), `separator` (288), `esp_pump` (106)
- **`inspection_method`:** `drone` (106446), `manual` (18752)
- **`maintenance_type`:** `scheduled` (12987), `corrective` (4428)
- **`maintenance_equipment_kind`:** `pump_jack` (5475), `flowline` (4557), `wellhead` (5684), `rod_string` (228), `downhole_pump` (212), `separator` (128), `esp_pump` (1131)
- **`event_type`:** `spill_report_filed` (133), `notice_of_violation` (36), `site_inspection` (131), `nov_response_filed` (28)
- **`protocol_id`:** `SR-01` (169), `SR-03` (131), `RC-04` (28)
- **`agency`:** `State Oil & Gas Commission` (197), `Regional Environmental Protection Office` (131)
- **`event_status`:** `closed` (317), `open` (11)
- **`note_type`:** `correction` (194), `operator_note` (1687), `operator_feedback` (3), `data_correction` (3)
- **`user_role`:** `production_supervisor` (4), `field_operator` (8), `field_inspector` (8), `maintenance_lead` (1), `maintenance_technician` (4), `hse_officer` (2)

## 5. Formal Corrections Census (`note_type == 'correction'`)

Total formal corrections found: **194** across all 200 wells.
All 56 corrections reclassify AI false-positive detections (rainwater, mud, shadow, produced water).

| Well ID | Note ID | Inspection ID | Category | Override Text |
| :--- | :--- | :--- | :--- | :--- |
| `WELL-0001` | `CTX-0001-001` | `INS-0001-0070` | `rainwater_soil_false_positive` | Inspection INS-0001-0070: dark patch is rainwater mixed with soil, not crude. Not a spill. |
| `WELL-0003` | `CTX-0003-002` | `INS-0003-0183` | `shadow_false_positive` | Inspection INS-0003-0183: shadow from the pump jack. Not a crude spill. |
| `WELL-0004` | `CTX-0004-001` | `INS-0004-0190` | `produced_water_washout_false_positive` | Inspection INS-0004-0190: produced water from a washout, no crude. Not a crude spill. |
| `WELL-0006` | `CTX-0006-001` | `INS-0006-0110` | `rainwater_soil_false_positive` | Inspection INS-0006-0110: wet soil after rain. Not a crude spill. |
| `WELL-0008` | `CTX-0008-001` | `INS-0008-0084` | `rainwater_soil_false_positive` | Inspection INS-0008-0084: wet soil after rain. Not a crude spill. |
| `WELL-0011` | `CTX-0011-001` | `INS-0011-0201` | `produced_water_washout_false_positive` | Inspection INS-0011-0201: produced water from a washout, no crude. Not a crude spill. |
| `WELL-0015` | `CTX-0015-002` | `INS-0015-0205` | `rainwater_soil_false_positive` | Inspection INS-0015-0205: wet soil after rain. Not a crude spill. |
| `WELL-0018` | `CTX-0018-001` | `INS-0018-0045` | `shadow_false_positive` | Inspection INS-0018-0045: shadow from the pump jack. Not a crude spill. |
| `WELL-0019` | `CTX-0019-001` | `INS-0019-0002` | `shadow_false_positive` | Inspection INS-0019-0002: shadow from the pump jack. Not a crude spill. |
| `WELL-0024` | `CTX-0024-001` | `INS-0024-0172` | `shadow_false_positive` | Inspection INS-0024-0172: shadow from the pump jack. Not a crude spill. |
| `WELL-0027` | `CTX-0027-001` | `INS-0027-0139` | `shadow_false_positive` | Inspection INS-0027-0139: shadow from the pump jack. Not a crude spill. |
| `WELL-0037` | `CTX-0037-002` | `INS-0037-0108` | `rainwater_soil_false_positive` | Inspection INS-0037-0108: wet soil after rain. Not a crude spill. |
| `WELL-0045` | `CTX-0045-001` | `INS-0045-0084` | `shadow_false_positive` | Inspection INS-0045-0084: shadow from the pump jack. Not a crude spill. |
| `WELL-0048` | `CTX-0048-001` | `INS-0048-0091` | `shadow_false_positive` | Inspection INS-0048-0091: shadow from the pump jack. Not a crude spill. |
| `WELL-0054` | `CTX-0054-002` | `INS-0054-0172` | `rainwater_soil_false_positive` | Inspection INS-0054-0172: wet soil after rain. Not a crude spill. |
| `WELL-0055` | `CTX-0055-001` | `INS-0055-0016` | `shadow_false_positive` | Inspection INS-0055-0016: shadow from the pump jack. Not a crude spill. |
| `WELL-0056` | `CTX-0056-001` | `INS-0056-0155` | `shadow_false_positive` | Inspection INS-0056-0155: shadow from the pump jack. Not a crude spill. |
| `WELL-0062` | `CTX-0062-001` | `INS-0062-0187` | `shadow_false_positive` | Inspection INS-0062-0187: shadow from the pump jack. Not a crude spill. |
| `WELL-0064` | `CTX-0064-002` | `INS-0064-0046` | `shadow_false_positive` | Inspection INS-0064-0046: shadow from the pump jack. Not a crude spill. |
| `WELL-0065` | `CTX-0065-001` | `INS-0065-0041` | `shadow_false_positive` | Inspection INS-0065-0041: shadow from the pump jack. Not a crude spill. |
| `WELL-0069` | `CTX-0069-002` | `INS-0069-0162` | `produced_water_washout_false_positive` | Inspection INS-0069-0162: produced water from a washout, no crude. Not a crude spill. |
| `WELL-0075` | `CTX-0075-001` | `INS-0075-0165` | `shadow_false_positive` | Inspection INS-0075-0165: shadow from the pump jack. Not a crude spill. |
| `WELL-0076` | `CTX-0076-002` | `INS-0076-0152` | `shadow_false_positive` | Inspection INS-0076-0152: shadow from the pump jack. Not a crude spill. |
| `WELL-0078` | `CTX-0078-001` | `INS-0078-0011` | `produced_water_washout_false_positive` | Inspection INS-0078-0011: produced water from a washout, no crude. Not a crude spill. |
| `WELL-0080` | `CTX-0080-002` | `INS-0080-0192` | `produced_water_washout_false_positive` | Inspection INS-0080-0192: produced water from a washout, no crude. Not a crude spill. |
| `WELL-0081` | `CTX-0081-001` | `INS-0081-0171` | `rainwater_soil_false_positive` | Inspection INS-0081-0171: wet soil after rain. Not a crude spill. |
| `WELL-0104` | `CTX-0104-001` | `INS-0104-0058` | `shadow_false_positive` | Inspection INS-0104-0058: shadow from the pump jack. Not a crude spill. |
| `WELL-0107` | `CTX-0107-002` | `INS-0107-0201` | `rainwater_soil_false_positive` | Inspection INS-0107-0201: wet soil after rain. Not a crude spill. |
| `WELL-0108` | `CTX-0108-001` | `INS-0108-0131` | `produced_water_washout_false_positive` | Inspection INS-0108-0131: produced water from a washout, no crude. Not a crude spill. |
| `WELL-0113` | `CTX-0113-001` | `INS-0113-0021` | `rainwater_soil_false_positive` | Inspection INS-0113-0021: wet soil after rain. Not a crude spill. |
| `WELL-0114` | `CTX-0114-001` | `INS-0114-0110` | `rainwater_soil_false_positive` | Inspection INS-0114-0110: wet soil after rain. Not a crude spill. |
| `WELL-0118` | `CTX-0118-001` | `INS-0118-0010` | `produced_water_washout_false_positive` | Inspection INS-0118-0010: produced water from a washout, no crude. Not a crude spill. |
| `WELL-0119` | `CTX-0119-001` | `INS-0119-0191` | `produced_water_washout_false_positive` | Inspection INS-0119-0191: produced water from a washout, no crude. Not a crude spill. |
| `WELL-0120` | `CTX-0120-001` | `INS-0120-0202` | `shadow_false_positive` | Inspection INS-0120-0202: shadow from the pump jack. Not a crude spill. |
| `WELL-0121` | `CTX-0121-001` | `INS-0121-0170` | `shadow_false_positive` | Inspection INS-0121-0170: shadow from the pump jack. Not a crude spill. |
| `WELL-0122` | `CTX-0122-002` | `INS-0122-0201` | `rainwater_soil_false_positive` | Inspection INS-0122-0201: wet soil after rain. Not a crude spill. |
| `WELL-0125` | `CTX-0125-001` | `INS-0125-0025` | `shadow_false_positive` | Inspection INS-0125-0025: shadow from the pump jack. Not a crude spill. |
| `WELL-0128` | `CTX-0128-001` | `INS-0128-0026` | `rainwater_soil_false_positive` | Inspection INS-0128-0026: wet soil after rain. Not a crude spill. |
| `WELL-0138` | `CTX-0138-002` | `INS-0138-0142` | `produced_water_washout_false_positive` | Inspection INS-0138-0142: produced water from a washout, no crude. Not a crude spill. |
| `WELL-0142` | `CTX-0142-001` | `INS-0142-0003` | `produced_water_washout_false_positive` | Inspection INS-0142-0003: produced water from a washout, no crude. Not a crude spill. |
| `WELL-0145` | `CTX-0145-001` | `INS-0145-0071` | `shadow_false_positive` | Inspection INS-0145-0071: shadow from the pump jack. Not a crude spill. |
| `WELL-0146` | `CTX-0146-001` | `INS-0146-0036` | `produced_water_washout_false_positive` | Inspection INS-0146-0036: produced water from a washout, no crude. Not a crude spill. |
| `WELL-0149` | `CTX-0149-001` | `INS-0149-0068` | `rainwater_soil_false_positive` | Inspection INS-0149-0068: wet soil after rain. Not a crude spill. |
| `WELL-0158` | `CTX-0158-001` | `INS-0158-0034` | `rainwater_soil_false_positive` | Inspection INS-0158-0034: wet soil after rain. Not a crude spill. |
| `WELL-0159` | `CTX-0159-001` | `INS-0159-0016` | `shadow_false_positive` | Inspection INS-0159-0016: shadow from the pump jack. Not a crude spill. |
| `WELL-0161` | `CTX-0161-001` | `INS-0161-0058` | `shadow_false_positive` | Inspection INS-0161-0058: shadow from the pump jack. Not a crude spill. |
| `WELL-0164` | `CTX-0164-001` | `INS-0164-0071` | `produced_water_washout_false_positive` | Inspection INS-0164-0071: produced water from a washout, no crude. Not a crude spill. |
| `WELL-0168` | `CTX-0168-001` | `INS-0168-0089` | `produced_water_washout_false_positive` | Inspection INS-0168-0089: produced water from a washout, no crude. Not a crude spill. |
| `WELL-0169` | `CTX-0169-001` | `INS-0169-0120` | `produced_water_washout_false_positive` | Inspection INS-0169-0120: produced water from a washout, no crude. Not a crude spill. |
| `WELL-0177` | `CTX-0177-001` | `INS-0177-0151` | `produced_water_washout_false_positive` | Inspection INS-0177-0151: produced water from a washout, no crude. Not a crude spill. |
| `WELL-0183` | `CTX-0183-001` | `INS-0183-0182` | `rainwater_soil_false_positive` | Inspection INS-0183-0182: wet soil after rain. Not a crude spill. |
| `WELL-0187` | `CTX-0187-001` | `INS-0187-0015` | `produced_water_washout_false_positive` | Inspection INS-0187-0015: produced water from a washout, no crude. Not a crude spill. |
| `WELL-0189` | `CTX-0189-001` | `INS-0189-0009` | `produced_water_washout_false_positive` | Inspection INS-0189-0009: produced water from a washout, no crude. Not a crude spill. |
| `WELL-0194` | `CTX-0194-002` | `INS-0194-0192` | `shadow_false_positive` | Inspection INS-0194-0192: shadow from the pump jack. Not a crude spill. |
| `WELL-0195` | `CTX-0195-001` | `INS-0195-0155` | `rainwater_soil_false_positive` | Inspection INS-0195-0155: wet soil after rain. Not a crude spill. |
| `WELL-0199` | `CTX-0199-002` | `INS-0199-0200` | `shadow_false_positive` | Inspection INS-0199-0200: shadow from the pump jack. Not a crude spill. |
| `WELL-0201` | `CTX-0201-001` | `INS-0201-0084` | `produced_water_washout_false_positive` | Inspection INS-0201-0084: produced water from a washout, no crude. Not a crude spill. |
| `WELL-0203` | `CTX-0203-001` | `INS-0203-0155` | `rainwater_soil_false_positive` | Inspection INS-0203-0155: wet soil after rain. Not a crude spill. |
| `WELL-0209` | `CTX-0209-002` | `INS-0209-0181` | `rainwater_soil_false_positive` | Inspection INS-0209-0181: wet soil after rain. Not a crude spill. |
| `WELL-0211` | `CTX-0211-001` | `INS-0211-0196` | `rainwater_soil_false_positive` | Inspection INS-0211-0196: wet soil after rain. Not a crude spill. |
| `WELL-0213` | `CTX-0213-001` | `INS-0213-0099` | `shadow_false_positive` | Inspection INS-0213-0099: shadow from the pump jack. Not a crude spill. |
| `WELL-0214` | `CTX-0214-001` | `INS-0214-0107` | `shadow_false_positive` | Inspection INS-0214-0107: shadow from the pump jack. Not a crude spill. |
| `WELL-0217` | `CTX-0217-001` | `INS-0217-0085` | `rainwater_soil_false_positive` | Inspection INS-0217-0085: wet soil after rain. Not a crude spill. |
| `WELL-0219` | `CTX-0219-001` | `INS-0219-0007` | `produced_water_washout_false_positive` | Inspection INS-0219-0007: produced water from a washout, no crude. Not a crude spill. |
| `WELL-0225` | `CTX-0225-001` | `INS-0225-0140` | `shadow_false_positive` | Inspection INS-0225-0140: shadow from the pump jack. Not a crude spill. |
| `WELL-0227` | `CTX-0227-001` | `INS-0227-0080` | `produced_water_washout_false_positive` | Inspection INS-0227-0080: produced water from a washout, no crude. Not a crude spill. |
| `WELL-0230` | `CTX-0230-001` | `INS-0230-0110` | `produced_water_washout_false_positive` | Inspection INS-0230-0110: produced water from a washout, no crude. Not a crude spill. |
| `WELL-0233` | `CTX-0233-001` | `INS-0233-0102` | `rainwater_soil_false_positive` | Inspection INS-0233-0102: wet soil after rain. Not a crude spill. |
| `WELL-0243` | `CTX-0243-001` | `INS-0243-0122` | `shadow_false_positive` | Inspection INS-0243-0122: shadow from the drive panel. Not a crude spill. |
| `WELL-0244` | `CTX-0244-001` | `INS-0244-0011` | `rainwater_soil_false_positive` | Inspection INS-0244-0011: wet soil after rain. Not a crude spill. |
| `WELL-0245` | `CTX-0245-001` | `INS-0245-0117` | `produced_water_washout_false_positive` | Inspection INS-0245-0117: produced water from a washout, no crude. Not a crude spill. |
| `WELL-0249` | `CTX-0249-001` | `INS-0249-0043` | `rainwater_soil_false_positive` | Inspection INS-0249-0043: wet soil after rain. Not a crude spill. |
| `WELL-0251` | `CTX-0251-001` | `INS-0251-0173` | `rainwater_soil_false_positive` | Inspection INS-0251-0173: wet soil after rain. Not a crude spill. |
| `WELL-0257` | `CTX-0257-002` | `INS-0257-0170` | `rainwater_soil_false_positive` | Inspection INS-0257-0170: wet soil after rain. Not a crude spill. |
| `WELL-0259` | `CTX-0259-001` | `INS-0259-0170` | `rainwater_soil_false_positive` | Inspection INS-0259-0170: wet soil after rain. Not a crude spill. |
| `WELL-0260` | `CTX-0260-002` | `INS-0260-0190` | `shadow_false_positive` | Inspection INS-0260-0190: shadow from the pump jack. Not a crude spill. |
| `WELL-0261` | `CTX-0261-001` | `INS-0261-0022` | `produced_water_washout_false_positive` | Inspection INS-0261-0022: produced water from a washout, no crude. Not a crude spill. |
| `WELL-0265` | `CTX-0265-001` | `INS-0265-0002` | `produced_water_washout_false_positive` | Inspection INS-0265-0002: produced water from a washout, no crude. Not a crude spill. |
| `WELL-0267` | `CTX-0267-002` | `INS-0267-0194` | `rainwater_soil_false_positive` | Inspection INS-0267-0194: wet soil after rain. Not a crude spill. |
| `WELL-0268` | `CTX-0268-001` | `INS-0268-0187` | `rainwater_soil_false_positive` | Inspection INS-0268-0187: wet soil after rain. Not a crude spill. |
| `WELL-0272` | `CTX-0272-001` | `INS-0272-0196` | `shadow_false_positive` | Inspection INS-0272-0196: shadow from the pump jack. Not a crude spill. |
| `WELL-0276` | `CTX-0276-001` | `INS-0276-0172` | `rainwater_soil_false_positive` | Inspection INS-0276-0172: wet soil after rain. Not a crude spill. |
| `WELL-0279` | `CTX-0279-001` | `INS-0279-0143` | `produced_water_washout_false_positive` | Inspection INS-0279-0143: produced water from a washout, no crude. Not a crude spill. |
| `WELL-0282` | `CTX-0282-001` | `INS-0282-0091` | `rainwater_soil_false_positive` | Inspection INS-0282-0091: wet soil after rain. Not a crude spill. |
| `WELL-0285` | `CTX-0285-002` | `INS-0285-0199` | `rainwater_soil_false_positive` | Inspection INS-0285-0199: wet soil after rain. Not a crude spill. |
| `WELL-0286` | `CTX-0286-001` | `INS-0286-0053` | `produced_water_washout_false_positive` | Inspection INS-0286-0053: produced water from a washout, no crude. Not a crude spill. |
| `WELL-0288` | `CTX-0288-002` | `INS-0288-0195` | `rainwater_soil_false_positive` | Inspection INS-0288-0195: wet soil after rain. Not a crude spill. |
| `WELL-0291` | `CTX-0291-001` | `INS-0291-0033` | `produced_water_washout_false_positive` | Inspection INS-0291-0033: produced water from a washout, no crude. Not a crude spill. |
| `WELL-0292` | `CTX-0292-001` | `INS-0292-0071` | `produced_water_washout_false_positive` | Inspection INS-0292-0071: produced water from a washout, no crude. Not a crude spill. |
| `WELL-0294` | `CTX-0294-002` | `INS-0294-0106` | `rainwater_soil_false_positive` | Inspection INS-0294-0106: wet soil after rain. Not a crude spill. |
| `WELL-0295` | `CTX-0295-001` | `INS-0295-0040` | `shadow_false_positive` | Inspection INS-0295-0040: shadow from the pump jack. Not a crude spill. |
| `WELL-0302` | `CTX-0302-001` | `INS-0302-0011` | `rainwater_soil_false_positive` | Inspection INS-0302-0011: wet soil after rain. Not a crude spill. |
| `WELL-0303` | `CTX-0303-001` | `INS-0303-0064` | `rainwater_soil_false_positive` | Inspection INS-0303-0064: wet soil after rain. Not a crude spill. |
| `WELL-0306` | `CTX-0306-001` | `INS-0306-0200` | `shadow_false_positive` | Inspection INS-0306-0200: shadow from the pump jack. Not a crude spill. |
| `WELL-0307` | `CTX-0307-001` | `INS-0307-0006` | `produced_water_washout_false_positive` | Inspection INS-0307-0006: produced water from a washout, no crude. Not a crude spill. |
| `WELL-0321` | `CTX-0321-001` | `INS-0321-0100` | `produced_water_washout_false_positive` | Inspection INS-0321-0100: produced water from a washout, no crude. Not a crude spill. |
| `WELL-0325` | `CTX-0325-001` | `INS-0325-0075` | `produced_water_washout_false_positive` | Inspection INS-0325-0075: produced water from a washout, no crude. Not a crude spill. |
| `WELL-0326` | `CTX-0326-001` | `INS-0326-0005` | `shadow_false_positive` | Inspection INS-0326-0005: shadow from the pump jack. Not a crude spill. |
| `WELL-0336` | `CTX-0336-001` | `INS-0336-0184` | `rainwater_soil_false_positive` | Inspection INS-0336-0184: wet soil after rain. Not a crude spill. |
| `WELL-0338` | `CTX-0338-002` | `INS-0338-0190` | `shadow_false_positive` | Inspection INS-0338-0190: shadow from the pump jack. Not a crude spill. |
| `WELL-0345` | `CTX-0345-001` | `INS-0345-0205` | `shadow_false_positive` | Inspection INS-0345-0205: shadow from the pump jack. Not a crude spill. |
| `WELL-0348` | `CTX-0348-001` | `INS-0348-0161` | `rainwater_soil_false_positive` | Inspection INS-0348-0161: wet soil after rain. Not a crude spill. |
| `WELL-0352` | `CTX-0352-001` | `INS-0352-0008` | `shadow_false_positive` | Inspection INS-0352-0008: shadow from the drive panel. Not a crude spill. |
| `WELL-0353` | `CTX-0353-001` | `INS-0353-0005` | `shadow_false_positive` | Inspection INS-0353-0005: shadow from the pump jack. Not a crude spill. |
| `WELL-0355` | `CTX-0355-002` | `INS-0355-0174` | `rainwater_soil_false_positive` | Inspection INS-0355-0174: wet soil after rain. Not a crude spill. |
| `WELL-0357` | `CTX-0357-001` | `INS-0357-0060` | `produced_water_washout_false_positive` | Inspection INS-0357-0060: produced water from a washout, no crude. Not a crude spill. |
| `WELL-0359` | `CTX-0359-002` | `INS-0359-0191` | `shadow_false_positive` | Inspection INS-0359-0191: shadow from the pump jack. Not a crude spill. |
| `WELL-0360` | `CTX-0360-001` | `INS-0360-0051` | `produced_water_washout_false_positive` | Inspection INS-0360-0051: produced water from a washout, no crude. Not a crude spill. |
| `WELL-0361` | `CTX-0361-001` | `INS-0361-0186` | `shadow_false_positive` | Inspection INS-0361-0186: shadow from the drive panel. Not a crude spill. |
| `WELL-0364` | `CTX-0364-001` | `INS-0364-0127` | `produced_water_washout_false_positive` | Inspection INS-0364-0127: produced water from a washout, no crude. Not a crude spill. |
| `WELL-0367` | `CTX-0367-001` | `INS-0367-0005` | `rainwater_soil_false_positive` | Inspection INS-0367-0005: wet soil after rain. Not a crude spill. |
| `WELL-0368` | `CTX-0368-001` | `INS-0368-0064` | `rainwater_soil_false_positive` | Inspection INS-0368-0064: wet soil after rain. Not a crude spill. |
| `WELL-0370` | `CTX-0370-001` | `INS-0370-0072` | `produced_water_washout_false_positive` | Inspection INS-0370-0072: produced water from a washout, no crude. Not a crude spill. |
| `WELL-0371` | `CTX-0371-001` | `INS-0371-0028` | `rainwater_soil_false_positive` | Inspection INS-0371-0028: wet soil after rain. Not a crude spill. |
| `WELL-0373` | `CTX-0373-002` | `INS-0373-0165` | `shadow_false_positive` | Inspection INS-0373-0165: shadow from the pump jack. Not a crude spill. |
| `WELL-0374` | `CTX-0374-001` | `INS-0374-0135` | `shadow_false_positive` | Inspection INS-0374-0135: shadow from the pump jack. Not a crude spill. |
| `WELL-0375` | `CTX-0375-001` | `INS-0375-0160` | `produced_water_washout_false_positive` | Inspection INS-0375-0160: produced water from a washout, no crude. Not a crude spill. |
| `WELL-0382` | `CTX-0382-001` | `INS-0382-0088` | `rainwater_soil_false_positive` | Inspection INS-0382-0088: wet soil after rain. Not a crude spill. |
| `WELL-0383` | `CTX-0383-001` | `INS-0383-0036` | `rainwater_soil_false_positive` | Inspection INS-0383-0036: wet soil after rain. Not a crude spill. |
| `WELL-0384` | `CTX-0384-001` | `INS-0384-0025` | `shadow_false_positive` | Inspection INS-0384-0025: shadow from the pump jack. Not a crude spill. |
| `WELL-0387` | `CTX-0387-001` | `INS-0387-0124` | `rainwater_soil_false_positive` | Inspection INS-0387-0124: wet soil after rain. Not a crude spill. |
| `WELL-0389` | `CTX-0389-001` | `INS-0389-0097` | `produced_water_washout_false_positive` | Inspection INS-0389-0097: produced water from a washout, no crude. Not a crude spill. |
| `WELL-0397` | `CTX-0397-001` | `INS-0397-0086` | `shadow_false_positive` | Inspection INS-0397-0086: shadow from the pump jack. Not a crude spill. |
| `WELL-0398` | `CTX-0398-001` | `INS-0398-0181` | `produced_water_washout_false_positive` | Inspection INS-0398-0181: produced water from a washout, no crude. Not a crude spill. |
| `WELL-0400` | `CTX-0400-001` | `INS-0400-0024` | `produced_water_washout_false_positive` | Inspection INS-0400-0024: produced water from a washout, no crude. Not a crude spill. |
| `WELL-0403` | `CTX-0403-001` | `INS-0403-0004` | `shadow_false_positive` | Inspection INS-0403-0004: shadow from the pump jack. Not a crude spill. |
| `WELL-0404` | `CTX-0404-001` | `INS-0404-0121` | `rainwater_soil_false_positive` | Inspection INS-0404-0121: wet soil after rain. Not a crude spill. |
| `WELL-0405` | `CTX-0405-001` | `INS-0405-0023` | `shadow_false_positive` | Inspection INS-0405-0023: shadow from the pump jack. Not a crude spill. |
| `WELL-0406` | `CTX-0406-002` | `INS-0406-0139` | `produced_water_washout_false_positive` | Inspection INS-0406-0139: produced water from a washout, no crude. Not a crude spill. |
| `WELL-0409` | `CTX-0409-001` | `INS-0409-0197` | `rainwater_soil_false_positive` | Inspection INS-0409-0197: wet soil after rain. Not a crude spill. |
| `WELL-0410` | `CTX-0410-001` | `INS-0410-0202` | `rainwater_soil_false_positive` | Inspection INS-0410-0202: wet soil after rain. Not a crude spill. |
| `WELL-0411` | `CTX-0411-001` | `INS-0411-0040` | `rainwater_soil_false_positive` | Inspection INS-0411-0040: wet soil after rain. Not a crude spill. |
| `WELL-0412` | `CTX-0412-001` | `INS-0412-0045` | `rainwater_soil_false_positive` | Inspection INS-0412-0045: wet soil after rain. Not a crude spill. |
| `WELL-0416` | `CTX-0416-002` | `INS-0416-0097` | `produced_water_washout_false_positive` | Inspection INS-0416-0097: produced water from a washout, no crude. Not a crude spill. |
| `WELL-0420` | `CTX-0420-002` | `INS-0420-0064` | `rainwater_soil_false_positive` | Inspection INS-0420-0064: wet soil after rain. Not a crude spill. |
| `WELL-0431` | `CTX-0431-002` | `INS-0431-0135` | `rainwater_soil_false_positive` | Inspection INS-0431-0135: wet soil after rain. Not a crude spill. |
| `WELL-0432` | `CTX-0432-002` | `INS-0432-0184` | `produced_water_washout_false_positive` | Inspection INS-0432-0184: produced water from a washout, no crude. Not a crude spill. |
| `WELL-0433` | `CTX-0433-001` | `INS-0433-0076` | `rainwater_soil_false_positive` | Inspection INS-0433-0076: wet soil after rain. Not a crude spill. |
| `WELL-0442` | `CTX-0442-001` | `INS-0442-0101` | `produced_water_washout_false_positive` | Inspection INS-0442-0101: produced water from a washout, no crude. Not a crude spill. |
| `WELL-0447` | `CTX-0447-001` | `INS-0447-0025` | `produced_water_washout_false_positive` | Inspection INS-0447-0025: produced water from a washout, no crude. Not a crude spill. |
| `WELL-0448` | `CTX-0448-001` | `INS-0448-0114` | `produced_water_washout_false_positive` | Inspection INS-0448-0114: produced water from a washout, no crude. Not a crude spill. |
| `WELL-0450` | `CTX-0450-001` | `INS-0450-0063` | `rainwater_soil_false_positive` | Inspection INS-0450-0063: wet soil after rain. Not a crude spill. |
| `WELL-0451` | `CTX-0451-001` | `INS-0451-0164` | `shadow_false_positive` | Inspection INS-0451-0164: shadow from the pump jack. Not a crude spill. |
| `WELL-0452` | `CTX-0452-001` | `INS-0452-0056` | `shadow_false_positive` | Inspection INS-0452-0056: shadow from the pump jack. Not a crude spill. |
| `WELL-0453` | `CTX-0453-001` | `INS-0453-0016` | `produced_water_washout_false_positive` | Inspection INS-0453-0016: produced water from a washout, no crude. Not a crude spill. |
| `WELL-0456` | `CTX-0456-001` | `INS-0456-0117` | `rainwater_soil_false_positive` | Inspection INS-0456-0117: wet soil after rain. Not a crude spill. |
| `WELL-0462` | `CTX-0462-001` | `INS-0462-0151` | `shadow_false_positive` | Inspection INS-0462-0151: shadow from the pump jack. Not a crude spill. |
| `WELL-0468` | `CTX-0468-001` | `INS-0468-0121` | `shadow_false_positive` | Inspection INS-0468-0121: shadow from the pump jack. Not a crude spill. |
| `WELL-0475` | `CTX-0475-001` | `INS-0475-0016` | `produced_water_washout_false_positive` | Inspection INS-0475-0016: produced water from a washout, no crude. Not a crude spill. |
| `WELL-0476` | `CTX-0476-001` | `INS-0476-0159` | `produced_water_washout_false_positive` | Inspection INS-0476-0159: produced water from a washout, no crude. Not a crude spill. |
| `WELL-0477` | `CTX-0477-001` | `INS-0477-0046` | `rainwater_soil_false_positive` | Inspection INS-0477-0046: wet soil after rain. Not a crude spill. |
| `WELL-0480` | `CTX-0480-001` | `INS-0480-0093` | `produced_water_washout_false_positive` | Inspection INS-0480-0093: produced water from a washout, no crude. Not a crude spill. |
| `WELL-0481` | `CTX-0481-001` | `INS-0481-0077` | `rainwater_soil_false_positive` | Inspection INS-0481-0077: wet soil after rain. Not a crude spill. |
| `WELL-0483` | `CTX-0483-001` | `INS-0483-0138` | `rainwater_soil_false_positive` | Inspection INS-0483-0138: wet soil after rain. Not a crude spill. |
| `WELL-0487` | `CTX-0487-001` | `INS-0487-0066` | `produced_water_washout_false_positive` | Inspection INS-0487-0066: produced water from a washout, no crude. Not a crude spill. |
| `WELL-0488` | `CTX-0488-001` | `INS-0488-0037` | `shadow_false_positive` | Inspection INS-0488-0037: shadow from the drive panel. Not a crude spill. |
| `WELL-0490` | `CTX-0490-001` | `INS-0490-0148` | `shadow_false_positive` | Inspection INS-0490-0148: shadow from the pump jack. Not a crude spill. |
| `WELL-0494` | `CTX-0494-001` | `INS-0494-0101` | `shadow_false_positive` | Inspection INS-0494-0101: shadow from the pump jack. Not a crude spill. |
| `WELL-0499` | `CTX-0499-001` | `INS-0499-0138` | `rainwater_soil_false_positive` | Inspection INS-0499-0138: wet soil after rain. Not a crude spill. |
| `WELL-0502` | `CTX-0502-001` | `INS-0502-0079` | `rainwater_soil_false_positive` | Inspection INS-0502-0079: wet soil after rain. Not a crude spill. |
| `WELL-0503` | `CTX-0503-001` | `INS-0503-0175` | `produced_water_washout_false_positive` | Inspection INS-0503-0175: produced water from a washout, no crude. Not a crude spill. |
| `WELL-0509` | `CTX-0509-001` | `INS-0509-0009` | `rainwater_soil_false_positive` | Inspection INS-0509-0009: wet soil after rain. Not a crude spill. |
| `WELL-0510` | `CTX-0510-001` | `INS-0510-0136` | `produced_water_washout_false_positive` | Inspection INS-0510-0136: produced water from a washout, no crude. Not a crude spill. |
| `WELL-0513` | `CTX-0513-001` | `INS-0513-0107` | `shadow_false_positive` | Inspection INS-0513-0107: shadow from the pump jack. Not a crude spill. |
| `WELL-0525` | `CTX-0525-002` | `INS-0525-0156` | `shadow_false_positive` | Inspection INS-0525-0156: shadow from the pump jack. Not a crude spill. |
| `WELL-0528` | `CTX-0528-001` | `INS-0528-0057` | `produced_water_washout_false_positive` | Inspection INS-0528-0057: produced water from a washout, no crude. Not a crude spill. |
| `WELL-0529` | `CTX-0529-001` | `INS-0529-0036` | `produced_water_washout_false_positive` | Inspection INS-0529-0036: produced water from a washout, no crude. Not a crude spill. |
| `WELL-0532` | `CTX-0532-001` | `INS-0532-0059` | `shadow_false_positive` | Inspection INS-0532-0059: shadow from the pump jack. Not a crude spill. |
| `WELL-0535` | `CTX-0535-001` | `INS-0535-0154` | `rainwater_soil_false_positive` | Inspection INS-0535-0154: wet soil after rain. Not a crude spill. |
| `WELL-0538` | `CTX-0538-001` | `INS-0538-0060` | `produced_water_washout_false_positive` | Inspection INS-0538-0060: produced water from a washout, no crude. Not a crude spill. |
| `WELL-0539` | `CTX-0539-001` | `INS-0539-0121` | `produced_water_washout_false_positive` | Inspection INS-0539-0121: produced water from a washout, no crude. Not a crude spill. |
| `WELL-0542` | `CTX-0542-001` | `INS-0542-0138` | `produced_water_washout_false_positive` | Inspection INS-0542-0138: produced water from a washout, no crude. Not a crude spill. |
| `WELL-0544` | `CTX-0544-001` | `INS-0544-0170` | `rainwater_soil_false_positive` | Inspection INS-0544-0170: wet soil after rain. Not a crude spill. |
| `WELL-0545` | `CTX-0545-001` | `INS-0545-0091` | `shadow_false_positive` | Inspection INS-0545-0091: shadow from the pump jack. Not a crude spill. |
| `WELL-0548` | `CTX-0548-001` | `INS-0548-0097` | `produced_water_washout_false_positive` | Inspection INS-0548-0097: produced water from a washout, no crude. Not a crude spill. |
| `WELL-0555` | `CTX-0555-001` | `INS-0555-0031` | `produced_water_washout_false_positive` | Inspection INS-0555-0031: produced water from a washout, no crude. Not a crude spill. |
| `WELL-0558` | `CTX-0558-001` | `INS-0558-0190` | `shadow_false_positive` | Inspection INS-0558-0190: shadow from the drive panel. Not a crude spill. |
| `WELL-0559` | `CTX-0559-001` | `INS-0559-0146` | `produced_water_washout_false_positive` | Inspection INS-0559-0146: produced water from a washout, no crude. Not a crude spill. |
| `WELL-0560` | `CTX-0560-001` | `INS-0560-0178` | `produced_water_washout_false_positive` | Inspection INS-0560-0178: produced water from a washout, no crude. Not a crude spill. |
| `WELL-0561` | `CTX-0561-001` | `INS-0561-0040` | `produced_water_washout_false_positive` | Inspection INS-0561-0040: produced water from a washout, no crude. Not a crude spill. |
| `WELL-0562` | `CTX-0562-002` | `INS-0562-0179` | `rainwater_soil_false_positive` | Inspection INS-0562-0179: wet soil after rain. Not a crude spill. |
| `WELL-0565` | `CTX-0565-002` | `INS-0565-0089` | `rainwater_soil_false_positive` | Inspection INS-0565-0089: wet soil after rain. Not a crude spill. |
| `WELL-0567` | `CTX-0567-001` | `INS-0567-0157` | `rainwater_soil_false_positive` | Inspection INS-0567-0157: wet soil after rain. Not a crude spill. |
| `WELL-0570` | `CTX-0570-001` | `INS-0570-0188` | `rainwater_soil_false_positive` | Inspection INS-0570-0188: wet soil after rain. Not a crude spill. |
| `WELL-0571` | `CTX-0571-002` | `INS-0571-0149` | `rainwater_soil_false_positive` | Inspection INS-0571-0149: wet soil after rain. Not a crude spill. |
| `WELL-0572` | `CTX-0572-001` | `INS-0572-0140` | `shadow_false_positive` | Inspection INS-0572-0140: shadow from the drive panel. Not a crude spill. |
| `WELL-0574` | `CTX-0574-001` | `INS-0574-0196` | `shadow_false_positive` | Inspection INS-0574-0196: shadow from the pump jack. Not a crude spill. |
| `WELL-0575` | `CTX-0575-001` | `INS-0575-0127` | `shadow_false_positive` | Inspection INS-0575-0127: shadow from the pump jack. Not a crude spill. |
| `WELL-0583` | `CTX-0583-001` | `INS-0583-0206` | `produced_water_washout_false_positive` | Inspection INS-0583-0206: produced water from a washout, no crude. Not a crude spill. |
| `WELL-0585` | `CTX-0585-001` | `INS-0585-0139` | `shadow_false_positive` | Inspection INS-0585-0139: shadow from the pump jack. Not a crude spill. |
| `WELL-0590` | `CTX-0590-001` | `INS-0590-0026` | `produced_water_washout_false_positive` | Inspection INS-0590-0026: produced water from a washout, no crude. Not a crude spill. |
| `WELL-0591` | `CTX-0591-001` | `INS-0591-0064` | `produced_water_washout_false_positive` | Inspection INS-0591-0064: produced water from a washout, no crude. Not a crude spill. |
| `WELL-0598` | `CTX-0598-001` | `INS-0598-0145` | `produced_water_washout_false_positive` | Inspection INS-0598-0145: produced water from a washout, no crude. Not a crude spill. |
| `WELL-0600` | `CTX-0600-002` | `INS-0600-0146` | `rainwater_soil_false_positive` | Inspection INS-0600-0146: wet soil after rain. Not a crude spill. |

## 6. Multi-Note Inspections & Disagreements

Total multi-note inspections found: **1**.
### Inspection `INS-0101-0197` on `WELL-0101`
- **`CTX-0101-002`** (by `U-104` as `operator_feedback`): Inspection INS-0101-0197: I think this was only produced water, not crude.
- **`CTX-0101-003`** (by `U-402` as `operator_feedback`): Inspection INS-0101-0197: sampled the stain, it is crude oil. The detection stands.

## 7. Free-Text Repair Reports (`maintenance-reports/*.md`)

- **Reports on Disk:** `4437`
- **Maintenance References:** `4437`
- **Resolved References:** `4437` (Path Resolution: **100.0%**)
- **Broken References:** `0`

### Distinct Markdown Section Headers

| Section Header | Report Frequency | Meaning / Context |
| :--- | :--- | :--- |
| `## What happened` | `4437` | Common structure |
| `## Root cause` | `4437` | Common structure |
| `## Safety and permits` | `4437` | Common structure |
| `## Testing and return to service` | `4437` | Common structure |
| `## Compliance check` | `4437` | Common structure |
| `## Notes and recommendations` | `4437` | Common structure |
| `## Work done` | `4400` | Common structure |
| `## Parts and cost` | `4400` | Common structure |
| `## Spill clean-up and waste` | `1806` | Common structure |
| `## Waste` | `869` | Common structure |
| `## Work done so far` | `37` | Common structure |
| `## Parts and cost (estimate; work in progress)` | `37` | Common structure |
| `# Maintenance Report — MNT-0001-002` | `1` | Common structure |
| `# Maintenance Report — MNT-0001-005` | `1` | Common structure |
| `# Maintenance Report — MNT-0001-008` | `1` | Common structure |
| `# Maintenance Report — MNT-0001-009` | `1` | Common structure |
| `# Maintenance Report — MNT-0001-011` | `1` | Common structure |
| `# Maintenance Report — MNT-0001-014` | `1` | Common structure |
| `# Maintenance Report — MNT-0001-016` | `1` | Common structure |
| `# Maintenance Report — MNT-0001-023` | `1` | Common structure |

## 8. Calibration Anchors 1–6 Ground-Truth Verification

| Anchor # | Scenario Ref | Asset ID | Status | Description |
| :--- | :--- | :--- | :--- | :--- |
| **1** | `Q1` | `WELL-0001` | **`FAILED`** | WELL-0001 latest inspection, 3.2 C delta T (non-producing), Ryan Brooks U-104, stale active status |
| **2** | `Q4` | `WELL-0001` | **`PASSED`** | WELL-0001 4-year spills: 7 raw detections, 1 corrected rainwater (INS-0001-0070), 6 real spills = 15.1 bbl |
| **3** | `Q5` | `WELL-0001` | **`PASSED`** | WELL-0001 2025 downtime: 3 non-producing inspections = 21 days downtime, hot-day 8.5 C delta |
| **4** | `Q2 / Q12` | `NE-08` | **`FAILED`** | Northeast Block 8 latest inspections: exactly 4 non-producing wells (WELL-0164, WELL-0170, WELL-0172, WELL-0175) |
| **5** | `Q10 / Q13` | `WELL-0082 / WELL-0100 / WELL-0151` | **`PASSED`** | Spill containment hours in repair reports: WELL-0082 (7.1h), WELL-0100 (8.1h), WELL-0151 (6.4h, 4.5 bbl) |
| **6** | `Q18` | `WELL-0101` | **`PASSED`** | WELL-0101 INS-0101-0197 1.0 bbl detection, conflicting notes CTX-0101-002 vs CTX-0101-003, repair MNT-0101-029 |
