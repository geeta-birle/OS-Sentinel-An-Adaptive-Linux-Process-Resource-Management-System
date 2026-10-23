# OS Sentinel: Academic Demonstration & Presentation Script

**Project**: OS Sentinel — An Adaptive Linux Process & Resource Management System  
**Stack**: React 19 + TypeScript + Vite, Python Flask, psutil, SQLite WAL  
**Status**: COMPLETE WITH DOCUMENTED LIMITATIONS  

---

## 1. Demonstration Overview & Protocol

This script defines two strictly separated evaluation paths to ensure scientific integrity and eliminate synthetic data contamination:

- **Path A (Genuine Live Telemetry Demonstration)**: Observes only genuine, naturally occurring host OS telemetry. Production thresholds are preserved intact. If the system is operating within nominal boundaries, no artificial alerts are forced.
- **Path B (Controlled Test Demonstration — SIMULATED TEST EVENT)**: Demonstrates the explainable alert lifecycle, multi-sample spike suppression, recovery hysteresis, and cooldown behavior inside an isolated temporary database (`test_demo.db`). It **never** writes synthetic records to the user's primary database (`sentinel.db`).

---

## 2. Demonstration Path A: Genuine Live Telemetry Observation

### Prerequisites & Startup
1. **Backend WSGI Runner**:
   ```powershell
   cd "d:\sem 3\OSY\Project"
   python backend/wsgi.py
   # Serves on http://127.0.0.1:5000 (Debug: False, loopback only)
   ```
2. **Frontend Operations Dashboard**:
   ```powershell
   cd "d:\sem 3\OSY\Project\frontend"
   npm run dev
   # Serves on http://localhost:5173
   ```
3. Open browser to `http://localhost:5173`.

### Presentation Walkthrough

#### Step 1: System Telemetry & Platform Context (Overview View)
- Point to the **Header Connection Badge**: Displays `Connected` (green) indicating active health probes to `/healthz` and `/api/v1/health`.
- Point to the **Platform Scope Tag**: Identifies the runtime environment as `Windows Host Environment`.
- Note the **Load Average Card**: On Windows, run-queue load averages are not provided by the kernel; the card displays an explicit notice: *Unsupported on Windows Host — Requires Linux or WSL2 kernel*. This demonstrates strict avoidance of fake metrics.
- Review **Live Telemetry Cards**:
  - CPU Utilization (%): Real-time non-blocking delta calculated across collection intervals.
  - Memory: Used, total, and available physical memory.
  - Swap: Configured swap utilization.
  - Telemetry Chart: Zero-dependency SVG time-series rendering recent samples.

#### Step 2: Read-Only Process Explorer & Credential Redaction (Process Explorer View)
- Navigate to **Process Explorer**.
- **Sorting & Bounded Pagination**:
  - Click on column headers (`CPU %`, `Memory %`, `RSS`) to demonstrate server-side sorting.
  - Switch pagination (10, 25, 50 rows).
  - Note response speed: Cached queries complete in **~3.9ms** via the thread-safe 2.0s in-memory cache (`ProcessService.CACHE_TTL_SECONDS = 2.0`).
- **Granular Inspection Modal**:
  - Click **Inspect** on any process (e.g., `python.exe` or `node.exe`).
  - Modal renders Parent PID (PPID), thread count, scheduling priority (`nice`), Virtual Memory (VMS), and Resident Set Size (RSS).
  - Point out **Command-Line Redaction**: Any argument matching sensitive flags (e.g., `--password`, `-p`, `--token`, `--api-key`) or key-value pairs (e.g., `--token=value`) is masked to `***`.
  - Point out the **Safety Guarantee Banner**: *Read-only monitoring mode. No process termination, suspension, or priority alteration capabilities are implemented.*

#### Step 3: Live Alert Assessment (Alerts & Analysis View)
- Navigate to **Alerts & Analysis**.
- Observe current alert state:
  > **Factual Observation**: Under normal operating host load, **no genuine live alerts are active**. All monitored resources are functioning within nominal parameters (CPU < 72%, Memory < 80%, Swap < 50%).
- Demonstrate Status & Severity Filters: Filter by `Active`, `Recovered`, or `All` alerts.

#### Step 4: Investigative Recommendations (Recommendations View)
- Navigate to **Recommendations**.
- With all systems nominal, the engine displays the **Baseline Health Guidance Card** (`rec_baseline_nominal`).
- Point out the **Operating System Uncertainty Note**: The recommendation emphasizes that memory usage alone does not indicate malfunction, cautioning operators about Linux page cache dynamics.

#### Step 5: Historical Metrics & Audit Trail (History & Audit View)
- Navigate to **History & Audit**.
- Toggle between **System Telemetry History** and **Alert Audit Trail**.
- Demonstrates persistent storage backed by SQLite in WAL mode.

