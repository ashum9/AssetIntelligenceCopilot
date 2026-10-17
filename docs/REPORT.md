# FlytBase Asset Intelligence Copilot
## Final Evaluation Report: Architecture, Technical Moats & 11 Benchmark Questions

---

# Page 1: System Design, Architecture & Technical Moats

### 1. Architectural Philosophy: The Dual Epistemic Split
The FlytBase Asset Intelligence Copilot is engineered around a fundamental principle: **LLMs must never calculate compliance numbers, generate free-form SQL queries, or mutate operational state without verification.** Compliance and safety decisions in critical energy infrastructure require auditability, mathematical monotonicity, and forensic reproducibility. 

We decouple the system into three distinct layers:
1. **Immutable Bitemporal Ledger:** Records every telemetry reading, work order, supervisor correction, and drone observation with both *Valid Time* (when the event occurred) and *Recorded Time* (when the system learned of it).
2. **Belief State (Bayesian Epistemics):** Maintains calibrated probability distributions over latent asset conditions (e.g. wellhead flow state, true spill volume, gas hazard severity), surfacing operational doubts, measurement drift, and indirect prompt injections.
3. **Record of Reference (Deterministic Semantic Layer):** Executed exclusively via vectorized DuckDB SQL views over strict domain rules (§9.3 thermal thresholds, SR-01/02/03 spill protocols, RC-01..05 compliance, and OPS-1..06 standard operating procedures).

```
   ┌────────────────────────────────────────────────────────────────────────┐
   │                    USER INTERACTION & CHAT INTERFACE                  │
   │           Next.js 15 App Router · Typed Visual Component Protocol      │
   └───────────────────────────────────┬────────────────────────────────────┘
                                       │
                                       ▼
   ┌────────────────────────────────────────────────────────────────────────┐
   │                    AGENTIC INTENT & ROUTING CORE                       │
   │     Gemma 4 Routing Model · Typed QueryPlan Generator (Metric/Window)  │
   │               Echo Window Interpretation ("Nov 1 -> Jan 15")           │
   └───────────────────┬────────────────────────────────┬───────────────────┘
                       │                                │
                       ▼                                ▼
   ┌─────────────────────────────────────┐  ┌───────────────────────────────┐
   │     HARDENED WRITE PATH (LEDGER)    │  │   DETERMINISTIC SEMANTIC SQL  │
   │ Propose ➔ Diff ➔ Confirm ➔ Commit  │  │  v_effective_inspections (125k)│
   │ Asymmetric Verification (Dual-Sign) │  │  v_well_current_status (600)  │
   │ Data-Layer ACL Isolation (Team/Area)│  │  v_spill_compliance_audit     │
   │ Bitemporal Ledger (ASOF Replays)   │  │  v_equipment_rca_tracker      │
   └─────────────────────────────────────┘  └───────────────┬───────────────┘
                                                            │
                                                            ▼
   ┌────────────────────────────────────────────────────────────────────────┐
   │                    DUAL EPISTEMIC SYNTHESIS ENGINE                     │
   │ Record of Reference (Statutory)  vs  Calibrated Belief State (Physics) │
   │ Active Probing & EVOI Engine ($ Value of Drone Verification Flight)    │
   └───────────────────────────────────┬────────────────────────────────────┘
                                       │
                                       ▼
   ┌────────────────────────────────────────────────────────────────────────┐
   │                   GENERATIVE UI CONTRACT (RENDERER)                   │
   │ StatusCard · RankedTable · LineChart · StackedBar · DiffBadge · Cards │
   └────────────────────────────────────────────────────────────────────────┘
```

### 2. Core Technical Moats & System Innovations
- **Hardened Write Path (`Propose ➔ Diff ➔ Confirm ➔ Commit`):** Any operational override (chat claims, replaced equipment, verbal status changes) creates an uncommitted proposal with a cryptographic diff badge (`OverrideDiffBadge`). Obligation-reducing changes (e.g. downgrading a spill or clearing a recall) require supervisor-grade credentials or two-party authorization.
- **Data-Layer ACL Isolation:** Team boundaries (TEAM-SW, TEAM-NE, TEAM-SE, TEAM-NW, TEAM-HSE) are enforced mathematically inside SQL predicates, eliminating model hallucination and indirect prompt injection attacks.
- **Expected Value of Information (EVOI) Probing Engine:** Quantifies economic risk around regulatory cutoffs (e.g. a 4.8 bbl spill with 20% CV error has a 36.9% chance of triggering statutory $5,000 reporting fines; drone verification yields a $+\$1,295$ net EVOI to dispatch before the statutory window expires).
- **Sub-Second Offline Compilation:** Fully compiles 600 wells, 125,198 inspections, 17,415 maintenance records, 4,437 free-text markdown repair reports, and 1,887 context notes in **10.53 seconds** into an embedded DuckDB instance.

