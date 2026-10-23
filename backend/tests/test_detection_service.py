import os
import unittest
import tempfile
from app.storage.database import Database
from app.models.detection_settings import DetectionSettings, ResourceThreshold, LoadThreshold
from app.services.detection_service import DetectionService

class DetectionServiceTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_detection.db")
        self.db = Database(self.db_path)
        # Use small persistence window (2 samples) and cooldown (30s) for testing
        self.settings = DetectionSettings(
            cpu=ResourceThreshold(warning=70.0, critical=85.0, recovery=60.0, persistence_samples=2, cooldown_seconds=30),
            memory=ResourceThreshold(warning=75.0, critical=90.0, recovery=65.0, persistence_samples=2, cooldown_seconds=30),
            swap=ResourceThreshold(warning=40.0, critical=70.0, recovery=30.0, persistence_samples=2, cooldown_seconds=30),
            load=LoadThreshold(warning_ratio=1.5, critical_ratio=2.5, recovery_ratio=1.0, persistence_samples=2, cooldown_seconds=30)
        )
        self.detector = DetectionService(self.db, self.settings)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _make_snapshot(self, cpu_val=20.0, mem_val=30.0, swap_val=0.0, load_1m=0.5, cores=4):
        return {
            "timestamp": "2026-10-22T10:00:00Z",
            "host": {"cpu_cores_logical": cores},
            "cpu": {
                "available": True,
                "total_percent": cpu_val,
                "logical_cores": cores,
                "per_core_percent": [cpu_val] * cores,
            },
            "memory": {
                "available": True,
                "percent": mem_val,
                "used_bytes": int(mem_val * 1000000),
                "total_bytes": 100000000,
                "available_bytes": int((100 - mem_val) * 1000000),
            },
            "swap": {
                "available": True,
                "swap_configured": True,
                "percent": swap_val,
                "used_bytes": int(swap_val * 10000),
                "total_bytes": 1000000,
            },
            "load_average": {
                "supported": True,
                "load_1m": load_1m,
                "load_5m": load_1m,
                "load_15m": load_1m,
            }
        }

    def test_transient_spike_suppression(self):
        """Verifies that an isolated 1-sample spike does NOT trigger an alert."""
        t0 = 1000.0
        # Sample 1: Normal
        self.detector.evaluate_snapshot(self._make_snapshot(cpu_val=15.0), current_time=t0)
        self.assertEqual(len(self.db.get_alerts()), 0)

        # Sample 2: Isolated spike to 95% CPU
        self.detector.evaluate_snapshot(self._make_snapshot(cpu_val=95.0), current_time=t0 + 5)
        # Persistence is 2 samples; 1 sample must NOT trigger
        self.assertEqual(len(self.db.get_alerts()), 0)

        # Sample 3: Returns to normal
        self.detector.evaluate_snapshot(self._make_snapshot(cpu_val=25.0), current_time=t0 + 10)
        self.assertEqual(len(self.db.get_alerts()), 0)

    def test_sustained_pressure_triggers_critical_alert(self):
        """Verifies sustained breach across persistence window triggers a critical alert."""
        t0 = 1000.0
        # Sample 1: 90% CPU (above critical 85%)
        self.detector.evaluate_snapshot(self._make_snapshot(cpu_val=90.0), current_time=t0)
        self.assertEqual(len(self.db.get_alerts()), 0)

        # Sample 2: 92% CPU (second consecutive critical sample)
        alerts = self.detector.evaluate_snapshot(self._make_snapshot(cpu_val=92.0), current_time=t0 + 5)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["alert_type"], "cpu_pressure")
        self.assertEqual(alerts[0]["severity"], "critical")
        self.assertEqual(alerts[0]["status"], "active")

        # Verify persisted in SQLite
        db_alerts = self.db.get_alerts(status="active")
        self.assertEqual(len(db_alerts), 1)
        self.assertEqual(db_alerts[0]["alert_type"], "cpu_pressure")
        self.assertIn("92.0", db_alerts[0]["explanation"])

    def test_repeated_samples_update_active_alert(self):
        """Verifies ongoing pressure updates the existing active alert without creating duplicate rows."""
        t0 = 1000.0
        self.detector.evaluate_snapshot(self._make_snapshot(cpu_val=90.0), current_time=t0)
        self.detector.evaluate_snapshot(self._make_snapshot(cpu_val=92.0), current_time=t0 + 5)
        self.assertEqual(len(self.db.get_alerts()), 1)

        # Sample 3 & 4: pressure continues
        self.detector.evaluate_snapshot(self._make_snapshot(cpu_val=88.0), current_time=t0 + 10)
        self.detector.evaluate_snapshot(self._make_snapshot(cpu_val=89.0), current_time=t0 + 15)

        # Total rows in alerts table must still be exactly 1
        all_alerts = self.db.get_alerts()
        self.assertEqual(len(all_alerts), 1)
        self.assertEqual(all_alerts[0]["status"], "active")
        self.assertIn("89.0", all_alerts[0]["explanation"])

    def test_recovery_transition(self):
        """Verifies alert transitions to 'recovered' when metric drops below recovery threshold."""
        t0 = 1000.0
        # Trigger active alert
        self.detector.evaluate_snapshot(self._make_snapshot(cpu_val=90.0), current_time=t0)
        self.detector.evaluate_snapshot(self._make_snapshot(cpu_val=92.0), current_time=t0 + 5)
        self.assertEqual(len(self.db.get_alerts(status="active")), 1)

        # Recovery threshold is 60.0, persistence is 2
        # Drop 1: 50% CPU
        self.detector.evaluate_snapshot(self._make_snapshot(cpu_val=50.0), current_time=t0 + 10)
        self.assertEqual(len(self.db.get_alerts(status="active")), 1)

        # Drop 2: 45% CPU (second consecutive recovery sample)
        self.detector.evaluate_snapshot(self._make_snapshot(cpu_val=45.0), current_time=t0 + 15)
        # Should now be recovered
        active = self.db.get_alerts(status="active")
        self.assertEqual(len(active), 0)

        recovered = self.db.get_alerts(status="recovered")
        self.assertEqual(len(recovered), 1)
        self.assertIsNotNone(recovered[0]["recovered_at"])

    def test_cooldown_suppression(self):
        """Verifies that after an alert recovers, re-breaches within cooldown window are suppressed."""
        t0 = 1000.0
        # Trigger alert
        self.detector.evaluate_snapshot(self._make_snapshot(cpu_val=90.0), current_time=t0)
        self.detector.evaluate_snapshot(self._make_snapshot(cpu_val=92.0), current_time=t0 + 5)
        # Recover
        self.detector.evaluate_snapshot(self._make_snapshot(cpu_val=40.0), current_time=t0 + 10)
        self.detector.evaluate_snapshot(self._make_snapshot(cpu_val=40.0), current_time=t0 + 15)
        self.assertEqual(len(self.db.get_alerts(status="active")), 0)

        # Now re-breach at t0 + 20s (cooldown is 30s from trigger at t0+5 -> cooldown expires at t0+35s)
        self.detector.evaluate_snapshot(self._make_snapshot(cpu_val=95.0), current_time=t0 + 20)
        self.detector.evaluate_snapshot(self._make_snapshot(cpu_val=95.0), current_time=t0 + 25)
        # Must be suppressed by cooldown!
        self.assertEqual(len(self.db.get_alerts(status="active")), 0)

        # Advance past cooldown to t0 + 40s and re-breach
        self.detector.evaluate_snapshot(self._make_snapshot(cpu_val=95.0), current_time=t0 + 40)
        self.detector.evaluate_snapshot(self._make_snapshot(cpu_val=95.0), current_time=t0 + 45)
        # Now a second alert should be triggered!
        active = self.db.get_alerts(status="active")
        self.assertEqual(len(active), 1)
        self.assertEqual(len(self.db.get_alerts()), 2)

    def test_missing_and_unsupported_metrics_tolerance(self):
        """Verifies missing metrics (e.g. unsupported load average or unconfigured swap) do not cause false alerts."""
        t0 = 1000.0
        # Snapshot with missing CPU and unsupported load average
        snapshot = {
            "timestamp": "2026-10-22T10:00:00Z",
            "cpu": {"available": False, "total_percent": None},
            "memory": {"available": True, "percent": 40.0},
            "swap": {"available": True, "swap_configured": False, "total_bytes": 0},
            "load_average": {"supported": False, "load_1m": None}
        }
        # Run 5 times
        for i in range(5):
            self.detector.evaluate_snapshot(snapshot, current_time=t0 + i*5)

        # Zero alerts should be generated
        self.assertEqual(len(self.db.get_alerts()), 0)

if __name__ == "__main__":
    unittest.main()
