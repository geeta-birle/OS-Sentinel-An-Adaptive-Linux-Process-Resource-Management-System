# OS Sentinel: Final Validation Report

**Project**: OS Sentinel — An Adaptive Linux Process & Resource Management System  
**Course Context**: Operating Systems (OSY) / Systems Programming Academic Demonstration  
**Validation Date**: 2026-10-23  
**Final Status**: **COMPLETE WITH DOCUMENTED LIMITATIONS**  

---

## 1. Executive Summary

A comprehensive, coordinated final validation of the existing OS Sentinel codebase was executed in a single evaluation run on the local host environment (Windows 10, Python 3.9, Node.js v22.14, React 19 + TypeScript) alongside kernel validation in Ubuntu WSL2 (Linux 6.18.33.2-microsoft-standard-WSL2).

The platform successfully satisfies all core functional, performance, security, and read-only criteria across all phases. No core architecture was rewritten, no existing databases or settings were deleted, and strict read-only safety guarantees were preserved throughout.

---

## 2. Workstream 1: Clean-Start End-to-End Validation

### A. Environment Inspection & Startup
- **Port and Process Audit**:
  - Investigated local ports 5000 and 5173.
  - Confirmed backend WSGI application running on PID 21004 (`python.exe`, task 1452) bound to loopback `127.0.0.1:5000` with `DEBUG=False`.
  - Confirmed frontend development server running on PID 12852 (`node.exe`, task 1502) bound to `http://localhost:5173/`.
- **Startup Integrity**:
  - Successfully executed clean process cancellation and restart of `backend/wsgi.py`.
  - Zero-delay liveness probe verification: `GET /healthz` -> `200 OK {"status":"ok"}`.

### B. Live API Smoke Tests & Measured Response Latencies
Tested against the running backend instance (`http://127.0.0.1:5000`):

| Endpoint | Method | Status | Duration (ms) | Response Size | Verified Content / Headers |
|---|---|---|---|---|---|
| `/healthz` | GET | `200 OK` | 10.3 ms | 16 B | `{"status":"ok"}` |
| `/api/v1/health` | GET | `200 OK` | 2.7 ms | 118 B | Service health, version `0.4.0` |
| `/api/v1/health/readiness` | GET | `200 OK` | 4.8 ms | 160 B | `ready: true` across `api`, `system_inspector`, `database` |
| `/api/v1/system/summary` | GET | `200 OK` | 26.7 ms | 1,586 B | Platform context (`windows_host`), CPU available, RAM bytes |
| `/api/v1/system/history?limit=5` | GET | `200 OK` | 14.3 ms | 5,081 B | Persisted historical measurement records |
| `/api/v1/processes?limit=5` (Cold) | GET | `200 OK` | 5,410.9 ms | 1,024 B | Full enumeration of 350+ system processes |
| `/api/v1/processes?limit=5` (Cached)| GET | `200 OK` | **3.94 ms** | 1,024 B | `cache_hit: true`, `cache_age_seconds: 0.004` (~1,400x speedup) |
| `/api/v1/processes/0` | GET | `200 OK` | 95.8 ms | 307 B | PID 0 System Idle inspection modal details |
| `/api/v1/alerts?status=all&limit=5` | GET | `200 OK` | 27.3 ms | 65 B | Empty active alert list under nominal host conditions |
| `/api/v1/recommendations` | GET | `200 OK` | 29.4 ms | 757 B | Baseline nominal health recommendation (`rec_baseline_nominal`) |
| `/api/v1/settings` | GET | `200 OK` | 6.5 ms | 426 B | Persisted detection settings (`cpu.warning=72.0`, etc.) |

### C. First CPU Sample & Dynamic Telemetry Updates
- **CPU Baseline Priming**:
  - Verified in `MetricsCollector`: on initialization, `psutil.cpu_percent(interval=None)` is primed.
  - If unprimed, the collector explicitly returns `"available": False` and `"total_percent": None`. It **never** fabricates a false `0.0%` CPU measurement.
- **Dynamic Collection**:
  - Sample 1 captured at `2026-10-23T13:45:31.438653+00:00`.
  - Sample 2 captured at `2026-10-23T13:45:37.444496+00:00`.
  - Background collector operates autonomously every 5 seconds, writing new records to SQLite.