---

# Page 2: Benchmark Results & Outputs (Q1 to Q6)

All queries executed on the **Test Dataset** (600 wells, 7 areas, reference date **15 Jan 2027**).

### Q1. Reservoir Pressure (Michael Turner, TEAM-NE)
- **Prompt:** *"All our wells feed one reservoir. Map the reservoir pressure across the field from the pressure data."*
- **Epistemic Answer & Reasoning:** **Cannot be answered from the data.** The telemetry collects surface wellhead temperature, ambient temperature, spill detection, and visual/manual observations. Maintenance records document routine hydrostatic pressure tests on flowlines and valves (WS-05), but **no downhole, casing, tubing, or reservoir pressure gauges exist** in the system. The copilot refuses to fabricate numbers or hallucinate a spatial pressure map, and recommends sonolog fluid-level testing or bottomhole pressure gauges.

### Q2. Best Producer in 2026 (Robert Hayes, TEAM-MX)
- **Prompt:** *"Which well produced the most oil in 2026?"*
- **Epistemic Answer & Reasoning:** **Cannot be answered from the data.** Volumetric production (bbl/day or total oil volume) is unmetered across the field. Production telemetry is binary (producing vs downtime) governed by wellhead-to-ambient thermal differential thresholds ($\Delta T \ge 15^\circ\text{C}$ for T200, $\ge 20^\circ\text{C}$ for T350, $\ge 25^\circ\text{C}$ for T500). In 2026, **412 wells achieved 100% operational uptime** (365 days / 0 downtime days across all 52 weekly inspections). While T500 wells utilize high-rate electric submersible pumps (ESP-400), actual volume produced cannot be determined without multiphase surface flow meters.

### Q3. Gas Odor Reports Since 1 Nov 2026 (Laura Simmons, TEAM-HSE)
- **Prompt:** *"Since 1 Nov 2026, every time an operator note reports gas at a well, did we get someone out to that well in time under our operating procedures? List every report and whether the response met the deadline."*
- **Rule (OPS-1):** Field response required within **24h before 1 Jan 2027**; cut to **12h from 1 Jan 2027**. Manual inspection or maintenance job counts; drone inspections do not.
- **Summary:** **26 total reports** | **17 Met** | **9 Missed**.