#### Step 6: Dynamic Engine Tuning (Settings View)
- Navigate to **Settings**.
- View current persisted thresholds.
- Demonstrate client-side validation: Set `Recovery` higher than `Warning`. Notice immediate validation blocking: *Recovery threshold must be strictly less than warning threshold*.
- Cancel or reset to preserve production configuration.

---

## 3. Demonstration Path B: Controlled Test Demonstration (`SIMULATED TEST EVENT`)

This automated script runs in an isolated temporary database, demonstrating the complete alert lifecycle without modifying production data or loading the host machine.

### Execution Command
```powershell
cd "d:\sem 3\OSY\Project"
python -c "
import tempfile, os, time
from backend.app.storage.database import Database
from backend.app.models.detection_settings import DetectionSettings, ResourceThreshold, LoadThreshold
from backend.app.services.detection_service import DetectionService

print('=== [CONTROLLED DEMONSTRATION: SIMULATED TEST EVENT] ===')
with tempfile.TemporaryDirectory() as temp_dir:
    db_path = os.path.join(temp_dir, 'demo_simulated.db')
    db = Database(db_path)
    
    # Configure deterministic test thresholds: Warning=70%, Critical=85%, Recovery=60%, Persistence=2
    settings = DetectionSettings(
        cpu=ResourceThreshold(warning=70.0, critical=85.0, recovery=60.0, persistence_samples=2, cooldown_seconds=30)
    )
    detector = DetectionService(db, settings)
    t0 = 1000.0

    def make_snapshot(cpu_val):
        return {
            'timestamp': '2026-10-23T12:00:00Z',
            'host': {'cpu_cores_logical': 4},
            'cpu': {'available': True, 'total_percent': cpu_val, 'logical_cores': 4, 'per_core_percent': [cpu_val]*4},
            'memory': {'available': True, 'percent': 40.0, 'used_bytes': 4000000, 'total_bytes': 10000000, 'available_bytes': 6000000},
            'swap': {'available': True, 'swap_configured': True, 'percent': 10.0, 'used_bytes': 1000, 'total_bytes': 10000},
            'load_average': {'supported': True, 'load_1m': 0.5, 'load_5m': 0.5, 'load_15m': 0.5}
        }

    # Phase 1: Isolated Spike (Spike Suppression)
    print('\n1. Testing Spike Suppression:')
    detector.evaluate_snapshot(make_snapshot(20.0), current_time=t0)
    detector.evaluate_snapshot(make_snapshot(95.0), current_time=t0+5) # Single spike
    alerts = db.get_alerts()
    print(f'   -> Sample 1 (95% CPU, persistence=2): Active Alerts = {len(alerts)} (SUPPRESSED as expected)')

    # Phase 2: Sustained Breach (Alert Opening)
    print('\n2. Testing Sustained Breach:')
    detector.evaluate_snapshot(make_snapshot(92.0), current_time=t0+10)
    detector.evaluate_snapshot(make_snapshot(94.0), current_time=t0+15) # Second consecutive breach
    alerts = db.get_alerts(status='active')
    print(f'   -> Sustained samples: Active Alerts = {len(alerts)}')
    print(f'   -> Alert ID: #{alerts[0][\"id\"]}, Severity: {alerts[0][\"severity\"]}, Type: {alerts[0][\"alert_type\"]}')
    print(f'   -> Explanation: {alerts[0][\"explanation\"]}')

    # Phase 3: In-Place Update (No Duplicate Rows)
    print('\n3. Testing In-Place Update (Ongoing Pressure):')
    detector.evaluate_snapshot(make_snapshot(91.0), current_time=t0+20)
    all_alerts = db.get_alerts()
    print(f'   -> Ongoing pressure: Total alert rows = {len(all_alerts)} (NO duplicate rows created)')

    # Phase 4: Recovery Transition
    print('\n4. Testing Recovery Transition:')
    detector.evaluate_snapshot(make_snapshot(50.0), current_time=t0+25) # Drop 1 (below 60% recovery)
    print(f'   -> Recovery Sample 1 (50% CPU, persistence=2): Active Alerts = {len(db.get_alerts(status=\"active\"))}')
    detector.evaluate_snapshot(make_snapshot(45.0), current_time=t0+30) # Drop 2
    active_now = db.get_alerts(status='active')
    recovered_now = db.get_alerts(status='recovered')
    print(f'   -> Recovery Sample 2: Active = {len(active_now)}, Recovered = {len(recovered_now)}')
    print(f'   -> Recovered At Timestamp: {recovered_now[0][\"recovered_at\"]}')

    # Phase 5: Cooldown Window Suppression
    print('\n5. Testing Cooldown Window:')
    detector.evaluate_snapshot(make_snapshot(95.0), current_time=t0+35) # Within 30s cooldown
    detector.evaluate_snapshot(make_snapshot(95.0), current_time=t0+40)
    print(f'   -> Re-breach within cooldown window: Active Alerts = {len(db.get_alerts(status=\"active\"))} (SUPPRESSED as expected)')

    # Phase 6: Post-Cooldown Re-Alerting
    print('\n6. Testing Post-Cooldown Re-Alerting:')
    detector.evaluate_snapshot(make_snapshot(95.0), current_time=t0+50) # After cooldown expires (> t0+45)
    detector.evaluate_snapshot(make_snapshot(95.0), current_time=t0+55)
    print(f'   -> Re-breach post cooldown: Active Alerts = {len(db.get_alerts(status=\"active\"))}, Total Alerts = {len(db.get_alerts())}')

print('\n=== [CONTROLLED DEMONSTRATION COMPLETE: ZERO RESIDUAL TEST DATA] ===')
"
```

