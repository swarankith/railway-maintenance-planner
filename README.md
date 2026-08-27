# AI-Assisted Railway Maintenance Block Planner (Decision-Support Prototype)

An intelligent full-stack decision-support application for Indian Railways and modern multimodal rail networks. The system ingests multi-department maintenance work proposals (Civil/Engineering, Electrical/TRD, Signal & Telecom), automatically calculates genuine spatial-temporal-resource conflicts, bundles compatible operations into consolidated maintenance blocks via Google OR-Tools CP-SAT, and presents an explainable interactive Gantt schedule for human controller approval.

---

## Key Features

1. **Zero Hardcoded Data & Clean Start**:
   - The database initializes completely blank. All corridor records, job proposals, and train movements are ingested dynamically from runtime user-uploaded PDF/DOCX documents.
2. **Multi-Format Ingestion Layer**:
   - Supports structured tables, semi-structured forms, circulars, and prose memos across `.pdf` and `.docx`.
   - Incomplete or ambiguous records are flagged with `status: "Needs-Review"` with an interactive inline editor.
3. **Multi-Dimensional Conflict Detection Engine**:
   - Evaluates spatial overlap (`max(r1.km_start, r2.km_start) < min(r1.km_end, r2.km_end)`), time window overlap (`max(start1, start2) < min(end1, end2)`), and identical corridor.
   - Strictly suppresses false positives across different corridors, different dates, and non-overlapping KM spans.
   - Detects specialized resource double-booking, live train movement collisions, and department incompatibilities.
4. **OR-Tools CP-SAT Optimization & Explainable Bundling**:
   - Solves multi-objective constraint satisfaction: maximizes high-priority jobs scheduled, minimizes track closure downtime, eliminates train interference, and maximizes joint department bundling.
   - Generates **Plan A (Maximum Bundling)** and **Plan B (Rapid Turnaround)**.
   - Produces domain-specific, plain-language reasoning for every maintenance block.
5. **Interactive Corridor Gantt Chart & Approval Hub**:
   - Visual timeline displaying corridors on Y-axis and IST hours on X-axis.
   - Color-coded department badges and bundled joint blocks.
   - Human-in-the-loop decision controls with role selector, comments, and persistent audit trail.

---

## Tech Stack

| Component | Technology |
|---|---|
| **Backend API** | Python 3.11, FastAPI, Pydantic V2, SQLAlchemy |
| **Optimization Engine** | Google OR-Tools CP-SAT |
| **File Parsing** | `pdfplumber`, `pypdf`, `python-docx` |
| **Frontend UI** | React 18, TypeScript, Tailwind CSS, Lucide Icons, Vite |
| **Database** | SQLite (`railway_planner.db`) |
| **Timezone** | Indian Standard Time (`IST`, `UTC+5:30`) |

---

## Quickstart Guide

### 1. Start the Backend API
```powershell
# In railway-maintenance-planner/
.\.venv\Scripts\uvicorn.exe backend.main:app --host 127.0.0.1 --port 8000 --reload
```
- API Docs: `http://127.0.0.1:8000/docs`
- Health Check: `http://127.0.0.1:8000/api/v1/health`

### 2. Start the Frontend Dashboard
```powershell
# In railway-maintenance-planner/frontend/
npm run dev
```
- Frontend URL: `http://127.0.0.1:3000`

### 3. Run Automated Tests
```powershell
python -m pytest backend/tests -v
```

---

## Deployment Options

### Option A: Docker / Container Deployment (Single-Command)

Build and start the complete application (Frontend + Backend + SQLite database) in a single container:
```bash
# Using Docker
docker build -t railway-maintenance-planner .
docker run -p 8000:8000 -e PORT=8000 railway-maintenance-planner

# Or using Docker Compose
docker-compose up --build
```
Access the application at `http://localhost:8000`.

### Option B: Cloud Platform Deployment (Render, Railway, Fly.io, Heroku)

1. **Environment Variables**:
   - `PORT`: Automatically set by platform (defaults to `8000`)
   - `DATABASE_URL`: Set to your database URI (e.g. SQLite `sqlite:///./railway_planner.db` or PostgreSQL `postgresql://user:pass@host:5432/db`)
2. **Build Command**:
   ```bash
   cd frontend && npm install && npm run build && cd .. && pip install -r requirements.txt
   ```
3. **Start Command**:
   ```bash
   python -m uvicorn backend.main:app --host 0.0.0.0 --port $PORT
   ```

### Option C: Decoupled Frontend (Vercel / Netlify) + Backend (Render / Cloud Run)

- **Frontend**: Set build root to `frontend`, run command `npm run build`, output directory `dist`. Configure environment variable `VITE_API_URL=https://your-backend-domain.com`.
- **Backend**: Deploy using Python 3.11+ / Docker with `requirements.txt`.

---

## Sample Documents for Runtime Testing

Realistic sample test documents are located in `sample_documents/`:
- `sample_documents/Northern_Railway_Maintenance_Circular.docx` (Multi-department table + train movement guidelines)
- `sample_documents/Western_Railway_Block_Requisition.pdf` (Table + incomplete review notes)

To regenerate sample files:
```powershell
python scripts/generate_sample_documents.py
```