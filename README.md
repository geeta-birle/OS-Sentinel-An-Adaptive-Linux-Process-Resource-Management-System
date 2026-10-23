# OS Sentinel: Adaptive Linux Process & Resource Management System

**Phase 10: Final Validation, System Documentation & Academic Demonstration**

OS Sentinel is an explainable, adaptive operating systems platform designed to monitor, inspect, and analyze system resource pressure and process hierarchies with strict safety and read-only guarantees.

---

## 1. Executive Summary & Operating System Concepts Demonstrated

OS Sentinel demonstrates core Operating System principles in a concrete, production-grade architecture:

1. **Process Management & Inspection (`/proc` & OS Subsystems)**
   - Read-only process tree enumeration via batched kernel attribute queries (`psutil.process_iter`).
   - Graceful kernel exception handling (`NoSuchProcess`, `AccessDenied`, `ZombieProcess`).
   - Command-line argument sanitization to protect runtime credentials (`--password`, `--token`, `--api-key`).
   - Thread-safe in-memory caching with Time-To-Live (TTL = 2.0s) yielding a ~1,500x speedup on repeated scans.

2. **Memory Subsystems & Paging Dynamics**
   - Distinction between Virtual Memory (`vms`), Resident Set Size (`rss`), and Page Cache / Buffers.
   - Swap space utilization analysis and thrashing pressure awareness.
   - Explicit uncertainty boundaries: high memory usage is never flagged as failure without verifying swap paging activity and buffer availability.

3. **CPU Scheduling, Load Averages & Run-Queue Dynamics**
   - Multi-core CPU utilization sampling with baseline calibration.
   - Run-queue pressure tracking via exponentially decaying load averages (1m, 5m, 15m) on Linux / WSL2.
   - Distinction between CPU-bound saturation and I/O wait contention.

4. **Concurrency, Background Collection & Persistence Durability**
   - Singleton background collector daemon operating autonomously on a fixed schedule ($T = 5\text{s}$).
   - Multi-threaded persistence into SQLite utilizing Write-Ahead Logging (`PRAGMA journal_mode=WAL;`), normal synchronization (`PRAGMA synchronous=NORMAL;`), and busy timeout protection (`PRAGMA busy_timeout = 5000;`).
   - Proven restart durability across independent operating system process lifetimes.

5. **Explainable Adaptive Detection & Recommendation Engine**
   - Multi-sample persistence windows suppressing isolated spikes.
   - Symmetric recovery thresholds preventing alert flapping.
   - Dynamic threshold reconfiguration with runtime validation ($0 \le \text{recovery} < \text{warning} < \text{critical} \le 100$).
   - Non-destructive triage recommendations mapped directly from observable evidence.

---

## 2. Architecture Overview

```
                      +-------------------------------------------------------+
                      |               React 19 + TypeScript + Vite            |
                      |                 Operations Dashboard                  |
                      |               (http://localhost:5173)                 |
                      |                                                       |
                      |  [Overview]  [Process Explorer]  [Alerts & Analysis]  |
                      |  [Recommendations]   [History & Audit]   [Settings]   |
                      |  • Polling Loop Guard (No Overlapping Requests)       |
                      |  • Zero-Dependency Pure SVG History Time-Series Chart |
                      |  • Read-Only Inspection Modal & Bounded Pagination    |
                      +---------------------------+---------------------------+
                                                  |
                                                  | REST API / JSON (CORS-Filtered)
                                                  v
                      +-------------------------------------------------------+
                      |               Production WSGI Application             |
                      |                 (backend/wsgi.py)                     |
                      |          Waitress (Win/Linux) / Gunicorn (WSL2)       |
                      |               (http://127.0.0.1:5000)                 |
                      +-------------+-----------------------------+-----------+
                                    |                             |
                     +--------------+                             +---------------+
                     |                                                            |
                     v                                                            v
        +---------------------------+                                +---------------------------+
        |     MetricsCollector      |                                |      ProcessService       |
        | - CPU (primed baseline)   |                                | - Read-only inspection    |
        | - Virtual & Swap Memory   |                                | - NoSuchProcess tolerance |
        | - /proc/uptime & load avg |                                | - AccessDenied fallback   |
        | - WSL2 / Host detection   |                                | - In-memory cache (2.0s)  |
        |                           |                                | - Command-line redaction  |
        +-------------+-------------+                                +---------------------------+
                      |
                      v
        +---------------------------+
        | BackgroundMetricsCollector|
        | - Singleton daemon thread |
        | - Reloader duplicate guard|
        +-------------+-------------+
                      |
                      +-----------------------------------+
                      |                                   |
                      v                                   v
        +---------------------------+       +---------------------------+
        |     DetectionService      |       |      SQLite Database      |
        | - Configurable thresholds |       | - WAL journal mode        |
        | - Spike suppression       |       | - 5000ms busy timeout     |
        | - Dynamic settings reload |       | - system_metrics table    |
        | - Recovery tracking       |       | - alerts & settings table |
        | - Cooldown enforcement    |       +---------------------------+
        +-------------+-------------+
                      |
                      v
        +---------------------------+
        |   RecommendationService   |
        | - Non-destructive triage  |
        | - Shell diagnostic guides |
        | - Uncertainty boundaries  |
        +---------------------------+
```