| Well | Area | Reported At (UTC) | Response (Record ID & Time) | Hours to Response | Deadline | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **WELL-0163** | Northeast Block 8 | 2026-11-03 20:55 | MNT-0163-019 at 2026-11-14 08:00 | 251.1h | 24 hours | **Missed** |
| **WELL-0149** | Northeast Block 7 | 2026-11-06 18:20 | MNT-0149-029 at 2026-11-07 08:00 | 13.7h | 24 hours | **Met** |
| **WELL-0165** | Northeast Block 8 | 2026-11-13 20:35 | MNT-0165-031 at 2026-11-14 08:00 | 11.4h | 24 hours | **Met** |
| **WELL-0341** | Northwest Block 12 | 2026-11-19 07:40 | INS-0341-0109 at 2026-12-17 13:30 | 677.8h | 24 hours | **Missed** |
| **WELL-0091** | Southwest Block 24 | 2026-11-27 22:25 | MNT-0091-019 at 2026-11-28 08:00 | 9.6h | 24 hours | **Met** |
| **WELL-0423** | Northwest Block 12 | 2026-12-03 05:25 | INS-0423-0213 at 2026-12-03 09:15 | 3.8h | 24 hours | **Met** |
| **WELL-0059** | Southwest Block 24 | 2026-12-03 06:10 | INS-0059-0213 at 2026-12-03 12:15 | 6.1h | 24 hours | **Met** |
| **WELL-0332** | Northwest Block 12 | 2026-12-03 12:10 | none | - | 24 hours | **Missed** |
| **WELL-0401** | Northwest Block 12 | 2026-12-05 13:50 | MNT-0401-033 at 2026-12-11 08:00 | 138.2h | 24 hours | **Missed** |
| **WELL-0189** | Northeast Block 8 | 2026-12-10 12:35 | MNT-0189-037 at 2026-12-11 08:00 | 19.4h | 24 hours | **Met** |
| **WELL-0403** | Northwest Block 12 | 2026-12-10 21:15 | MNT-0403-024 at 2026-12-11 08:00 | 10.8h | 24 hours | **Met** |
| **WELL-0244** | Southeast Block 31 | 2026-12-11 05:25 | MNT-0244-026 at 2026-12-11 08:00 | 2.6h | 24 hours | **Met** |
| **WELL-0040** | Southwest Block 23 | 2026-12-12 01:55 | MNT-0040-029 at 2026-12-12 08:00 | 6.1h | 24 hours | **Met** |
| **WELL-0228** | Southeast Block 31 | 2026-12-16 19:50 | INS-0228-0144 at 2026-12-17 12:45 | 16.9h | 24 hours | **Met** |
| **WELL-0052** | Southwest Block 24 | 2026-12-18 06:45 | none | - | 24 hours | **Missed** |
| **WELL-0370** | Northwest Block 12 | 2026-12-21 12:45 | MNT-0370-028 at 2026-12-22 08:00 | 19.2h | 24 hours | **Met** |
| **WELL-0362** | Northwest Block 12 | 2026-12-24 00:15 | MNT-0362-030 at 2026-12-25 08:00 | 31.8h | 24 hours | **Missed** |
| **WELL-0161** | Northeast Block 8 | 2026-12-25 15:45 | INS-0161-0168 at 2027-01-14 11:00 | 475.2h | 24 hours | **Missed** |
| **WELL-0135** | Northeast Block 7 | 2026-12-27 03:50 | MNT-0135-034 at 2026-12-27 08:00 | 4.2h | 24 hours | **Met** |
| **WELL-0324** | Northwest Block 12 | 2027-01-01 22:40 | MNT-0324-036 at 2027-01-02 08:00 | 9.3h | 12 hours | **Met** |
| **WELL-0330** | Northwest Block 12 | 2027-01-02 21:40 | MNT-0330-030 at 2027-01-03 08:00 | 10.3h | 12 hours | **Met** |
| **WELL-0599** | Southeast Block 32 | 2027-01-06 17:20 | INS-0599-0196 at 2027-01-07 09:45 | 16.4h | 12 hours | **Missed** |
| **WELL-0516** | Southeast Block 32 | 2027-01-06 21:15 | INS-0516-0215 at 2027-01-07 12:15 | 15.0h | 12 hours | **Missed** |
| **WELL-0425** | Northwest Block 12 | 2027-01-07 05:20 | INS-0425-0218 at 2027-01-07 09:00 | 3.7h | 12 hours | **Met** |
| **WELL-0465** | Southeast Block 32 | 2027-01-08 23:35 | MNT-0465-031 at 2027-01-09 08:00 | 8.4h | 12 hours | **Met** |
| **WELL-0137** | Northeast Block 7 | 2027-01-10 23:30 | MNT-0137-032 at 2027-01-11 08:00 | 8.5h | 12 hours | **Met** |

### Q4. Temporary Flowline Bypasses (Chris Dalton, TEAM-HSE)
- **Prompt:** *"Across all areas, which temporary flowline bypasses are in place right now, and is each one allowed? Also list any bypass, past or present, that stayed in after its approval ran out or was never approved at all."*
- **Rule (OPS-2):** Allowed only under active MOC memo. MOC-044 extends MOC-031 to **28 Feb 2027**. MOC-036 expired **15 Dec 2026** (not extended). Unlisted wells are unapproved violations.

| Well | Area | Bypass In | Bypass Out | Approval (Memo ID) | Approval Valid Until | Status | Violation / Operational Finding |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **WELL-0248** | Southwest Block 23 | 2026-11-05 | still in | MOC-2026-044 (ext. 031) | 2027-02-28 | **Allowed** | In place right now under authorized extension. |
| **WELL-0249** | Southwest Block 23 | 2026-11-25 | still in | MOC-2026-036 | 2026-12-15 | **Expired** | In place right now; MOC-036 expired on 15 Dec 2026. |
| **WELL-0405** | Northwest Block 12 | 2026-12-20 | still in | none | none | **Not approved** | In place right now without any MOC approval. |
| **WELL-0087** | Southwest Block 24 | 2026-12-02 | 2027-01-06 | MOC-2026-036 | 2026-12-15 | **Expired** | Past bypass; stayed in 22 days past approval expiry. |
| **WELL-0158** | Northeast Block 8 | 2026-11-20 | 2026-12-28 | MOC-2026-036 | 2026-12-15 | **Expired** | Past bypass; stayed in 13 days past approval expiry. |
| **WELL-0561** | Southeast Block 32 | 2026-12-08 | 2026-12-19 | none | none | **Not approved** | Past bypass; installed and removed without any approval. |

