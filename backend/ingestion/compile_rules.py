"""Phase 3: Manual & SOP Rule Registry Compiler (Markdown -> SQL)."""

import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add workspace root to sys.path
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

import duckdb

from backend.config.settings import get_settings
from backend.db.connection import get_db_connection
from backend.db.schema import init_database_schema


def parse_markdown_sections(markdown_text: str) -> Dict[str, Dict[str, str]]:
    """Parse Markdown text into structured headings and their raw content."""
    sections: Dict[str, Dict[str, str]] = {}
    current_heading = "Header"
    current_content: List[str] = []

    for line in markdown_text.splitlines():
        if line.startswith("#"):
            content_str = "\n".join(current_content).strip()
            if not content_str:
                content_str = f"{current_heading} (Section header)"
            sections[current_heading] = {
                "heading": current_heading,
                "content": content_str,
            }
            current_heading = line.strip()
            current_content = []
        else:
            current_content.append(line)

    content_str = "\n".join(current_content).strip()
    if not content_str:
        content_str = f"{current_heading} (Section header)"
    sections[current_heading] = {
        "heading": current_heading,
        "content": content_str,
    }

    return sections


class RulesCompiler:
    """Deterministic parser and compiler for fleet manuals and SOPs."""

    def __init__(self, dataset_root: Path, db_path: Optional[Path] = None):
        self.dataset_root = dataset_root.resolve()
        self.db_path = db_path
        self.fleet_dir = self.dataset_root / "fleet"

    def compile(self) -> Dict[str, Any]:
        """Compile all manuals and SOPs into rules_registry and sop_protocols tables."""
        con = get_db_connection(db_path=self.db_path)
        try:
            init_database_schema(con, drop_existing=True, phases=[3])

            rules_rows: List[Tuple] = []
            sop_rows: List[Tuple] = []
            now_iso = datetime.now(timezone.utc).isoformat()

            # 1. Parse T200.md
            t200_path = self.fleet_dir / "well-types" / "T200.md"
            with open(t200_path, "r", encoding="utf-8") as f:
                t200_text = f.read()

            t200_sections = parse_markdown_sections(t200_text)

            # Extract T200 Delta T
            m_t200_delta = re.search(r"at least\s+\*\*(\d+(?:\.\d+)?)\s*°C\s+above ambient\*\*", t200_text, re.I)
            t200_delta = float(m_t200_delta.group(1)) if m_t200_delta else 15.0

            # Extract T200 Max Temp
            m_t200_alarm = re.search(r"stay\s+\*\*at or below\s+(\d+(?:\.\d+)?)\s*°C\*\*", t200_text, re.I)
            t200_alarm = float(m_t200_alarm.group(1)) if m_t200_alarm else 85.0

            # Extract T200 RCA repairs count
            m_t200_rca = re.search(r"(Three|\d+)\s+or more\s+\*\*corrective\*\*\s+maintenance events.*?(\d+)\s+months", t200_text, re.I | re.DOTALL)
            t200_rca_threshold = 3.0
            t200_rca_window = 365

            # T200 Rules
            rules_rows.append((
                "RULE-PROD-DELTA-T200-BASE",
                "MIN_PRODUCING_TEMP_DELTA_C",
                "well_type",
                "T200",
                "ALL",
                "GTE",
                t200_delta,
                "celsius",
                None,
                "T200.md §9.3",
                "fleet/well-types/T200.md",
                "A T200 well is considered producing (active) when its wellhead temperature is at least 15 °C above ambient air temperature at the time of the reading.",
                True, False, None, None, None, now_iso
            ))

            rules_rows.append((
                "RULE-TEMP-ALARM-T200-BASE",
                "MAX_TEMP_ALARM_C",
                "well_type",
                "T200",
                "ALL",
                "LTE",
                t200_alarm,
                "celsius",
                None,
                "T200.md §9.4",
                "fleet/well-types/T200.md",
                "The wellhead must stay at or below 85 °C. Any reading above 85 °C requires the operator to shut in and inspect the stuffing box and rod string within 24 hours.",
                True, False, None, None, None, now_iso
            ))

            rules_rows.append((
                "RULE-SPILL-SHUTIN-T200-BASE",
                "SPILL_SHUTIN_PAD_AREA_PCT",
                "well_type",
                "T200",
                "ALL",
                "LTE",
                5.0,
                "percent",
                None,
                "T200.md §9.5",
                "fleet/well-types/T200.md",
                "If a spill covers more than 5 % of the pad area, shut in the well immediately and keep it shut in until the source is repaired.",
                True, False, None, None, None, now_iso
            ))

            rules_rows.append((
                "RULE-PLANNED-SHUTIN-T200-BASE",
                "PLANNED_SHUTIN_MAINT_LOG_REQUIRED",
                "well_type",
                "T200",
                "ALL",
                "EQ",
                1.0,
                "boolean",
                None,
                "T200.md §4.4",
                "fleet/well-types/T200.md",
                "record the shut-in in the maintenance system before work starts.",
                True, False, None, None, None, now_iso
            ))

            rules_rows.append((
                "RULE-RCA-REPAIRS-T200-BASE",
                "CORRECTIVE_REPAIRS_RCA_THRESHOLD",
                "well_type",
                "T200",
                "ALL",
                "GTE",
                t200_rca_threshold,
                "repairs_per_12m",
                t200_rca_window,
                "T200.md §10",
                "fleet/well-types/T200.md",
                "Three or more corrective maintenance events on the same equipment kind in the 12 months before the current date require a root-cause analysis (RCA) before the next repair is closed.",
                True, False, None, None, None, now_iso
            ))

            rules_rows.append((
                "RULE-DOWNTIME-ALERT-T200-BASE",
                "CONSECUTIVE_DOWNTIME_ESCALATION_DAYS",
                "well_type",
                "T200",
                "ALL",
                "GT",
                14.0,
                "days",
                None,
                "T200.md §10",
                "fleet/well-types/T200.md",
                "Downtime of more than 14 consecutive days must be reported to the area production supervisor.",
                True, False, None, None, None, now_iso
            ))

            # Store T200 sections into sop_protocols
            for heading, data in t200_sections.items():
                sec_id = f"T200-{re.sub(r'[^A-Za-z0-9]+', '-', heading).strip('-')}"
                sop_rows.append((
                    sec_id,
                    heading.lstrip("# ").strip(),
                    "well_manual_T200",
                    "T200",
                    None, None, None, None, None,
                    "fleet/well-types/T200.md",
                    heading,
                    data["content"]
                ))

            # 2. Parse T350.md
            t350_path = self.fleet_dir / "well-types" / "T350.md"
            with open(t350_path, "r", encoding="utf-8") as f:
                t350_text = f.read()

            t350_sections = parse_markdown_sections(t350_text)

            m_t350_delta = re.search(r"at least\s+\*\*(\d+(?:\.\d+)?)\s*°C\s+above\s+ambient\*\*", t350_text, re.I)
            t350_delta = float(m_t350_delta.group(1)) if m_t350_delta else 20.0

            m_t350_alarm = re.search(r"stay\s+\*\*at or below\s+(\d+(?:\.\d+)?)\s*°C\*\*", t350_text, re.I)
            t350_alarm = float(m_t350_alarm.group(1)) if m_t350_alarm else 95.0

            rules_rows.append((
                "RULE-PROD-DELTA-T350-BASE",
                "MIN_PRODUCING_TEMP_DELTA_C",
                "well_type",
                "T350",
                "ALL",
                "GTE",
                t350_delta,
                "celsius",
                None,
                "T350.md §3",
                "fleet/well-types/T350.md",
                "a T350 well is considered producing (active) only when its wellhead temperature is at least 20 °C above ambient air temperature at the time of the reading.",
                True, False, None, None, None, now_iso
            ))

            rules_rows.append((
                "RULE-TEMP-ALARM-T350-BASE",
                "MAX_TEMP_ALARM_C",
                "well_type",
                "T350",
                "ALL",
                "LTE",
                t350_alarm,
                "celsius",
                None,
                "T350.md §4",
                "fleet/well-types/T350.md",
                "The wellhead must stay at or below 95 °C. Above 95 °C, shut in and inspect within 24 hours.",
                True, False, None, None, None, now_iso
            ))

            # Cross-reference inheritance from T200
            rules_rows.append((
                "RULE-RCA-REPAIRS-T350-BASE",
                "CORRECTIVE_REPAIRS_RCA_THRESHOLD",
                "well_type",
                "T350",
                "ALL",
                "GTE",
                3.0,
                "repairs_per_12m",
                365,
                "T350.md §6 -> T200.md §10",
                "fleet/well-types/T350.md",
                "Same as T200 section 10 (RCA after three corrective events on the same equipment kind within 12 months; report downtime over 14 consecutive days).",
                True, False, None, None, None, now_iso
            ))

            rules_rows.append((
                "RULE-SPILL-SHUTIN-T350-BASE",
                "SPILL_SHUTIN_PAD_AREA_PCT",
                "well_type",
                "T350",
                "ALL",
                "LTE",
                5.0,
                "percent",
                None,
                "T350.md §5 -> T200.md §9.5",
                "fleet/well-types/T350.md",
                "Same as T200: a spill covering more than 5 % of the pad area requires immediate shut-in.",
                True, False, None, None, None, now_iso
            ))

            rules_rows.append((
                "RULE-PLANNED-SHUTIN-T350-BASE",
                "PLANNED_SHUTIN_MAINT_LOG_REQUIRED",
                "well_type",
                "T350",
                "ALL",
                "EQ",
                1.0,
                "boolean",
                None,
                "T350.md §1 -> T200.md §4.4",
                "fleet/well-types/T350.md",
                "Procedures not listed here follow the T200 manual.",
                True, False, None, None, None, now_iso
            ))

            for heading, data in t350_sections.items():
                sec_id = f"T350-{re.sub(r'[^A-Za-z0-9]+', '-', heading).strip('-')}"
                sop_rows.append((
                    sec_id,
                    heading.lstrip("# ").strip(),
                    "well_manual_T350",
                    "T350",
                    None, None, None, None, None,
                    "fleet/well-types/T350.md",
                    heading,
                    data["content"]
                ))

            # 2b. Parse T500.md if present
            t500_path = self.fleet_dir / "well-types" / "T500.md"
            if t500_path.exists():
                with open(t500_path, "r", encoding="utf-8") as f:
                    t500_text = f.read()

                t500_sections = parse_markdown_sections(t500_text)

                rules_rows.append((
                    "RULE-PROD-DELTA-T500-BASE",
                    "MIN_PRODUCING_TEMP_DELTA_C",
                    "well_type",
                    "T500",
                    "ALL",
                    "GTE",
                    25.0,
                    "celsius",
                    None,
                    "T500.md §3",
                    "fleet/well-types/T500.md",
                    "A T500 well is considered producing (active) only when its wellhead temperature is at least 25 °C above ambient air temperature at the time of the reading.",
                    True, False, None, None, None, now_iso
                ))

                rules_rows.append((
                    "RULE-TEMP-ALARM-T500-BASE",
                    "MAX_TEMP_ALARM_C",
                    "well_type",
                    "T500",
                    "ALL",
                    "LTE",
                    95.0,
                    "celsius",
                    None,
                    "T500.md §4",
                    "fleet/well-types/T500.md",
                    "The wellhead must stay at or below 95 °C. Above 95 °C, shut in and check drive and motor within 24 hours.",
                    True, False, None, None, None, now_iso
                ))

                rules_rows.append((
                    "RULE-RCA-REPAIRS-T500-ESP",
                    "CORRECTIVE_REPAIRS_RCA_THRESHOLD",
                    "well_type",
                    "T500",
                    "esp_pump",
                    "GTE",
                    2.0,
                    "repairs_per_12m",
                    365,
                    "T500.md §7",
                    "fleet/well-types/T500.md",
                    "Two or more corrective maintenance events on the ESP in the 12 months before the current date require a root-cause analysis (RCA) before the next repair is closed.",
                    True, False, None, None, None, now_iso
                ))

                rules_rows.append((
                    "RULE-RCA-REPAIRS-T500-OTHER",
                    "CORRECTIVE_REPAIRS_RCA_THRESHOLD",
                    "well_type",
                    "T500",
                    "ALL",
                    "GTE",
                    3.0,
                    "repairs_per_12m",
                    365,
                    "T500.md §7 -> T200.md §10",
                    "fleet/well-types/T500.md",
                    "For all other equipment, follow T200 section 10 (three events in 12 months).",
                    True, False, None, None, None, now_iso
                ))

                rules_rows.append((
                    "RULE-SPILL-SHUTIN-T500-BASE",
                    "SPILL_SHUTIN_PAD_AREA_PCT",
                    "well_type",
                    "T500",
                    "ALL",
                    "LTE",
                    5.0,
                    "percent",
                    None,
                    "T500.md §6 -> T200.md §9.5",
                    "fleet/well-types/T500.md",
                    "Same as T200: a spill covering more than 5 % of the pad area requires immediate shut-in.",
                    True, False, None, None, None, now_iso
                ))

                for heading, data in t500_sections.items():
                    sec_id = f"T500-{re.sub(r'[^A-Za-z0-9]+', '-', heading).strip('-')}"
                    sop_rows.append((
                        sec_id,
                        heading.lstrip("# ").strip(),
                        "well_manual_T500",
                        "T500",
                        None, None, None, None, None,
                        "fleet/well-types/T500.md",
                        heading,
                        data["content"]
                    ))

            # 2c. Parse operations-sop-rev2.md if present
            ops2_path = self.fleet_dir / "sops" / "operations-sop-rev2.md"
            if ops2_path.exists():
                with open(ops2_path, "r", encoding="utf-8") as f:
                    ops2_text = f.read()
                ops2_sections = parse_markdown_sections(ops2_text)

                sop_rows.extend([
                    ("OPS-1", "Gas Odor Field Response", "operations", "ALL", None, None, None, 12.0, None, "fleet/sops/operations-sop-rev2.md", "## OPS-1 Gas odor response", "Field response within 24h before 1 Jan 2027; within 12h from 1 Jan 2027."),
                    ("OPS-2", "Temporary Flowline Bypass Authorization", "operations", "ALL", None, None, None, None, None, "fleet/sops/operations-sop-rev2.md", "## OPS-2 Temporary bypass", "Allowed only on wells named in active MOC memos."),
                    ("OPS-3", "Status Evidence Precedence", "operations", "ALL", None, None, None, None, None, "fleet/sops/operations-sop-rev2.md", "## OPS-3 Status evidence precedence", "Most recent of inspection reading and shut-in/restart operator note."),
                    ("OPS-4", "Failure Classification Hierarchy", "operations", "ALL", None, None, None, None, None, "fleet/sops/operations-sop-rev2.md", "## OPS-4 Failure classification", "Order: Installation error, Sand, Scale, Gas interference, Corrosion, Electrical, Fatigue/wear, Other."),
                    ("OPS-5", "Freeze Protection (1 Dec - 28 Feb)", "operations", "ALL", None, None, None, None, 7.0, "fleet/sops/operations-sop-rev2.md", "## OPS-5 Freeze protection", "Ambient <= -5C on producing well requires heat trace check within 7 days."),
                    ("OPS-6", "Repeat Failure Window (30 Days)", "operations", "ALL", None, None, None, None, 30.0, "fleet/sops/operations-sop-rev2.md", "## OPS-6 Repeat failure", "Same equipment kind on same well starting within 30 days of previous corrective job."),
                ])

                for heading, data in ops2_sections.items():
                    sec_id = f"OPS2-{re.sub(r'[^A-Za-z0-9]+', '-', heading).strip('-')}"
                    sop_rows.append((
                        sec_id,
                        heading.lstrip("# ").strip(),
                        "operations_sop_rev2",
                        "ALL",
                        None, None, None, None, None,
                        "fleet/sops/operations-sop-rev2.md",
                        heading,
                        data["content"]
                    ))

            # 2d. Parse supplier recall notice if present
            recall_path = self.fleet_dir / "sops" / "supplier-recall-notice-2026-12-01.md"
            if recall_path.exists():
                with open(recall_path, "r", encoding="utf-8") as f:
                    recall_text = f.read()
                recall_sections = parse_markdown_sections(recall_text)
                for heading, data in recall_sections.items():
                    sec_id = f"RECALL-{re.sub(r'[^A-Za-z0-9]+', '-', heading).strip('-')}"
                    sop_rows.append((
                        sec_id,
                        heading.lstrip("# ").strip(),
                        "supplier_recall_notice",
                        "ALL",
                        None, None, None, None, 30.0,
                        "fleet/sops/supplier-recall-notice-2026-12-01.md",
                        heading,
                        data["content"]
                    ))

            # 2e. Parse MOC memos if present
            for moc_file in self.fleet_dir.glob("sops/moc-*.md"):
                with open(moc_file, "r", encoding="utf-8") as f:
                    moc_text = f.read()
                moc_sections = parse_markdown_sections(moc_text)
                rel_moc = str(moc_file.relative_to(self.dataset_root))
                for heading, data in moc_sections.items():
                    sec_id = f"{moc_file.stem.upper()}-{re.sub(r'[^A-Za-z0-9]+', '-', heading).strip('-')}"
                    sop_rows.append((
                        sec_id,
                        heading.lstrip("# ").strip(),
                        "management_of_change",
                        "ALL",
                        None, None, None, None, None,
                        rel_moc,
                        heading,
                        data["content"]
                    ))

            # 2f. Parse regulator letter if present
            reg_letter_path = self.fleet_dir / "sops" / "regulator-letter-2026-11-20.md"
            if reg_letter_path.exists():
                with open(reg_letter_path, "r", encoding="utf-8") as f:
                    reg_text = f.read()
                reg_sections = parse_markdown_sections(reg_text)
                for heading, data in reg_sections.items():
                    sec_id = f"REG-LETTER-{re.sub(r'[^A-Za-z0-9]+', '-', heading).strip('-')}"
                    sop_rows.append((
                        sec_id,
                        heading.lstrip("# ").strip(),
                        "regulator_letter",
                        "ALL",
                        None, 5.0, None, None, None,
                        "fleet/sops/regulator-letter-2026-11-20.md",
                        heading,
                        data["content"]
                    ))

            # 3. Parse spill-response-sop.md
            sr_path = self.fleet_dir / "sops" / "spill-response-sop.md"
            with open(sr_path, "r", encoding="utf-8") as f:
                sr_text = f.read()

            sr_sections = parse_markdown_sections(sr_text)

            # Spill severity classes
            spill_classes = [
                ("SOP-CLASS-MINOR", "Minor Spill", "spill_response", "ALL", "minor", 0.0, 1.0, None, None, "fleet/sops/spill-response-sop.md", "## 3. Spill classes", "below 1 bbl: Record and clean up; no external report"),
                ("SOP-CLASS-MODERATE", "Moderate Spill", "spill_response", "ALL", "moderate", 1.0, 5.0, 72.0, None, "fleet/sops/spill-response-sop.md", "## 3. Spill classes", "1 bbl to below 5 bbl: Record, clean up, notify HSE within 72 h"),
                ("SOP-CLASS-REPORTABLE", "Reportable Spill", "spill_response", "ALL", "reportable", 5.0, 25.0, 24.0, None, "fleet/sops/spill-response-sop.md", "## 3. Spill classes", "5 bbl to below 25 bbl: External report required (SR-01) within 24h"),
                ("SOP-CLASS-MAJOR", "Major Spill", "spill_response", "ALL", "major", 25.0, None, 2.0, None, "fleet/sops/spill-response-sop.md", "## 3. Spill classes", "25 bbl or more: External report within 2 h (company rule), incident command"),
            ]
            sop_rows.extend(spill_classes)

            # Protocols SR-01 through SR-04
            sr_protocols = [
                ("SR-01", "Written Spill Reporting Deadline", "spill_response", "ALL", "reportable", 5.0, None, 24.0, None, "fleet/sops/spill-response-sop.md", "## 4. Protocols", "file the written notice (volume, affected area, cleanup plan) within 24 hours of discovery, or within 2 hours for a major spill."),
                ("SR-02", "Spill Source Isolation and Containment Limit", "spill_response", "ALL", None, None, None, 4.0, None, "fleet/sops/spill-response-sop.md", "## 4. Protocols", "The source must be stopped and the spill contained within 4 hours of discovery."),
                ("SR-03", "Soil Cleanup Target and Remediation Verification", "spill_response", "ALL", "reportable", 5.0, None, None, 60.0, "fleet/sops/spill-response-sop.md", "## 4. Protocols", "Contaminated soil must be cleaned to 1.0% TPH or less. Take at least 4 soil samples... remediation must be verified within 60 days of discovery by agency."),
                ("SR-04", "Asset Spill Record Duty", "spill_response", "ALL", None, None, None, None, None, "fleet/sops/spill-response-sop.md", "## 4. Protocols", "Every spill, including minor ones, must be recorded against the asset with an estimated volume and affected area."),
            ]
            sop_rows.extend(sr_protocols)

            # Add SR rules to rules_registry
            rules_rows.append((
                "RULE-SR01-REPORTING-THRESHOLD",
                "SPILL_REPORTABLE_MIN_BBL",
                "fleet",
                "ALL",
                "ALL",
                "GTE",
                5.0,
                "barrels",
                None,
                "SR-01",
                "fleet/sops/spill-response-sop.md",
                "Our reporting threshold (5 bbl or more) is slightly stricter than more than 5 bbl.",
                True, False, None, None, None, now_iso
            ))

            rules_rows.append((
                "RULE-SR01-DEADLINE-HOURS",
                "SPILL_REPORTING_DEADLINE_HOURS",
                "fleet",
                "ALL",
                "ALL",
                "LTE",
                24.0,
                "hours",
                None,
                "SR-01",
                "fleet/sops/spill-response-sop.md",
                "file the written notice (volume, affected area, cleanup plan) within 24 hours of discovery",
                True, False, None, None, None, now_iso
            ))

            rules_rows.append((
                "RULE-SR02-CONTAINMENT-HOURS",
                "SPILL_CONTAINMENT_LIMIT_HOURS",
                "fleet",
                "ALL",
                "ALL",
                "LTE",
                4.0,
                "hours",
                None,
                "SR-02",
                "fleet/sops/spill-response-sop.md",
                "The source must be stopped and the spill contained within 4 hours of discovery.",
                True, False, None, None, None, now_iso
            ))

            rules_rows.append((
                "RULE-SR03-VERIFICATION-DAYS",
                "SPILL_CLEANUP_VERIFICATION_DAYS",
                "fleet",
                "ALL",
                "ALL",
                "LTE",
                60.0,
                "days",
                None,
                "SR-03",
                "fleet/sops/spill-response-sop.md",
                "For reportable and major spills, the remediation must be verified within 60 days of discovery",
                True, False, None, None, None, now_iso
            ))

            rules_rows.append((
                "RULE-SR03-TPH-TARGET",
                "TPH_CLEANUP_TARGET_PCT",
                "fleet",
                "ALL",
                "ALL",
                "LTE",
                1.0,
                "percent",
                None,
                "SR-03",
                "fleet/sops/spill-response-sop.md",
                "Contaminated soil must be cleaned to 1.0% TPH or less.",
                True, False, None, None, None, now_iso
            ))

            rules_rows.append((
                "RULE-SR03-MIN-SAMPLES",
                "MIN_SOIL_SAMPLES",
                "fleet",
                "ALL",
                "ALL",
                "GTE",
                4.0,
                "count",
                None,
                "SR-03",
                "fleet/sops/spill-response-sop.md",
                "Take at least 4 soil samples to map the edges of a reportable spill.",
                True, False, None, None, None, now_iso
            ))

            # 4. Parse regulatory-compliance-sop.md
            rc_path = self.fleet_dir / "sops" / "regulatory-compliance-sop.md"
            with open(rc_path, "r", encoding="utf-8") as f:
                rc_text = f.read()

            rc_protocols = [
                ("RC-01", "Inspection Frequency", "regulatory_compliance", "ALL", None, None, None, None, 14.0, "fleet/sops/regulatory-compliance-sop.md", "## 2. Protocols", "Every well must be inspected at least once every 14 days."),
                ("RC-02", "Annual Flowline Integrity Test", "regulatory_compliance", "ALL", None, None, None, None, 365.0, "fleet/sops/regulatory-compliance-sop.md", "## 2. Protocols", "Every flowline must pass an integrity test once per calendar year."),
                ("RC-03", "Extended Downtime Reporting", "regulatory_compliance", "ALL", None, None, None, None, 14.0, "fleet/sops/regulatory-compliance-sop.md", "## 2. Protocols", "Any well down for more than 14 consecutive days must be reported to the area production supervisor."),
                ("RC-04", "Notice of Violation Response Deadline", "regulatory_compliance", "ALL", None, None, None, None, 30.0, "fleet/sops/regulatory-compliance-sop.md", "## 2. Protocols", "Agency notices of violation must be answered within 30 days and tracked until closed."),
                ("RC-05", "Flowline Maintenance Program", "regulatory_compliance", "ALL", None, None, None, None, None, "fleet/sops/regulatory-compliance-sop.md", "## 2. Protocols", "Keep a flowline maintenance program: weekly visual inspection of pad and flowline route, corrective repair, prompt cleanup."),
            ]
            sop_rows.extend(rc_protocols)

            rules_rows.append((
                "RULE-RC01-INSPECTION-INTERVAL",
                "INSPECTION_MAX_INTERVAL_DAYS",
                "fleet",
                "ALL",
                "ALL",
                "LTE",
                14.0,
                "days",
                None,
                "RC-01",
                "fleet/sops/regulatory-compliance-sop.md",
                "Every well must be inspected at least once every 14 days.",
                True, False, None, None, None, now_iso
            ))

            rules_rows.append((
                "RULE-RC02-FLOWLINE-ANNUAL-DAYS",
                "ANNUAL_FLOWLINE_TEST_MAX_DAYS",
                "fleet",
                "ALL",
                "flowline",
                "LTE",
                365.0,
                "days",
                None,
                "RC-02",
                "fleet/sops/regulatory-compliance-sop.md",
                "Every flowline must pass an integrity test once per calendar year.",
                True, False, None, None, None, now_iso
            ))

            rules_rows.append((
                "RULE-RC04-NOV-RESPONSE-DAYS",
                "NOV_RESPONSE_DEADLINE_DAYS",
                "fleet",
                "ALL",
                "ALL",
                "LTE",
                30.0,
                "days",
                None,
                "RC-04",
                "fleet/sops/regulatory-compliance-sop.md",
                "Agency notices of violation must be answered within 30 days and tracked until closed.",
                True, False, None, None, None, now_iso
            ))

            # 5. Parse field-work-sop.md
            ws_path = self.fleet_dir / "sops" / "field-work-sop.md"
            with open(ws_path, "r", encoding="utf-8") as f:
                ws_text = f.read()

            ws_protocols = [
                ("WS-01", "Pre-job Safety Meeting (JSA)", "field_work", "ALL", None, None, None, None, None, "fleet/sops/field-work-sop.md", "## 3. Protocols", "Hold and record a pre-job safety meeting (job safety analysis) with the whole crew before any work starts."),
                ("WS-02", "Energy Isolation (LOTO)", "field_work", "ALL", None, None, None, None, None, "fleet/sops/field-work-sop.md", "## 3. Protocols", "Isolate energy before touching moving or pressurised equipment. Stop prime mover, chain brake, lockout/tagout, bleed pressure."),
                ("WS-03", "H2S Monitoring & Stop-Work Limit", "field_work", "ALL", None, None, None, None, None, "fleet/sops/field-work-sop.md", "## 3. Protocols", "Personal H2S monitor bump-tested. If reading >= 10 ppm, stop work, move upwind."),
                ("WS-04", "Hot Work Permit & Flammable Gas Limit", "field_work", "ALL", None, None, None, None, None, "fleet/sops/field-work-sop.md", "## 3. Protocols", "Hot work permit and gas test. No hot work while flammable gas >= 10% LEL."),
                ("WS-05", "Flowline Pressure Testing", "field_work", "ALL", None, None, None, 4.0, None, "fleet/sops/field-work-sop.md", "## 3. Protocols", "Pressure-test repaired section at >= 1.25 x MOP and hold for 4 hours with no unexplained drop."),
                ("WS-06", "Oily Waste Management & Disposal Manifest", "field_work", "ALL", None, None, None, None, None, "fleet/sops/field-work-sop.md", "## 3. Protocols", "Contaminated soil, absorbents, parts are waste. Record quantity and ship with waste manifest."),
                ("WS-07", "Maintenance Report Close-out & Compliance Check", "field_work", "ALL", None, None, None, None, 3.0, "fleet/sops/field-work-sop.md", "## 3. Protocols", "Write the maintenance report within 3 days of finishing the work. Include compliance check."),
            ]
            sop_rows.extend(ws_protocols)

            # Insert into DuckDB
            con.executemany(
                """
                INSERT OR REPLACE INTO rules_registry VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rules_rows,
            )

            con.executemany(
                """
                INSERT OR REPLACE INTO sop_protocols VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                sop_rows,
            )

            rules_count = con.execute("SELECT count(*) FROM rules_registry").fetchone()[0]
            sop_count = con.execute("SELECT count(*) FROM sop_protocols").fetchone()[0]

            return {
                "status": "success",
                "rules_registry_count": rules_count,
                "sop_protocols_count": sop_count,
            }
        finally:
            con.close()


def compile_rules_data(
    dataset_root: Optional[Path] = None,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """CLI/API wrapper to compile fleet rules."""
    settings = get_settings()
    d_root = (dataset_root or settings.dataset_path).resolve()
    compiler = RulesCompiler(dataset_root=d_root, db_path=db_path)
    return compiler.compile()


if __name__ == "__main__":
    res = compile_rules_data()
    print("Rules compilation result:", res)