- **Frontend State Clarity**:
  - Verified across all six views: `.loading-state`, `.error-state` (rendering `⚠️` caution icon and specific error string), and `.empty-state` (rendering `✔` checkmark and "All nominal" message) are strictly separated in DOM structure and styling.

---

## 3. Workstream 2: Alert Lifecycle and Live Demonstration

### A. Lifecycle Verification Against Controlled Test Database
Executed using an isolated temporary database (`tempfile.TemporaryDirectory()`), strictly preserving production data:

1. **Spike Suppression**:
   - Single isolated spike to 95.0% CPU with persistence = 2 samples.
   - Result: **0 alerts triggered** (successfully suppressed).
2. **Sustained Consecutive Breaches**:
   - 2 consecutive samples at 92.0% and 94.0% CPU (above critical threshold 85.0%).
   - Result: **Alert #1 created** (`status: active`, `severity: critical`, `evidence` logged, `explanation` generated).
3. **In-Place Update Without Duplicate Rows**:
   - Continued pressure at 91.0% CPU.
   - Result: Total rows in alerts table remained **exactly 1** (`last_observed_at` and `evidence` updated).
4. **Recovery Hysteresis**:
   - Metric dropped to 40.0% CPU (below recovery threshold 60.0%) for 2 consecutive samples.
   - Result: Alert transitioned to `status: recovered` with `recovered_at` timestamp populated. Active alert count dropped to 0.
5. **Cooldown Window Suppression**:
   - Re-breach at 95.0% CPU attempted within the 30-second cooldown window.
   - Result: **Suppressed**. Active alert count remained 0.
6. **Post-Cooldown Re-Alerting**:
   - Re-breach attempted after the 30-second cooldown window expired.
   - Result: **Alert #2 created** (`status: active`, total rows = 2).
7. **Streak Reset on Invalid/Missing Telemetry**:
   - Verified that missing or unparseable metric samples reset the consecutive breach counter, preventing false escalations.

### B. Genuine Live vs Controlled Demonstration Paths
- **Path A (Genuine Live Demonstration)**:
  - Host telemetry observed naturally: CPU = 0.0%, RAM = 56.9%, Swap = 7.6%.
  - Production thresholds: CPU Warning = 72.0%, RAM Warning = 80.0%, Swap Warning = 50.0%.
  - **Factual Finding**: **No genuine live alert was observed.** The system accurately reports 0 active alerts and renders the baseline health recommendation.
- **Path B (Controlled Test Demonstration)**:
  - Documented as an automated, reproducible script in `docs/FINAL_DEMO_SCRIPT.md` labelled `'SIMULATED TEST EVENT'`.
  - Runs in a temporary database without modifying `backend/data/sentinel.db`.

---

## 4. Workstream 3: WSGI, Deployment, and WSL2 Validation

### A. WSGI Implementation Audit
- **Callable Compatibility**:
  - `backend/wsgi.py` explicitly exports both `application = create_app(ProductionConfig)` and `app = application`.
  - Matches Gunicorn invocation: `gunicorn ... wsgi:app`.
  - Matches Waitress invocation: `waitress-serve ... wsgi:application`.
- **WSGI Server Distinctions**:
  - The local fallback runner executed by `python backend/wsgi.py` uses Flask's built-in Werkzeug server with `debug=False`. The startup banner explicitly logs:  
    `WARNING: This is a development server. Do not use it in a production deployment. Use a production WSGI server instead.`
  - On Linux/WSL2, Gunicorn is the documented production server.

### B. Requirements & Python Version Compatibility
- `backend/requirements.txt`:
  - `Flask>=3.0.0` (Requires Python 3.8+)
  - `pytest>=8.0.0` (Requires Python 3.8+)
  - `psutil>=5.9.0` (Precompiled C-extensions on Windows/Linux)
  - `python-dotenv>=1.0.0` (Pure Python)
- **Dependency Finding**: Neither `gunicorn` nor `waitress` is currently declared in `backend/requirements.txt`. While `wsgi.py` handles this with a fallback on Windows, production deployment on Linux requires running `pip install gunicorn`.