### Q5. The Regulator's Letter on Spills (Michael Turner, TEAM-NE)
- **Prompt:** *"The State Oil & Gas Commission wrote to us in November 2026 about spills. Which of our spills does the letter cover, and on which ones are we not compliant? Show me a table."*
- **Criteria:** Reportable spills ($\ge 5.0$ bbl) in Northeast Block 7/8 since 1 Jun 2026. Compliant only if clean-up report contains the exact lab sentence: `"Soil samples sent to the lab."`

| Well | Area | Inspection (ID & Date) | Volume | Clean-up Job | Compliant? | Compliance Reason & Verification Proof |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **WELL-0119** | Northeast Block 7 | INS-0119-0209 (2026-11-05) | 6.0 bbl | MNT-0119-029 | **Yes** | Clean-up report contains exact text: *"Soil samples sent to the lab."* |
| **WELL-0123** | Northeast Block 7 | INS-0123-0093 (2026-09-24) | 6.0 bbl | MNT-0123-014 | **No** | Non-compliant: report has field screening (0.68% TPH) but lacks laboratory verification statement. |
| **WELL-0168** | Northeast Block 8 | INS-0168-0190 (2026-06-11) | 5.6 bbl | MNT-0168-024 | **Yes** | Clean-up report contains exact text: *"Soil samples sent to the lab."* |
| **WELL-0182** | Northeast Block 8 | INS-0182-0208 (2026-12-03) | 5.2 bbl | MNT-0182-028 | **No** | Non-compliant: report has field screening (0.74% TPH) but lacks laboratory verification statement. |
| **WELL-0262** | Northeast Block 8 | INS-0262-0218 (2027-01-07) | 6.1 bbl | MNT-0262-029 | **No** | Non-compliant: report has field screening (0.77% TPH) but lacks laboratory verification statement. |
| **WELL-0277** | Northeast Block 7 | INS-0277-0205 (2026-10-01) | 6.2 bbl | MNT-0277-031 | **Yes** | Clean-up report contains exact text: *"Soil samples sent to the lab."* |

### Q6. Which Status is Right? (Nathan Pierce, TEAM-NW)
- **Prompt:** *"Across the whole field, not just my area, for which wells do the latest inspection and the operator notes disagree about whether the well is producing oil? For each one, what is its real status right now, and why?"*
- **Rule (OPS-3):** Latest inspection vs latest operator shut-in/restart note. Later shut-in $\rightarrow$ **not producing (shut in)**. Later restart $\rightarrow$ **producing oil (unconfirmed)**.

| Well | Area | Latest Inspection (ID, Date & Telemetry) | Latest Operator Note (Date & Text) | Real Status Right Now | Governing Rationale (OPS-3) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **WELL-0033** | Southwest Block 23 | INS-0033-0222 (2027-01-14): Not producing ($\Delta T=10.0^\circ\text{C} < 20^\circ\text{C}$) | 2027-01-15 10:25: *"Restarted WELL-0033, unit running smooth."* | **Producing oil (unconfirmed)** | Note is more recent than inspection reading; well is producing pending confirming inspection. |
| **WELL-0044** | Southwest Block 23 | INS-0044-0218 (2027-01-14): Producing ($\Delta T=23.7^\circ\text{C} \ge 15^\circ\text{C}$) | 2027-01-14 13:05: *"Shut in WELL-0044 at wellhead, flowline leak suspected."* | **Not producing (shut in)** | Operator shut-in note is more recent than inspection; thermal reading is superseded. |
| **WELL-0323** | Northwest Block 12 | INS-0323-0219 (2027-01-14): Producing ($\Delta T=24.5^\circ\text{C} \ge 15^\circ\text{C}$) | 2027-01-14 19:20: *"Shut-in WELL-0323 after pumper reported stuffing box leak."* | **Not producing (shut in)** | Operator shut-in note is more recent than inspection. |
| **WELL-0422** | Northwest Block 12 | INS-0422-0215 (2027-01-14): Producing ($\Delta T=27.7^\circ\text{C} \ge 20^\circ\text{C}$) | 2027-01-14 21:35: *"Shut in WELL-0422 for night, high pressure alarm on separator."* | **Not producing (shut in)** | Operator shut-in note is more recent than inspection. |
| **WELL-0481** | Southeast Block 32 | INS-0481-0220 (2027-01-14): Producing ($\Delta T=22.4^\circ\text{C} \ge 15^\circ\text{C}$) | 2027-01-14 18:50: *"Shut in WELL-0481 for night, high pressure alarm on separator."* | **Not producing (shut in)** | Operator shut-in note is more recent than inspection. |

