import os
import unittest
import tempfile
from datetime import datetime, timezone, timedelta
from app.storage.database import Database

class DatabaseTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_sentinel.db")
        self.db = Database(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_database_initialization(self):
        """Verifies tables and indexes are created properly upon initialization."""
        self.assertTrue(os.path.exists(self.db_path))
        self.assertEqual(self.db.get_count(), 0)

    def test_insert_and_get_history(self):
        """Verifies inserting metric snapshots and retrieving chronologically."""
        sample_metrics_1 = {
            "timestamp": "2026-10-22T10:00:00Z",
            "cpu": {"total_percent": 15.5},
            "memory": {"percent": 45.2, "used_bytes": 4000000000, "total_bytes": 16000000000},
            "swap": {"percent": 0.0},
            "uptime_seconds": 3600.0,
            "load_average": {"load_1m": 0.5}
        }
        sample_metrics_2 = {
            "timestamp": "2026-10-22T10:01:00Z",
            "cpu": {"total_percent": 25.0},
            "memory": {"percent": 48.0, "used_bytes": 4200000000, "total_bytes": 16000000000},
            "swap": {"percent": 0.0},
            "uptime_seconds": 3660.0,
            "load_average": {"load_1m": 0.8}
        }

        row1 = self.db.insert_metrics(sample_metrics_1)
        row2 = self.db.insert_metrics(sample_metrics_2)
        self.assertGreater(row1, 0)
        self.assertGreater(row2, row1)
        self.assertEqual(self.db.get_count(), 2)

        # Query all history
        history = self.db.get_history(limit=10)
        self.assertEqual(len(history), 2)
        # Should be chronologically ascending
        self.assertEqual(history[0]["timestamp"], "2026-10-22T10:00:00Z")
        self.assertEqual(history[1]["timestamp"], "2026-10-22T10:01:00Z")

    def test_history_limit_and_since(self):
        """Verifies history limits and since timestamp filtering."""
        for i in range(10):
            ts = f"2026-10-22T10:0{i}:00Z"
            self.db.insert_metrics({
                "timestamp": ts,
                "cpu": {"total_percent": float(i * 5)},
                "memory": {"percent": 40.0},
            })

        # Limit to 3 items
        limited = self.db.get_history(limit=3)
        self.assertEqual(len(limited), 3)
        # Should be the most recent 3 items, chronologically ascending
        self.assertEqual(limited[0]["timestamp"], "2026-10-22T10:07:00Z")
        self.assertEqual(limited[2]["timestamp"], "2026-10-22T10:09:00Z")

        # Query since 10:05:00Z
        filtered = self.db.get_history(limit=20, since="2026-10-22T10:05:00Z")
        self.assertEqual(len(filtered), 5)
        self.assertEqual(filtered[0]["timestamp"], "2026-10-22T10:05:00Z")

    def test_prune_by_max_records(self):
        """Verifies pruning deletes oldest records when total exceeds max_records."""
        for i in range(10):
            self.db.insert_metrics({
                "timestamp": f"2026-10-22T10:{i:02d}:00Z",
                "cpu": {"total_percent": 10.0},
            })

        self.assertEqual(self.db.get_count(), 10)
        deleted = self.db.prune_history(max_records=5, retention_hours=48)
        self.assertEqual(deleted, 5)
        self.assertEqual(self.db.get_count(), 5)

        # Remaining records should be the latest 5 (from 05 to 09)
        remaining = self.db.get_history(limit=10)
        self.assertEqual(remaining[0]["timestamp"], "2026-10-22T10:05:00Z")

    def test_prune_by_retention_hours(self):
        """Verifies pruning deletes records older than retention_hours."""
        old_time = (datetime.now(timezone.utc) - timedelta(hours=30)).isoformat()
        recent_time = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()

        self.db.insert_metrics({"timestamp": old_time, "cpu": {"total_percent": 5.0}})
        self.db.insert_metrics({"timestamp": recent_time, "cpu": {"total_percent": 10.0}})

        deleted = self.db.prune_history(max_records=100, retention_hours=24)
        self.assertEqual(deleted, 1)
        self.assertEqual(self.db.get_count(), 1)
        history = self.db.get_history(limit=5)
        self.assertEqual(history[0]["timestamp"], recent_time)

    def test_concurrent_readers_and_writers(self):
        """Verifies concurrent writes (metrics, alerts, settings) and reads do not lock or corrupt database."""
        import threading
        errors = []

        def worker_metrics(worker_id):
            try:
                for i in range(25):
                    self.db.insert_metrics({
                        "timestamp": f"2026-10-23T10:{worker_id:02d}:{i:02d}Z",
                        "cpu": {"total_percent": float(i)},
                        "memory": {"percent": 50.0},
                    })
            except Exception as e:
                errors.append(f"worker_metrics_{worker_id}: {e}")

        def worker_alerts():
            try:
                for i in range(15):
                    alert_id = self.db.insert_alert({
                        "alert_type": "cpu_pressure",
                        "severity": "warning",
                        "status": "active",
                        "first_observed_at": "2026-10-23T10:00:00Z",
                        "last_observed_at": "2026-10-23T10:01:00Z",
                        "evidence": {"current_value_percent": 80.0},
                        "explanation": "CPU high",
                    })
                    self.db.update_alert(alert_id, {
                        "status": "recovered",
                        "recovered_at": "2026-10-23T10:02:00Z",
                    })
            except Exception as e:
                errors.append(f"worker_alerts: {e}")

        def worker_settings():
            try:
                for i in range(15):
                    self.db.save_settings("detection_settings", {
                        "cpu": {"warning": 70.0 + (i % 5), "critical": 90.0, "recovery": 60.0}
                    })
                    saved = self.db.get_settings("detection_settings")
                    if not saved:
                        errors.append("worker_settings: retrieved None")
            except Exception as e:
                errors.append(f"worker_settings: {e}")

        def worker_reader():
            try:
                for _ in range(25):
                    _ = self.db.get_history(limit=10)
                    _ = self.db.get_alerts(status="all", limit=10)
                    _ = self.db.get_settings("detection_settings")
            except Exception as e:
                errors.append(f"worker_reader: {e}")

        threads = [
            threading.Thread(target=worker_metrics, args=(1,)),
            threading.Thread(target=worker_metrics, args=(2,)),
            threading.Thread(target=worker_alerts),
            threading.Thread(target=worker_settings),
            threading.Thread(target=worker_reader),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Concurrent database errors encountered: {errors}")
        self.assertEqual(self.db.get_count(), 50)
        self.assertEqual(len(self.db.get_alerts(status="recovered")), 15)
        final_settings = self.db.get_settings("detection_settings")
        self.assertIsNotNone(final_settings)

if __name__ == "__main__":
    unittest.main()