---

## 3. Operations Dashboard & Capabilities

1. **Overview Page**
   - Telemetry cards displaying real-time CPU %, Memory (used/total/free), Swap utilization, and Run-Queue Load Averages (1m, 5m, 15m).
   - Zero-dependency SVG time-series chart with interactive tooltip cursor and dynamic scaling.
   - Platform identification tags distinguishing native Linux, WSL2 virtual machine guest, and Windows host.
   - Active alert banner providing immediate visual feedback during resource pressure.

2. **Process Explorer**
   - Searchable, sortable process table with bounded pagination (10, 25, 50 rows).
   - Columns: PID, Process Name, Status, CPU %, Memory %, Resident Set Size (RSS), and User.
   - Granular Read-Only Inspection Modal displaying command line arguments, memory mappings (RSS/VMS), thread count, PPID, and nice priority.
   - Security banner affirming zero process-kill or modification capabilities.

3. **Alerts & Analysis**
   - Severity filters (`warning`, `critical`) and status filters (`all`, `active`, `recovered`).
   - Diagnostic evidence chips showing exact breach measurements, persistence window, and threshold.
   - Natural-language explanations detailing why each alert was opened, escalated, or recovered.

4. **Investigative Recommendations**
   - Evidence-correlated triage recommendations mapped from active alerts.
   - Step-by-step diagnostic shell commands (e.g., `top -b -n 1 -o %CPU`, `vmstat 1 5`).
   - Clear distinction between abnormal thrashing and standard OS memory caching.

5. **History & Audit Log**
   - Dual-tab view: System Metric Time-Series timeline and Historical Alert Audit Log.
   - Directly persisted from SQLite (`sentinel.db`).
   - Configurable query limits (25, 50, 100 rows).

6. **Settings & Engine Tuning**
   - Interactive configuration form for CPU, Memory, Swap, and Load thresholds.
   - Client and server validation ensuring $0 \le \text{recovery} < \text{warning} < \text{critical} \le 100$, persistence between 1–30 samples, and cooldown between 5–86,400s.
   - Runtime application of new thresholds without service restart.

---

## 4. API Endpoints Reference

| Method | Endpoint | Query Parameters / Body | Description | Status Codes |
|---|---|---|---|---|
| `GET` | `/healthz` | None | Top-level liveness probe | `200` |
| `GET` | `/api/v1/health` | None | Service health status and version (`0.4.0`) | `200` |
| `GET` | `/api/v1/health/readiness` | None | Readiness probe (`api`, `system_inspector`, `database`) | `200` |
| `GET` | `/api/v1/system/summary` | None | Host metadata and live system measurements | `200` |
| `GET` | `/api/v1/system/history` | `limit` (1..500, default 50)<br>`since` (ISO-8601 string) | Time-series historical measurements from SQLite | `200`, `400`, `500` |
| `GET` | `/api/v1/processes` | `limit` (1..500, default 50)<br>`sort_by` (`cpu_percent`, `memory_percent`, `memory_rss`, `pid`, `name`, `status`)<br>`order` (`desc`, `asc`) | Safe, bounded list of system processes (cached 2.0s) | `200`, `400`, `500` |
| `GET` | `/api/v1/processes/<pid>` | None | Granular read-only details for a specific PID (sanitized) | `200`, `400`, `403`, `404`, `500` |
| `GET` | `/api/v1/alerts` | `status` (`active`, `recovered`, `all`, default `all`)<br>`severity` (`warning`, `critical`)<br>`limit` (1..500, default 50) | Returns persisted resource pressure alerts | `200`, `400`, `500` |
| `GET` | `/api/v1/recommendations` | None | Explainable, non-destructive investigative guidance | `200`, `500` |
| `GET` | `/api/v1/settings` | None | Retrieves current detection thresholds and windows | `200`, `500` |
| `PUT` | `/api/v1/settings` | JSON body with updated thresholds | Updates detection thresholds dynamically with validation | `200`, `400`, `500` |