### C. Systemd Service Unit Audit (`deployment/os-sentinel.service`)
- **Unit Template Analysis**:
  - `WorkingDirectory=/opt/os-sentinel/backend`
  - `ExecStart=/opt/os-sentinel/backend/.venv/bin/gunicorn --workers 1 --threads 4 --bind 127.0.0.1:5000 wsgi:app`
  - `SENTINEL_DB_PATH=/var/lib/os-sentinel/data/sentinel.db`
  - `ProtectHome=read-only`, `NoNewPrivileges=true`
  - `Restart=on-failure`, `RestartSec=5s`
- **Deployment Status**:
  - The paths `/opt/os-sentinel` and `/var/lib/os-sentinel` are standard FHS Linux placeholders and have **NOT** been deployed to the filesystem.
  - The unit file has **NOT** been installed to `/etc/systemd/system/` or activated via `systemctl start`. It is an uninstalled reference template.

### D. WSL2 Kernel vs Full Web-App Validation
- **Direct Linux `/proc` Telemetry**: **VERIFIED**
  - Executed inside Ubuntu WSL2 (kernel `6.18.33.2-microsoft-standard-WSL2`, Python 3.14.4).
  - Successfully read `/proc/loadavg` (`0.28, 0.09, 0.03`), `/proc/uptime` (`127.9s`), `/proc/meminfo` (`12.38 GB total`), and enumerated 74 Linux guest processes.
- **Full Flask Application Inside WSL2**: **UNVERIFIED (Documented Blocker)**
  - Python 3.14.4 in the Ubuntu WSL2 environment lacks `pip`, `ensurepip`, and `python3-venv` packages.
  - `flask`, `psutil`, and dependencies are not installed in the WSL2 guest.
  - Resolving this requires running `sudo apt update && sudo apt install -y python3-pip python3-venv`, which requires elevated privileges. Per strict safety instructions, external package installation was halted.

### E. Security & Redaction Verification
- **Command-Line Secret Redaction**: Verified across `--token=value`, `--token value`, `--api-key=value`, `--api-key value`, `--password=value`, `--password value`, `-p value`, `-p=value`, `--secret=value`, `--secret value`. All sensitive arguments are replaced with `***`. Ordinary flags (`--host`, `--port`, `--verbose`) remain untouched.
- **Strict CORS Defense**: Unapproved origins (`http://evil.com`) receive `Access-Control-Allow-Origin: None`. Approved origins (`http://localhost:5173`) receive matching CORS headers.
- **Loopback Enforcement**: Default configuration binds strictly to `127.0.0.1` with `DEBUG=False`.

---

## 5. Test Suite & Code Quality Results

| Test Category | Command | Files / Tests | Duration | Exit Status |
|---|---|---|---|---|
| **Full Backend Regression** | `python -m unittest discover -s backend/tests -t backend -p "test_*.py"` | 10 files / 68 tests | 26.081s | **0 (OK)** |
| **Subprocess Restart Durability** | `python -m unittest discover -s backend/tests -t backend -p "test_process_restart_persistence.py"` | 1 file / 1 test | 1.103s | **0 (OK)** |
| **Frontend Component Tests** | `npm --prefix frontend test -- --run` | 3 files / 13 tests | 2.020s | **0 (OK)** |
| **Frontend Static Linter** | `npm --prefix frontend run lint` (`oxlint`) | 20 files / 116 rules | 61 ms | **0 (0 Errors, 6 Advisory Warnings)** |
| **Frontend Production Build** | `npm --prefix frontend run build` (`tsc -b && vite build`) | Production dist | 197 ms | **0 (Built successfully)** |

### Note on Linter Warnings
The 6 advisory warnings flagged by `oxlint` are `react(set-state-in-effect)` in `RecommendationsPage`, `AlertsPage`, `App`, `HistoryPage`, `ProcessesPage`, and `SettingsPage`. These reflect initial data fetching calls inside `useEffect`. In React 19 + TypeScript, these are non-blocking advisory warnings and cause zero compilation or runtime errors.

---

## 6. Known Limitations

