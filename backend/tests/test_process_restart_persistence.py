import os
import sys
import json
import time
import unittest
import tempfile
import subprocess

class ProcessRestartPersistenceTestCase(unittest.TestCase):
    """
    Validates genuine operating system process lifecycle restart persistence.
    Spawns independent OS subprocesses with separate PIDs and memory spaces to verify
    SQLite WAL persistence, recovery timestamps, alert states, and settings across process boundaries.
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "restart_test.db")
        self.backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_genuine_os_process_restart_persistence(self):
        # 1. PROCESS 1: Launch independent OS subprocess to write initial state
        worker1_code = f"""
import sys
sys.path.insert(0, r"{self.backend_dir}")
from app.storage.database import Database

db = Database(r"{self.db_path}")

# Write metric snapshot
db.insert_metrics({{
    "timestamp": "2026-10-23T11:00:00Z",
    "cpu": {{"total_percent": 55.5}},
    "memory": {{"percent": 42.0}},
}})

# Write active alert
alert1_id = db.insert_alert({{
    "alert_type": "cpu_pressure",
    "severity": "critical",
    "status": "active",
    "first_observed_at": "2026-10-23T11:00:00Z",
    "last_observed_at": "2026-10-23T11:01:00Z",
    "evidence": {{"current_value_percent": 95.0}},
    "explanation": "Critical CPU load in process 1",
}})

# Write recovered alert
alert2_id = db.insert_alert({{
    "alert_type": "memory_pressure",
    "severity": "warning",
    "status": "active",
    "first_observed_at": "2026-10-23T10:45:00Z",
    "last_observed_at": "2026-10-23T10:50:00Z",
    "evidence": {{"current_percent": 82.0}},
    "explanation": "Memory warning in process 1",
}})
db.update_alert(alert2_id, {{
    "status": "recovered",
    "recovered_at": "2026-10-23T10:55:00Z",
}})

# Write custom detection settings
db.save_settings("detection_settings", {{
    "cpu": {{"warning": 68.0, "critical": 88.0, "recovery": 58.0}}
}})

print(f"PROCESS_1_DONE:alert1={{alert1_id}},alert2={{alert2_id}}")
"""
        proc1 = subprocess.run(
            [sys.executable, "-c", worker1_code],
            capture_output=True,
            text=True,
            check=True
        )
        self.assertIn("PROCESS_1_DONE", proc1.stdout)

        # Confirm database file exists on disk
        self.assertTrue(os.path.exists(self.db_path))

        # 2. PROCESS 2: Launch a second completely separate OS subprocess with fresh PID and address space
        worker2_code = f"""
import sys
import json
sys.path.insert(0, r"{self.backend_dir}")
from app.storage.database import Database

db = Database(r"{self.db_path}")

history = db.get_history(limit=10)
active_alerts = db.get_alerts(status="active")
recovered_alerts = db.get_alerts(status="recovered")
settings = db.get_settings("detection_settings")

result = {{
    "history_count": len(history),
    "history_cpu": history[0]["cpu"]["total_percent"] if history else None,
    "active_count": len(active_alerts),
    "active_severity": active_alerts[0]["severity"] if active_alerts else None,
    "recovered_count": len(recovered_alerts),
    "recovered_at": recovered_alerts[0]["recovered_at"] if recovered_alerts else None,
    "cpu_warning_setting": settings["cpu"]["warning"] if settings else None,
}}
print("PROCESS_2_RESULT:" + json.dumps(result))
"""
        proc2 = subprocess.run(
            [sys.executable, "-c", worker2_code],
            capture_output=True,
            text=True,
            check=True
        )
        self.assertIn("PROCESS_2_RESULT:", proc2.stdout)

        # Parse Process 2 output
        line = [l for l in proc2.stdout.splitlines() if l.startswith("PROCESS_2_RESULT:")][0]
        data = json.loads(line.replace("PROCESS_2_RESULT:", ""))

        # 3. Assertions across the process restart boundary
        self.assertEqual(data["history_count"], 1)
        self.assertEqual(data["history_cpu"], 55.5)
        self.assertEqual(data["active_count"], 1)
        self.assertEqual(data["active_severity"], "critical")
        self.assertEqual(data["recovered_count"], 1)
        self.assertEqual(data["recovered_at"], "2026-10-23T10:55:00Z")
        self.assertEqual(data["cpu_warning_setting"], 68.0)

if __name__ == "__main__":
    unittest.main()
