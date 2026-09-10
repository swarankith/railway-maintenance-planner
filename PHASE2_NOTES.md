# RailBlock AI — Phase 2 Architecture & Upgrade Notes (v6 Final)

## 1. Summary of Changes
- **Complete Auth Removal**: Stripped JWT auth, passwords, and user logins. All API endpoints are open and accessible. Approval sign-offs capture role and name directly from UI/API request payload.
- **Deterministic Scheduling Engine (Steps 0–7)**:
  - **Step 0**: Batch assembly preserving `retry_count`, duplicate detection via `token_sort_ratio >= 90`, and `ProcessingCycle` record creation.
  - **Step 1**: Emergency lane (`block_type == 'Emergency'`), isolated with `[isolated_at - 15m, latest_end + 15m]` safety buffer; competing emergency detection.
  - **Step 2**: Category A/B classification with RapidFuzz (`score >= 85`). Category B fast path (non-intrusive, no disconnection, no shared resource conflict).
  - **Step 3**: Connected component spatial-temporal grouping (`corridor` + 15-min buffered time + min 0.1 KM overlap).
  - **Step 4**: Rule C clash detection (exact match on normalized `work_type` and `asset`).
  - **Step 5**: Strict capped bundling (sizes 1–3, all pairs compatible, quality score formula).
  - **Step 6**: Priority walk ordering `score = (4 - priority) * 100 + max(0, 7 - days_to_due) * 10`; greedy 15-minute best-fit allocation.
  - **Step 7**: Retry thresholding (`retry_count < 3` -> Deferred; `>= 3` -> Manual Review).
- **Processing Cycle Status Model**: `ProcessingCycle` transitions: `Active` -> `Approved` | `Rejected` | `Archived`.
- **In-Memory Demo Runner**: `POST /api/v1/demo/run` executes pipeline without database writes, returning `X-Demo-Mode: true`.
- **Part F Approval Report**: Two-section signed PDF report generated with ReportLab (`GET /api/v1/schedules/{id}/approval-report`).
- **Bulk Delete with Active Cycle Guard**: `POST /api/v1/requests/bulk-delete` deletes requests safely, skipping those in `Active` cycles.
- **Frontend Rebuild**: Gantt chart with 0.5x/1x/2x zoom, sticky 160px corridor column, 28px maintenance lane, 16px hatched train lane, and deferred/manual review sections.

---

## 2. Train Schedule Document Format
Trains can be uploaded via PDF tables or CSV format. Expected fields:

| Field | Type | Description | Sample Value |
|---|---|---|---|
| `train_number` | String | Railway train service number | `12004` |
| `train_name` | String | Commercial train name | `Lucknow Swarna Shatabdi` |
| `corridor` | String | Railway line / section | `NDLS-GZB` |
| `departure_time` | ISO / Time | Station departure time (IST) | `2026-09-11 06:10:00` |
| `arrival_time` | ISO / Time | Section clearing time (IST) | `2026-09-11 07:05:00` |
| `km_start` | Float | Route starting kilometer | `0.0` |
| `km_end` | Float | Route ending kilometer | `25.4` |
| `speed_kmh` | Float | Maximum permissible section speed | `110.0` |
| `train_type` | String | Train priority classification | `High-Speed Passenger` |

---

## 3. Database & Supabase Pooler Configuration
- Supports both SQLite (`sqlite:///./railway_planner.db`) and PostgreSQL.
- When deploying to Supabase / Render:
  - Use Transaction Pooler (port `6543`) or Session Pooler (port `5432`).
  - `config.py` automatically strips `pgbouncer=true` parameters incompatible with SQLAlchemy.
  - Automatically appends `sslmode=require` for PostgreSQL URLs.
  - Safe, idempotent schema migrations run on startup via `init_db()`.

---

## 4. Scoring Formulas
1. **Bundle Quality Score (Step 5)**:
   $$\text{Quality} = \left(\frac{\text{Time Saved}}{\text{Total Isolated Window}}\right) \times 0.4 + \left(\frac{\text{Unique Departments}}{3}\right) \times 0.3 + \left(\frac{\text{Resources Bundled}}{\text{Max Resources}}\right) \times 0.3$$
2. **Priority Walk Sorting Score (Step 6)**:
   $$\text{Walk Score} = (4 - \text{priority}) \times 100 + \max(0, 7 - \text{days to due}) \times 10$$

---

## 5. Eligibility & Cycle Lifecycle
- **Eligible Requests**: `status IN ('Confirmed', 'Needs-Review', 'Deferred', 'Manual Review') AND cycle_id IS NULL`.
- **Eligible Trains**: `cycle_id IS NULL`.
- **Cycle Resolution**:
  - **On Approval**: Cycle status becomes `Approved`. Bundled requests transition to `Approved` and remain assigned to `cycle_id`. Deferred/Manual Review requests have `cycle_id` reset to `NULL` to re-enter future batches. Trains have `cycle_id` sealed.
  - **On Rejection**: Cycle status becomes `Rejected`. Requests revert to `Confirmed` with `cycle_id` cleared to re-enter next optimization cycle.

---

## 6. Demo Simulation Mode
- `POST /api/v1/demo/run` loads standardized Indian Railways fixtures in-memory.
- Entire pipeline runs without calling `db.commit()` or modifying persistent database state.
- UI indicates active simulation with banner: *"Demo Mode Active — Data in-memory only, will not be saved to database"*.
