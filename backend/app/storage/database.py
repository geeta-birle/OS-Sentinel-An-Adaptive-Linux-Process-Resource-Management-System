import os
import json
import sqlite3
import threading
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional

class Database:
    """
    Thread-safe SQLite storage for OS Sentinel time-series system measurements,
    dynamic detection configuration, and explainable alert state persistence.
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
            
        conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=10.0)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA busy_timeout = 5000;")
        except Exception:
            pass
        return conn

    def _init_db(self) -> None:
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                try:
                    cursor.execute("PRAGMA journal_mode=WAL;")
                    cursor.execute("PRAGMA synchronous=NORMAL;")
                except Exception:
                    pass
                # 1. System Metrics Time-series Table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS system_metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        cpu_percent REAL,
                        memory_percent REAL,
                        memory_used INTEGER,
                        memory_total INTEGER,
                        swap_percent REAL,
                        uptime_seconds REAL,
                        load_1m REAL,
                        raw_metrics_json TEXT NOT NULL
                    );
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_metrics_timestamp 
                    ON system_metrics(timestamp);
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_metrics_id 
                    ON system_metrics(id DESC);
                """)

                # 2. Resource Pressure Alerts Table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS alerts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        alert_type TEXT NOT NULL,
                        severity TEXT NOT NULL,
                        status TEXT NOT NULL,
                        first_observed_at TEXT NOT NULL,
                        last_observed_at TEXT NOT NULL,
                        recovered_at TEXT,
                        evidence_json TEXT NOT NULL,
                        explanation TEXT NOT NULL
                    );
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_alerts_status 
                    ON alerts(status, alert_type);
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_alerts_last_observed 
                    ON alerts(last_observed_at DESC);
                """)

                # 3. Dynamic Configuration Table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS settings (
                        key TEXT PRIMARY KEY,
                        value_json TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                """)

                conn.commit()
            finally:
                conn.close()

    # --- Metrics Time-Series Methods ---

    def insert_metrics(self, metrics: Dict[str, Any]) -> int:
        timestamp = metrics.get("timestamp") or datetime.now(timezone.utc).isoformat()
        cpu_percent = metrics.get("cpu", {}).get("total_percent")
        mem = metrics.get("memory", {})
        mem_percent = mem.get("percent")
        mem_used = mem.get("used_bytes")
        mem_total = mem.get("total_bytes")
        swap_percent = metrics.get("swap", {}).get("percent")
        uptime = metrics.get("uptime_seconds")
        load_1m = metrics.get("load_average", {}).get("load_1m")
        raw_json = json.dumps(metrics)

        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO system_metrics (
                        timestamp, cpu_percent, memory_percent, memory_used,
                        memory_total, swap_percent, uptime_seconds, load_1m,
                        raw_metrics_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    timestamp, cpu_percent, mem_percent, mem_used,
                    mem_total, swap_percent, uptime, load_1m, raw_json
                ))
                conn.commit()
                return cursor.lastrowid
            finally:
                conn.close()

    def get_history(self, limit: int = 50, since: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                if since:
                    cursor.execute("""
                        SELECT raw_metrics_json FROM system_metrics
                        WHERE timestamp >= ?
                        ORDER BY id DESC
                        LIMIT ?
                    """, (since, limit))
                else:
                    cursor.execute("""
                        SELECT raw_metrics_json FROM system_metrics
                        ORDER BY id DESC
                        LIMIT ?
                    """, (limit,))
                rows = cursor.fetchall()
                results = []
                for row in reversed(rows):
                    try:
                        results.append(json.loads(row["raw_metrics_json"]))
                    except Exception:
                        pass
                return results
            finally:
                conn.close()

    def get_count(self) -> int:
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM system_metrics")
                return cursor.fetchone()[0]
            finally:
                conn.close()

    def prune_history(self, max_records: int = 2000, retention_hours: int = 24) -> int:
        deleted_count = 0
        cutoff_time = (datetime.now(timezone.utc) - timedelta(hours=retention_hours)).isoformat()

        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM system_metrics WHERE timestamp < ?", (cutoff_time,))
                deleted_count += cursor.rowcount

                cursor.execute("SELECT COUNT(*) FROM system_metrics")
                total = cursor.fetchone()[0]
                if total > max_records:
                    excess = total - max_records
                    cursor.execute("""
                        DELETE FROM system_metrics WHERE id IN (
                            SELECT id FROM system_metrics ORDER BY id ASC LIMIT ?
                        )
                    """, (excess,))
                    deleted_count += cursor.rowcount

                conn.commit()
                return deleted_count
            finally:
                conn.close()

    # --- Phase 3 Alerts Persistence Methods ---

    def insert_alert(self, alert: Dict[str, Any]) -> int:
        first_observed = alert.get("first_observed_at") or datetime.now(timezone.utc).isoformat()
        last_observed = alert.get("last_observed_at") or first_observed
        evidence_json = json.dumps(alert.get("evidence", {}))

        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO alerts (
                        alert_type, severity, status, first_observed_at,
                        last_observed_at, recovered_at, evidence_json, explanation
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    alert["alert_type"],
                    alert["severity"],
                    alert.get("status", "active"),
                    first_observed,
                    last_observed,
                    alert.get("recovered_at"),
                    evidence_json,
                    alert.get("explanation", "")
                ))
                conn.commit()
                return cursor.lastrowid
            finally:
                conn.close()

    def update_alert(self, alert_id: int, updates: Dict[str, Any]) -> None:
        fields = []
        params = []
        for key in ("severity", "status", "last_observed_at", "recovered_at", "explanation"):
            if key in updates:
                fields.append(f"{key} = ?")
                params.append(updates[key])
        if "evidence" in updates:
            fields.append("evidence_json = ?")
            params.append(json.dumps(updates["evidence"]))

        if not fields:
            return

        params.append(alert_id)
        sql = f"UPDATE alerts SET {', '.join(fields)} WHERE id = ?"

        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(sql, tuple(params))
                conn.commit()
            finally:
                conn.close()

    def get_active_alert_by_type(self, alert_type: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM alerts
                    WHERE alert_type = ? AND status = 'active'
                    ORDER BY id DESC LIMIT 1
                """, (alert_type,))
                row = cursor.fetchone()
                if not row:
                    return None
                return self._format_alert_row(row)
            finally:
                conn.close()

    def get_alerts(
        self,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        clauses = []
        params: List[Any] = []

        if status:
            clauses.append("status = ?")
            params.append(status)
        if severity:
            clauses.append("severity = ?")
            params.append(severity)

        where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"SELECT * FROM alerts {where_clause} ORDER BY id DESC LIMIT ?"
        params.append(limit)

        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(sql, tuple(params))
                rows = cursor.fetchall()
                return [self._format_alert_row(r) for r in rows]
            finally:
                conn.close()

    def get_alert_by_id(self, alert_id: int) -> Optional[Dict[str, Any]]:
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,))
                row = cursor.fetchone()
                if not row:
                    return None
                return self._format_alert_row(row)
            finally:
                conn.close()

    @staticmethod
    def _format_alert_row(row: sqlite3.Row) -> Dict[str, Any]:
        data = dict(row)
        try:
            data["evidence"] = json.loads(data.pop("evidence_json", "{}"))
        except Exception:
            data["evidence"] = {}
        return data

    # --- Phase 3 Settings Persistence Methods ---

    def save_settings(self, key: str, data: Dict[str, Any]) -> None:
        updated_at = datetime.now(timezone.utc).isoformat()
        val_json = json.dumps(data)

        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO settings (key, value_json, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET
                        value_json = excluded.value_json,
                        updated_at = excluded.updated_at
                """, (key, val_json, updated_at))
                conn.commit()
            finally:
                conn.close()

    def get_settings(self, key: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT value_json FROM settings WHERE key = ?", (key,))
                row = cursor.fetchone()
                if not row:
                    return None
                return json.loads(row["value_json"])
            finally:
                conn.close()