---

# Page 3: Benchmark Results & Outputs (Q7 to Q11)

### Q7. What the Operators Are Hearing (Robert Hayes, TEAM-MX)
- **Prompt (Turn 1):** *"Rank the 10 most likely to need a repair in the next 90 days, other than a spill clean-up, and quote the notes as evidence."*
- **Prompt (Turn 2):** *"Which three would you send a crew to first this week, and why?"*

| Rank | Well | Area | Operator Note Evidence (Date & Quote) | Other Warning Signs in Telemetry | Last Repair on Well |
| :---: | :--- | :--- | :--- | :--- | :--- |
| **1** | **WELL-0332** | NW-12 | 2026-12-31: *"Rod squeal at stuffing box"* & 2027-01-03: *"Pumper reports rattling at pump jack"* | Unresolved gas odor on 3 Dec (CTX-0332-004) flagged off with zero crew response; compound safety & mechanical risk. | MNT-0332-033 (2026-11-20, flowline) |
| **2** | **WELL-0197** | NE-08 | 2027-01-04: *"rattling"*, 01-08: *"fluid pound"*, 01-12: *"Heard fluid pound on WELL-0197, unit still running."* | 3 consecutive warnings in 8 days following parted rod repair (MNT-0197-029 closed 1 Jan 2027); imminent repeat failure (OPS-6). | MNT-0197-029 (2027-01-01, parted rod) |
| **3** | **WELL-0481** | SE-32 | 2027-01-06: *"Rod squeal"*, 01-08: *"rattling"*, 01-14: *"Shut in WELL-0481 for night, high pressure alarm on separator."* | Emergency operator shut-in on 14 Jan due to separator overpressure combined with worsening drive rattling. | MNT-0481-025 (2026-12-14, pump jack) |
| **4** | **WELL-0010** | SW-23 | 2027-01-10 & 01-13: *"Rod squeal"*, 01-14: *"Heard fluid pound on WELL-0010, unit still running."* | 3 notes in 4 days showing stuffing box friction and fluid pound; clean-up on 8 Jan did not inspect pump. | MNT-0010-031 (2027-01-08, spill clean-up)|
| **5** | **WELL-0020** | SW-23 | 2027-01-12: *"Rod squeal at stuffing box"*, 01-15: *"Heard fluid pound on WELL-0020, unit still running."* | Friction leading to fluid pound; valve serviced in Dec but downhole pump unaddressed. | MNT-0020-036 (2026-12-18, wellhead) |
| **6** | **WELL-0428** | NW-12 | 2027-01-01 & 01-06: *"Heard fluid pound on WELL-0428, unit still running."* | Carries recalled Highline RP-175 pump (LOT-2410-B); fluid pound indicates plunger cracking / barrel scoring. | MNT-0428-028 (2026-12-19, pump jack) |
| **7** | **WELL-0122** | NE-07 | 2026-12-26: *"Heard fluid pound"*, 2027-01-13: *"Rod squeal at stuffing box, greased polished rod."* | Thermal delta depressed (16.2°C vs 15°C); packing degradation and fluid pound indicate gas interference. | MNT-0122-031 (2026-12-01, wellhead) |
| **8** | **WELL-0392** | NW-12 | 2026-12-19: *"rattling at pump jack"*, 12-24: *"Heard fluid pound on WELL-0392, unit still running."* | Gearbox vibration coupled with fluid pound; 52 days since last maintenance. | MNT-0392-016 (2026-11-27, wellhead) |
| **9** | **WELL-0136** | NE-07 | 2027-01-11: *"Heard fluid pound on WELL-0136, unit still running."* | Fluid pound on deep T350 well; higher cyclic stress on 8,500 ft rod string. | MNT-0136-033 (2026-12-06, pump jack) |
| **10** | **WELL-0305** | NW-12 | 2027-01-11: *"Pumper reports rattling at WELL-0305 pump jack, keep an eye on it."* | Recalled Highline RP-175 pump (LOT-2409-A) past 31 Dec deadline; drive rattling indicates binding. | MNT-0305-033 (2026-12-13, pump jack) |

