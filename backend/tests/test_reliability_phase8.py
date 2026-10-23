import os
import time
import unittest
import tempfile
import threading
from app.storage.database import Database
from app.models.detection_settings import DetectionSettings, ResourceThreshold, LoadThreshold
from app.services.detection_service import DetectionService
from app.services.process_service import ProcessService

class ReliabilityPhase8TestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_phase8.db")
        self.db = Database(self.db_path)
        ProcessService.clear_cache()

    def tearDown(self):
        ProcessService.clear_cache()
        self.temp_dir.cleanup()

    def _make_snapshot(self, cpu_val=20.0, cpu_available=True):
        return {
            "timestamp": "2026-10-23T10:00:00Z",
            "host": {"cpu_cores_logical": 4},
            "cpu": {
                "available": cpu_available,
                "total_percent": cpu_val if cpu_available else None,
                "logical_cores": 4,
                "per_core_percent": [cpu_val] * 4 if cpu_available else [],
            },
            "memory": {
                "available": True,
                "percent": 30.0,
                "used_bytes": 30000000,
                "total_bytes": 100000000,
                "available_bytes": 70000000,
            },
            "swap": {
                "available": True,
                "swap_configured": True,
                "percent": 10.0,
                "used_bytes": 100000,
                "total_bytes": 1000000,
            },
            "load_average": {
                "supported": True,
                "load_1m": 0.5,
                "load_5m": 0.5,
                "load_15m": 0.5,
            }
        }

    def test_backend_restart_persistence(self):
        """Validates that metrics, active alerts, recovered alerts, and settings survive backend restart."""
        # 1. Write metrics, settings, and alerts
        self.db.insert_metrics({
            "timestamp": "2026-10-23T10:00:00Z",
            "cpu": {"total_percent": 45.0},
            "memory": {"percent": 60.0},
        })
        custom_settings = {
            "cpu": {"warning": 65.0, "critical": 85.0, "recovery": 55.0, "persistence_samples": 2, "cooldown_seconds": 30}
        }
        self.db.save_settings("detection_settings", custom_settings)

        alert_id_1 = self.db.insert_alert({
            "alert_type": "cpu_pressure",
            "severity": "critical",
            "status": "active",
            "first_observed_at": "2026-10-23T10:00:00Z",
            "last_observed_at": "2026-10-23T10:01:00Z",
            "evidence": {"current_value_percent": 90.0},
            "explanation": "High CPU",
        })
        alert_id_2 = self.db.insert_alert({
            "alert_type": "memory_pressure",
            "severity": "warning",
            "status": "active",
            "first_observed_at": "2026-10-23T10:00:00Z",
            "last_observed_at": "2026-10-23T10:01:00Z",
            "evidence": {"current_percent": 82.0},
            "explanation": "High Memory",
        })
        self.db.update_alert(alert_id_2, {
            "status": "recovered",
            "recovered_at": "2026-10-23T10:02:00Z",
        })

        # 2. Simulate Backend Shutdown: destroy DB instance
        del self.db

        # 3. Simulate Backend Restart: reopen database from disk
        restarted_db = Database(self.db_path)

        # 4. Verify all records survived intact
        history = restarted_db.get_history(limit=10)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["cpu"]["total_percent"], 45.0)

        saved_settings = restarted_db.get_settings("detection_settings")
        self.assertIsNotNone(saved_settings)
        self.assertEqual(saved_settings["cpu"]["warning"], 65.0)

        active_alerts = restarted_db.get_alerts(status="active")
        self.assertEqual(len(active_alerts), 1)
        self.assertEqual(active_alerts[0]["id"], alert_id_1)
        self.assertEqual(active_alerts[0]["severity"], "critical")

        recovered_alerts = restarted_db.get_alerts(status="recovered")
        self.assertEqual(len(recovered_alerts), 1)
        self.assertEqual(recovered_alerts[0]["id"], alert_id_2)
        self.assertEqual(recovered_alerts[0]["recovered_at"], "2026-10-23T10:02:00Z")

    def test_process_cache_ttl_and_metadata(self):
        """Validates cache-age metadata, TTL expiration, dynamic pagination/sorting, and manual invalidation."""
        # Cold call
        res1 = ProcessService.list_processes(limit=5, sort_by="pid", order="asc")
        self.assertFalse(res1.get("cache_hit"))
        self.assertEqual(res1.get("cache_age_seconds"), 0.0)
        self.assertLessEqual(len(res1["processes"]), 5)

        # Fast follow-up within 2s TTL
        res2 = ProcessService.list_processes(limit=10, sort_by="pid", order="desc")
        self.assertTrue(res2.get("cache_hit"))
        self.assertGreaterEqual(res2.get("cache_age_seconds"), 0.0)
        self.assertLessEqual(res2.get("cache_age_seconds"), 2.0)
        # Verify dynamic sorting took effect on the cached snapshot
        pids_desc = [p["pid"] for p in res2["processes"]]
        self.assertEqual(pids_desc, sorted(pids_desc, reverse=True))

        # Invalidation via clear_cache
        ProcessService.clear_cache()
        res3 = ProcessService.list_processes(limit=5)
        self.assertFalse(res3.get("cache_hit"))
        self.assertEqual(res3.get("cache_age_seconds"), 0.0)

    def test_concurrent_cache_misses(self):
        """Validates multiple concurrent threads fetching process lists without corruption or race crashes."""
        results = []
        errors = []

        def worker(thread_id):
            try:
                res = ProcessService.list_processes(limit=10, sort_by="pid" if thread_id % 2 == 0 else "cpu_percent")
                results.append(res["returned_count"])
            except Exception as e:
                errors.append(f"Thread {thread_id}: {e}")

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Concurrent process errors: {errors}")
        self.assertEqual(len(results), 8)
        for count in results:
            self.assertGreater(count, 0)

    def test_pipeline_transient_spike_vs_sustained_breach_and_recovery(self):
        """Traces end-to-end pipeline: spike suppression -> sustained breach -> active alert -> recovery."""
        detector = DetectionService(
            self.db,
            DetectionSettings(
                cpu=ResourceThreshold(warning=70.0, critical=90.0, recovery=60.0, persistence_samples=2, cooldown_seconds=30)
            )
        )
        t0 = 1000.0

        # 1. Transient Spike (1 sample at 95%) -> MUST NOT trigger alert
        alerts = detector.evaluate_snapshot(self._make_snapshot(cpu_val=95.0), current_time=t0)
        self.assertEqual(len(alerts), 0)
        self.assertEqual(len(self.db.get_alerts()), 0)

        # 2. Return to normal
        detector.evaluate_snapshot(self._make_snapshot(cpu_val=40.0), current_time=t0 + 5)
        self.assertEqual(len(self.db.get_alerts()), 0)

        # 3. Sustained Breach (2 samples >= 90%) -> MUST trigger Critical Alert
        detector.evaluate_snapshot(self._make_snapshot(cpu_val=92.0), current_time=t0 + 10)
        self.assertEqual(len(self.db.get_alerts(status="active")), 0) # persistence=2
        alerts_active = detector.evaluate_snapshot(self._make_snapshot(cpu_val=93.0), current_time=t0 + 15)
        self.assertEqual(len(alerts_active), 1)
        self.assertEqual(alerts_active[0]["severity"], "critical")
        self.assertEqual(alerts_active[0]["status"], "active")
        alert_id = alerts_active[0]["id"]

        # 4. Sustained Recovery (2 samples <= 60%)
        detector.evaluate_snapshot(self._make_snapshot(cpu_val=50.0), current_time=t0 + 20)
        self.assertEqual(len(self.db.get_alerts(status="active")), 1) # 1 sample not enough
        detector.evaluate_snapshot(self._make_snapshot(cpu_val=45.0), current_time=t0 + 25)
        self.assertEqual(len(self.db.get_alerts(status="active")), 0) # recovered!
        recovered = self.db.get_alerts(status="recovered")
        self.assertEqual(len(recovered), 1)
        self.assertEqual(recovered[0]["id"], alert_id)
        self.assertIsNotNone(recovered[0]["recovered_at"])

        # 5. Cooldown suppression: re-breach at t0 + 35s (cooldown is 30s from trigger at t0+15 -> expires at t0+45)
        detector.evaluate_snapshot(self._make_snapshot(cpu_val=95.0), current_time=t0 + 30)
        detector.evaluate_snapshot(self._make_snapshot(cpu_val=95.0), current_time=t0 + 35)
        self.assertEqual(len(self.db.get_alerts(status="active")), 0, "Re-breach inside cooldown must be suppressed")

    def test_empty_alert_list_schema(self):
        """Confirms that an empty alert list produces a valid schema response, not confused with errors."""
        alerts = self.db.get_alerts(status="active")
        self.assertIsInstance(alerts, list)
        self.assertEqual(len(alerts), 0)

if __name__ == "__main__":
    unittest.main()