---

## 5. Security & Safety Boundaries

- **Strictly Read-Only Operation**: The platform contains no code paths for process termination (`SIGKILL`, `SIGTERM`), suspension (`SIGSTOP`), resumption (`SIGCONT`), or priority manipulation (`nice`, `renice`).
- **No Command Execution from Telemetry**: The application never automatically invokes external shell commands or scripts based on metric thresholds.
- **Credential Masking**: Command-line arguments containing sensitive flags (`--password`, `-p`, `--token`, `--api-key`, `--secret`) or assignments (`--token=value`, `--api-key=value`) are redacted to `***` before API serialization.
- **Strict CORS Origin Filtering**: Cross-Origin requests from unapproved domains are rejected with `Access-Control-Allow-Origin: None`. Only approved frontends (`http://localhost:5173`, `http://127.0.0.1:5173`) receive permission headers.
- **Safe Production Defaults**: Default configuration enforces `FLASK_ENV=production`, `DEBUG=False`, and loopback binding `HOST=127.0.0.1`.
- **Systemd Sandboxing**: Service template enforces `NoNewPrivileges=true` and `ProtectHome=read-only`.

---

## 6. Verification & Test Evidence

All tests executed on the real repository environment:

| Test Suite | Scope | Command | Result |
|---|---|---|---|
| **Backend Unit & Integration** | 68 Tests: Database WAL, Process Cache, Redaction, Detection Lifecycle, Dynamic Settings, API Schema | `python -m unittest discover -s backend/tests -t backend -p "test_*.py"` | **68 passed in 33.34s** (Exit 0) |
| **Subprocess Restart Durability** | Genuine OS subprocess restart and alert state persistence | `python -m unittest discover -s backend/tests -t backend -p "test_process_restart_persistence.py"` | **1 passed in 1.61s** (Exit 0) |
| **Frontend Component Suite** | 13 Tests: API client, App mounting, Dashboard views, SVGs | `npm --prefix frontend test -- --run` | **13 passed in 2.61s** (Exit 0) |
| **Frontend Code Quality** | Static AST analysis across 20 TypeScript/React files | `npm --prefix frontend run lint` | **0 errors** (Exit 0) |
| **Frontend Production Build** | TypeScript compilation & Vite bundle creation | `npm --prefix frontend run build` | **Built in 244ms** (Exit 0) |
| **Live WSGI API Smoke Tests** | 9 live HTTP endpoints, CORS filtering, Cold vs Cached latency | Python urllib live request script against `http://127.0.0.1:5000` | **9/9 passed, 200 OK** (Cold: 6.1s, Cached: 3.9ms) |

---

## 7. Setup & Execution Instructions

### A. Windows Host Execution (Current Verification Environment)

```powershell
# 1. Start Production WSGI Backend
cd "d:\sem 3\OSY\Project"
python backend/wsgi.py
# Backend runs on http://127.0.0.1:5000 (Debug: False)

# 2. In a second terminal, start Frontend Development Server
cd "d:\sem 3\OSY\Project\frontend"
npm run dev
# Frontend runs on http://localhost:5173
```

### B. Ubuntu WSL2 Linux Environment

```bash
# 1. Open Ubuntu WSL2 terminal
wsl -d Ubuntu
cd "/mnt/d/sem 3/OSY/Project"

# 2. Set up virtual environment and install dependencies (one-time)
sudo apt update && sudo apt install -y python3-venv python3-pip
python3 -m venv backend/.venv
source backend/.venv/bin/activate
pip install -r backend/requirements.txt
pip install gunicorn

# 3. Run production WSGI via Gunicorn
cd backend
gunicorn --workers 1 --threads 4 --bind 127.0.0.1:5000 wsgi:app

# 4. In another terminal, start frontend
cd ../frontend
npm run dev
```

---