- **Top 3 Dispatch Recommendation:**
  1. **WELL-0332:** Imminent toxic/safety hazard. Unresolved gas odor from 3 Dec with pad flagged off but no crew dispatch (OPS-1 violation). Now exhibiting rod squeal and rattling. Dispatch crew for gas sniff test (WS-03/04) and mechanical inspection.
  2. **WELL-0197:** Imminent repeat failure risk. Parted sucker rod on 1 Jan followed by rattling and repeated fluid pound notes (4, 8, 12 Jan). Dispatch immediately to prevent repeat parted rod and workover rig expenses (OPS-6).
  3. **WELL-0481:** Active operational shut-in. Shut in on 14 Jan due to separator high pressure alarm with preceding mechanical rattling. Dispatch crew to bleed separator and inspect safety relief valves.

### Q8. Multi-Session User Memory & Provenance (Nathan Pierce, Robert Hayes, Olivia Grant)
- **Turn 1 (Nathan Pierce):** Reports WELL-0333 recalled pump swapped yesterday. Recorded in ledger as an operational override with provenance: *"Verbal report from Nathan Pierce (U-601, NW Production Supervisor) on 15 Jan 2027; pending work order entry."*
- **Turn 2 (Nathan Pierce):** Preferences set: Sort by Area $\rightarrow$ Well ID; costs in thousands ($k). Scoped strictly to `user_id = 'U-601'`.
- **Turn 3 (Robert Hayes):** Robert queries active recalled pumps. Nathan's personal display preferences do NOT leak to Robert. Result: **8 recalled pumps** remain in ground (WELL-0333 excluded per Nathan's report). Costs shown in full dollars per Robert's default profile.
- **Turn 4 (Olivia Grant):** Olivia (SE Supervisor) reports Nathan told her WELL-0577 was swapped. Recorded with provenance and flagged as hearsay: *"Provisional replacement reported by Olivia Grant citing Nathan Pierce; pending work order verification."*
- **Turn 5 (Nathan Pierce):** Query for Northwest recalled pumps. Nathan's scoped preferences activate: sorted by Area/Well ID, costs in $k$, WELL-0333 excluded.
  * **WELL-0305:** Highline RP-175 (LOT-2409-A), installed MNT-0305-032 on 2026-10-16 $\rightarrow$ **$24.5k** ($24,528.00). Provenance: `MNT-0305-032`.
  * **WELL-0426:** Highline RP-175 (LOT-2409-C), installed MNT-0426-030 on 2026-06-19 $\rightarrow$ **$24.0k** ($24,044.00). Provenance: `MNT-0426-030`.
  * **WELL-0428:** Highline RP-175 (LOT-2410-B), installed MNT-0428-022 on 2026-03-07 $\rightarrow$ **$27.1k** ($27,074.00). Provenance: `MNT-0428-022`.

### Q9. One Conversation, Several Topics (Robert Hayes, TEAM-MX)
1. **Recalled Pumps:** 8 in ground across 4 areas (Northwest: 3, Northeast: 2, Southwest: 2, Southeast: 1).
2. **Northwest Production Lead:** Led by Nathan Pierce (U-601); team runs **150 wells** (all in Northwest Block 12).
3. **Cold Weather SOP (OPS-5):** Productor ambient $\le -5.0^\circ\text{C}$ between 1 Dec and 28 Feb requires heat trace check within 7 days. **WELL-0310** (NW Block 12, inspected 17 Dec, ambient −6.0°C) missed its required check.
4. **WELL-0332 H2S Reading:** **No H2S reading was taken or recorded.** Note CTX-0332-004 logged a gas odor with area flagged off; no field response occurred (OPS-1 violation).
5. **Non-Producing Recalled Pumps:** Exactly two: **WELL-0160** (NE Block 8, $\Delta T=3.8^\circ\text{C}$, repair MNT-0160-032 on pump jack in progress) and **WELL-0263** (SW Block 23, $\Delta T=4.0^\circ\text{C}$, repair MNT-0263-035 on flowline in progress).
6. **Highest Priority Well:** **WELL-0332**, due to unresolved gas odor/toxic safety exposure combined with stuffing box squeal and pump jack rattling.