1. **Authentication Boundary**:
   - OS Sentinel relies on CORS origin restriction and loopback binding (`127.0.0.1`).
   - CORS is enforced by browsers, not non-browser HTTP clients (`curl`, scripts). Production public deployment requires a reverse proxy (e.g. Nginx) with TLS termination and token authentication.
2. **Read-Only Scope**:
   - The platform strictly forbids process termination, suspension, or reprioritization. It is an explainable decision-support dashboard, not an automated process killer.
3. **Windows Host vs WSL2 Linux Scope**:
   - When running on a Windows host, Linux kernel load averages (`/proc/loadavg`) are unsupported and explicitly labelled as such.
   - WSL2 guest kernel telemetry was verified via direct `/proc` inspection, but full Flask web server execution inside WSL2 remains unverified due to missing guest Python packages (`python3-pip`).
4. **Systemd Service Unit**:
   - `deployment/os-sentinel.service` contains FHS paths (`/opt/os-sentinel`, `/var/lib/os-sentinel`) and has not been activated on a live systemd supervisor.

---

## 7. Final Status Determination

### Selected Status: **COMPLETE WITH DOCUMENTED LIMITATIONS**

**Justification**:
- Core functionality, explainable resource-pressure detection, non-destructive recommendations, SQLite WAL persistence, process caching (~1,400x speedup), command-line redaction, and dark-themed operations dashboard are 100% implemented, verified, and passing.
- 68/68 backend tests, 13/13 frontend tests, and 9/9 live API smoke tests passed with zero failures.
- Direct Linux `/proc` telemetry reading in Ubuntu WSL2 passed.
- Limitations (unverified full Flask inside WSL2 due to missing guest `pip`, uninstalled systemd template, lack of token authentication for non-browser clients) are explicitly documented and distinguished from verified components.

---

## 8. Academic Viva Revision Sheet

### 1. Virtual Memory Size (VMS) vs Resident Set Size (RSS)
- **Virtual Memory Size (VMS)**: The total address space assigned to a process by the OS memory management unit, including executable code, heap, paged-out memory, and shared library mappings.
- **Resident Set Size (RSS)**: The portion of virtual memory currently resident in physical RAM frames.
- **Application**: OS Sentinel reports both, prioritizing RSS in recommendations because physical RAM saturation directly causes paging and swap thrashing.

### 2. Linux Run-Queue Load Average vs Instantaneous CPU Utilization
- **CPU Utilization (%)**: Percentage of time processor cores were active over a discrete time slice.
- **Load Average**: Derived from `/proc/loadavg` as an exponential moving average (1m, 5m, 15m) counting threads in `TASK_RUNNING` (CPU runnable) and `TASK_UNINTERRUPTIBLE` (waiting on disk I/O).
- **Application**: Allows operators to distinguish CPU computation saturation from disk I/O bottlenecks.

### 3. SQLite Write-Ahead Logging (WAL) & Multi-Threaded Concurrency
- **Rollback Journal**: Locks the entire database file during writes, blocking concurrent readers.
- **WAL Mode (`PRAGMA journal_mode=WAL;`)**: Writes append to a `.wal` file while readers read snapshots from the main database without blocking.
- **Busy Timeout (`PRAGMA busy_timeout = 5000;`)**: Retries locked transactions for up to 5 seconds, eliminating race conditions between the background collector and HTTP endpoints.

### 4. Persistence Windows and Recovery Hysteresis
- **Persistence Window**: Requires $N$ consecutive samples ($N \ge 2$) above a threshold before triggering an alert, suppressing transient spikes.
- **Recovery Hysteresis**: Alert resolution requires metric values to drop below an asymmetric recovery threshold (strictly lower than warning threshold) for $N$ consecutive samples, preventing alert flapping.

### 5. CORS Origin Defense vs Authentication
- **CORS**: A browser security protocol preventing unauthorized origin websites from reading sensitive API responses.
- **Limitation**: Does not protect against direct HTTP calls from scripts or tools. Production internet deployment requires TLS and API authentication.

### 6. Why OS Sentinel is Strictly Read-Only
- Automatic process killing based on metric thresholds risks terminating essential background services or causing database corruption.
- OS Sentinel is an educational decision-support platform, not an IEC 61508 safety-critical control loop. It empowers operators with diagnostic guidance rather than automated destructive actions.
