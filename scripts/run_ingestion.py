#!/usr/bin/env python3
"""Unified Ingestion Pipeline CLI for FlytBase Asset Intelligence Copilot.

Orchestrates Phases 2 through 5:
  - Phase 2: Raw Structured JSON/JSONL Ingestion
  - Phase 3: Fleet Manual & SOP Rule Registry Compilation
  - Phase 4: Free-Text Repair Report Compilation
  - Phase 5: Historical Context & Corrections Ledger Compilation

Executes the entire end-to-end compilation in under 15 seconds.
"""

import argparse
import sys
import time
from pathlib import Path

# Add workspace root to sys.path
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from backend.config.settings import get_settings
from backend.db.views import init_views
from backend.ingestion.compile_context import compile_context_data
from backend.ingestion.compile_reports import compile_reports_data
from backend.ingestion.compile_rules import compile_rules_data
from backend.ingestion.ingest_raw import ingest_raw_data


def run_pipeline(
    data_dir: Path,
    db_path: Path,
    mode: str = "rebuild",
    reference_today: str = "2026-10-17",
) -> None:
    """Run Phases 2 to 5 end-to-end against the specified dataset directory."""
    print("==================================================================")
    print("FlytBase Asset Intelligence Copilot: Ingestion & Compiler Pipeline")
    print("==================================================================")
    print(f"Dataset root:    {data_dir}")
    print(f"Target DuckDB:   {db_path}")
    print(f"Ingestion mode:  {mode}")
    print(f"Reference today: {reference_today}")
    print("------------------------------------------------------------------")

    t_global = time.time()

    # Phase 2: Raw Ingestion
    print("\n[Phase 2] Ingesting raw JSON/JSONL tables...")
    t0 = time.time()
    res_p2 = ingest_raw_data(
        dataset_root=data_dir,
        db_path=db_path,
        mode=mode,
        reference_today=reference_today,
    )
    print(f"  ✓ Phase 2 completed in {time.time() - t0:.2f}s | {res_p2['counts']}")

    # Phase 3: Rules Compiler
    print("\n[Phase 3] Compiling fleet manuals and SOP rules...")
    t0 = time.time()
    res_p3 = compile_rules_data(dataset_root=data_dir, db_path=db_path)
    print(
        f"  ✓ Phase 3 completed in {time.time() - t0:.2f}s | "
        f"Rules: {res_p3['rules_registry_count']}, SOPs: {res_p3['sop_protocols_count']}"
    )

    # Phase 4: Repair Reports Compiler
    print("\n[Phase 4] Compiling free-text maintenance reports...")
    t0 = time.time()
    res_p4 = compile_reports_data(dataset_root=data_dir, db_path=db_path)
    print(
        f"  ✓ Phase 4 completed in {time.time() - t0:.2f}s | "
        f"Parsed reports: {res_p4['total_reports_parsed']}"
    )

    # Phase 5: Context & Corrections Compiler
    print("\n[Phase 5] Compiling historical context & corrections ledger...")
    t0 = time.time()
    res_p5 = compile_context_data(dataset_root=data_dir, db_path=db_path)
    print(
        f"  ✓ Phase 5 completed in {time.time() - t0:.2f}s | "
        f"Corrections: {res_p5['corrections_ledger_count']}, Enriched notes: {res_p5['enriched_context_notes_count']}"
    )

    # Phase 6: Semantic Overlay SQL Views
    print("\n[Phase 6] Initializing Semantic Overlay SQL Views...")
    t0 = time.time()
    init_views(db_path=db_path, ref_date=reference_today)
    print(f"  ✓ Phase 6 completed in {time.time() - t0:.2f}s | 5 Semantic Views initialized")

    total_time = time.time() - t_global
    print("\n==================================================================")
    print(f"Pipeline finished successfully in {total_time:.2f} seconds!")
    print("==================================================================")


def main():
    settings = get_settings()
    parser = argparse.ArgumentParser(description="FlytBase Copilot Ingestion Pipeline")
    parser.add_argument(
        "--data-dir",
        type=str,
        default=str(settings.dataset_path),
        help="Path to dataset directory (e.g., sample-data or test-data)",
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default=str(settings.artifacts_path / "copilot.duckdb"),
        help="Path to target DuckDB file",
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["rebuild", "merge"],
        default="rebuild",
        help="Ingestion mode ('rebuild' drops existing, 'merge' appends/updates)",
    )
    parser.add_argument(
        "--today",
        type=str,
        default=settings.REFERENCE_TODAY,
        help="Reference today date (default: 2026-10-17)",
    )
    args = parser.parse_args()

    run_pipeline(
        data_dir=Path(args.data_dir),
        db_path=Path(args.db_path),
        mode=args.mode,
        reference_today=args.today,
    )


if __name__ == "__main__":
    main()