### Q10. Shut-in Delay Breakdown by Area in 2026 (Michael Turner, TEAM-NE)
- **Prompt:** *"When a well stays shut in longer than the repair itself, what are we usually waiting on: parts, crews, contractors or weather? Break it down by area for jobs started in 2026, with typical extra days, and tell me if any area stands out."*
- **Key Discovery:** Delays in 2026 were driven exclusively by **Weather (66.7%, 26 jobs)** and **Parts (33.3%, 13 jobs)**; crews and contractors account for **0%** of delays in the operational record.

| Area | Delayed Jobs | Parts Delay Share (Jobs) | Parts Typical Extra Days | Weather Delay Share (Jobs) | Weather Typical Extra Days |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Southeast Block 32** | **12** | **50.0% (6 jobs)** | **35 days** *(Outlier)* | 50.0% (6 jobs) | 21 days |
| **Northwest Block 12** | **8** | 0.0% (0 jobs) | - | **100.0% (8 jobs)** | 21 days |
| **Southeast Block 31** | **7** | 28.6% (2 jobs) | 14 days | 71.4% (5 jobs) | 21 days |
| **Northeast Block 7** | **4** | 0.0% (0 jobs) | - | 100.0% (4 jobs) | 21 days |
| **Southwest Block 23** | **4** | 50.0% (2 jobs) | 18 days | 50.0% (2 jobs) | 28 days |
| **Southwest Block 24** | **2** | 100.0% (2 jobs) | 14 days | 0.0% (0 jobs) | - |
| **Northeast Block 8** | **2** | 50.0% (1 job) | 14 days | 50.0% (1 job) | 21 days |

- **Standing Out:** **Southeast Block 32 stands out dramatically**, incurring 46.2% of all parts delay incidents field-wide and a median extra shut-in duration of **35 days** (more than double the 14-day field average). Northwest Block 12 stands out for weather sensitivity (8 jobs).
- **Stacked Bar Chart Specification:** Rendered via `StackedBarChartWidget` with categories `Parts Delay` (#f59e0b) and `Weather Delay` (#3b82f6) grouped by Area.

```
Southeast Block 32  [████████████ Parts: 6 (35d) ][████████████ Weather: 6 (21d) ]
Northwest Block 12  [                                ][████████████████ Weather: 8 (21d) ]
Southeast Block 31  [████ Parts: 2 (14d)         ][██████████ Weather: 5 (21d)   ]
Northeast Block 7   [                                ][████████ Weather: 4 (21d)     ]
Southwest Block 23  [████ Parts: 2 (18d)         ][████ Weather: 2 (28d)         ]
Southwest Block 24  [████ Parts: 2 (14d)         ]
Northeast Block 8   [██ Parts: 1 (14d)           ][██ Weather: 1 (21d)           ]
```

### Q11. Hotter Wells (Olivia Grant, TEAM-SE)
- **Prompt:** *"Which region of the field consistently runs hotter?"*
- **Statistical Evidence (125,198 Inspections):** The **Southeast region** consistently runs hottest across the entire field.
  * **Southeast:** Mean Wellhead = **51.24°C** | Median = **51.10°C** | Mean $\Delta T$ = **29.70°C** | Median $\Delta T$ = **30.90°C**
  * **Northwest:** Mean Wellhead = 50.06°C | Median = 50.00°C | Mean $\Delta T$ = 28.57°C | Median $\Delta T$ = 29.50°C
  * **Northeast:** Mean Wellhead = 48.54°C | Median = 48.40°C | Mean $\Delta T$ = 27.03°C | Median $\Delta T$ = 27.80°C
  * **Southwest:** Mean Wellhead = 48.17°C | Median = 48.10°C | Mean $\Delta T$ = 26.69°C | Median $\Delta T$ = 27.60°C
- **Lease-Level Outlier:** Within the Southeast, **Southeast Block 31** is the single hottest area in the field, averaging a wellhead temperature of **52.85°C** and mean $\Delta T$ of **31.36°C** (median **35.60°C**).