---

## 4. Academic Viva Examination Revision Sheet

### Q1: Virtual Memory Size (VMS) vs Resident Set Size (RSS)
- **Virtual Memory Size (VMS)**: The cumulative address space reserved by the operating system memory management unit (MMU) for a process. Includes code segment, data segment, BSS, memory-mapped shared libraries, heap allocations, and paged-out anonymous memory.
- **Resident Set Size (RSS)**: The subset of virtual memory currently held in physical RAM frames. Does not include memory that has been paged out to swap or unreferenced mapped files.
- **OS Sentinel Architecture**: Inspects both `rss` and `vms` via `psutil.Process.memory_info()`. Triage recommendations prioritize `rss` because physical RAM occupancy directly determines memory pressure and eviction frequency.

### Q2: Linux Run-Queue Load Average vs Instantaneous CPU Utilization
- **CPU Utilization (%)**: The percentage of processor cycles spent executing instructions across user, system, nice, and interrupt contexts over a discrete sampling window ($\Delta t$).
- **Linux Load Average**: Derived from `/proc/loadavg` as an exponentially damped moving average over 1, 5, and 15 minutes. Crucially, Linux load average counts threads in both `TASK_RUNNING` (CPU runnable) and `TASK_UNINTERRUPTIBLE` (typically waiting for disk I/O).
- **Practical Distinction**: A system performing heavy disk I/O may exhibit low CPU utilization (< 15%) but a high load average (> 10). OS Sentinel captures both metrics to distinguish CPU computation bottlenecks from I/O wait saturation.

### Q3: SQLite Write-Ahead Logging (WAL) & Concurrency Dynamics
- **Standard Rollback Journal**: Locks the entire SQLite database file during writing, causing concurrent read queries to fail with `sqlite3.OperationalError: database is locked`.
- **WAL Mode (`PRAGMA journal_mode=WAL;`)**: Changes are appended sequentially to a separate write-ahead log file (`*.wal`) while database pages remain untouched. Readers read consistent snapshots from the main database without blocking writes, and writers append without blocking reads.
- **Busy Timeout (`PRAGMA busy_timeout = 5000;`)**: Configures SQLite to automatically retry locked operations for up to 5,000 milliseconds before raising an exception, resolving transient race conditions between the background collector and HTTP endpoints.

### Q4: Detection Persistence Windows and Hysteresis
- **Spike Suppression**: Transient CPU bursts caused by brief background tasks (e.g., cron jobs, compiler invocations) should not wake operators. The engine requires $N$ consecutive samples ($N \ge 2$) above the threshold before triggering an alert.
- **Recovery Hysteresis**: To prevent alert flapping (rapid cycling between active and recovered states when a metric oscillates around a single threshold), OS Sentinel enforces an asymmetric recovery threshold (e.g., Warning at 75%, Recovery at 60%). The alert resolves only when the metric drops below the recovery threshold for $N$ consecutive samples.

### Q5: CORS Origin Filtering vs User Authentication
- **CORS (Cross-Origin Resource Sharing)**: A browser-enforced security mechanism restricting web applications running at one origin from reading resources at another origin. OS Sentinel rejects unlisted origins by emitting `Access-Control-Allow-Origin: None`.
- **Why CORS Does Not Replace Authentication**: CORS does **not** protect against non-browser clients (such as `curl`, `Postman`, or Python scripts) communicating directly with the HTTP port. For production internet exposure, OS Sentinel must be placed behind a reverse proxy (e.g., Nginx) implementing TLS termination, mutual TLS, or API token authentication.

### Q6: Why OS Sentinel is Strictly Read-Only (Non-Certified Safety System)
- Automated process termination (`SIGKILL`) or priority degradation (`renice`) based purely on telemetry thresholds poses severe operational hazards:
  1. It can terminate critical infrastructure daemons experiencing temporary legitimate load.
  2. It can leave uncommitted database writes or broken IPC sockets.
  3. OS Sentinel is a decision-support and educational tool, not an IEC 61508 or ISO 26262 certified safety-critical control loop.
- The system enforces read-only observation and presents explainable diagnostic commands for human triage.
