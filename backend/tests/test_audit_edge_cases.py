import os
import math
import unittest
import tempfile
from unittest.mock import patch, MagicMock
from app.storage.database import Database
from app.models.detection_settings import DetectionSettings, ResourceThreshold, LoadThreshold
from app.services.detection_service import DetectionService
from app.services.metrics_collector import MetricsCollector
from app.services.process_service import ProcessService

class AuditEdgeCasesTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_audit.db")
        self.db = Database(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _make_snapshot(self, cpu_val=20.0, cpu_available=True):
        return {
            "timestamp": "2026-10-22T10:00:00Z",
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

    def test_settings_validation_rejects_nan_and_inf(self):
        """Verifies DetectionSettings rejects NaN and infinite values."""
        # NaN in CPU warning
        payload = {
            "cpu": {"warning": float("nan"), "critical": 90.0, "recovery": 70.0}
        }
        settings, err = DetectionSettings.from_dict(payload)
        self.assertIsNotNone(err, "Expected error when passing NaN threshold")

        # Inf in Memory critical
        payload_inf = {
            "memory": {"warning": 80.0, "critical": float("inf"), "recovery": 75.0}
        }
        settings_inf, err_inf = DetectionSettings.from_dict(payload_inf)
        self.assertIsNotNone(err_inf, "Expected error when passing Infinity threshold")

    def test_settings_validation_rejects_boolean_integers(self):
        """Verifies DetectionSettings rejects boolean True/False for persistence_samples."""
        payload_bool = {
            "cpu": {
                "warning": 75.0,
                "critical": 90.0,
                "recovery": 70.0,
                "persistence_samples": True
            }
        }
        settings, err = DetectionSettings.from_dict(payload_bool)
        self.assertIsNotNone(err, "Expected error when passing boolean True for persistence_samples")

    def test_live_detection_reloads_persisted_settings(self):
        """Verifies DetectionService reloads dynamic threshold changes made to the database."""
        # 1. Save custom threshold in DB: warning 50.0, critical 60.0, recovery 40.0
        custom_settings = DetectionSettings(
            cpu=ResourceThreshold(warning=50.0, critical=60.0, recovery=40.0, persistence_samples=2, cooldown_seconds=30),
            memory=ResourceThreshold(warning=75.0, critical=90.0, recovery=65.0, persistence_samples=2, cooldown_seconds=30),
            swap=ResourceThreshold(warning=40.0, critical=70.0, recovery=30.0, persistence_samples=2, cooldown_seconds=30),
            load=LoadThreshold(warning_ratio=1.5, critical_ratio=2.5, recovery_ratio=1.0, persistence_samples=2, cooldown_seconds=30)
        )
        self.db.save_settings("detection_settings", custom_settings.to_dict())

        # 2. Instantiate DetectionService without explicit settings (simulates background collector)
        detector = DetectionService(self.db)
        self.assertEqual(detector.settings.cpu.warning, 50.0, "Detector should load persisted warning threshold from DB on init")

        # 3. Feed 55% CPU (above custom warning 50%, below default 75%)
        detector.evaluate_snapshot(self._make_snapshot(cpu_val=55.0), current_time=1000.0)
        alerts = detector.evaluate_snapshot(self._make_snapshot(cpu_val=55.0), current_time=1005.0)
        self.assertEqual(len(alerts), 1, "Expected warning alert at 55% with persisted 50% threshold")

    def test_recovery_sequence_interrupted_by_missing_sample(self):
        """Verifies that an intervening missing sample resets recovery streak and prevents premature recovery."""
        detector = DetectionService(
            self.db,
            DetectionSettings(
                cpu=ResourceThreshold(warning=70.0, critical=85.0, recovery=60.0, persistence_samples=2, cooldown_seconds=30)
            )
        )
        t0 = 1000.0
        # Trigger active alert (2 critical samples)
        detector.evaluate_snapshot(self._make_snapshot(cpu_val=90.0), current_time=t0)
        detector.evaluate_snapshot(self._make_snapshot(cpu_val=90.0), current_time=t0 + 5)
        self.assertEqual(len(self.db.get_alerts(status="active")), 1)

        # Drop 1: Recovery sample 1 (below recovery 60%)
        detector.evaluate_snapshot(self._make_snapshot(cpu_val=50.0), current_time=t0 + 10)
        self.assertEqual(len(self.db.get_alerts(status="active")), 1)

        # Drop 2: Missing sample! (Must interrupt and reset recovery counter)
        detector.evaluate_snapshot(self._make_snapshot(cpu_available=False), current_time=t0 + 15)
        self.assertEqual(len(self.db.get_alerts(status="active")), 1)

        # Drop 3: Another recovery sample (sample 1 of new streak)
        detector.evaluate_snapshot(self._make_snapshot(cpu_val=50.0), current_time=t0 + 20)
        # Alert must STILL be active because streak was reset by the missing sample!
        self.assertEqual(len(self.db.get_alerts(status="active")), 1, "Alert must remain active after missing sample interrupted recovery")

        # Drop 4: Second recovery sample (sample 2 of new streak)
        detector.evaluate_snapshot(self._make_snapshot(cpu_val=50.0), current_time=t0 + 25)
        # Now it should be recovered
        self.assertEqual(len(self.db.get_alerts(status="active")), 0)
        self.assertEqual(len(self.db.get_alerts(status="recovered")), 1)

    def test_non_finite_cpu_sample_tolerance(self):
        """Verifies non-finite CPU readings (NaN/Inf) do not trigger false alerts or crash."""
        detector = DetectionService(self.db)
        snapshot = self._make_snapshot(cpu_val=float("nan"))
        alerts = detector.evaluate_snapshot(snapshot, current_time=1000.0)
        self.assertEqual(len(alerts), 0)
        self.assertEqual(len(self.db.get_alerts()), 0)

    def test_process_detail_unexpected_exception_tolerance(self):
        """Verifies ProcessService.get_process_detail survives unexpected exceptions reading cmdline/exe."""
        mock_proc = MagicMock()
        mock_proc.pid = 1234
        mock_proc.name.return_value = "worker"
        mock_proc.status.return_value = "running"
        mock_proc.exe.side_effect = RuntimeError("Kernel lock contention")
        mock_proc.cmdline.side_effect = UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte")
        mock_proc.username.return_value = "user"
        mock_proc.create_time.return_value = 1700000000.0
        mock_proc.cpu_percent.return_value = 5.0
        mock_proc.memory_info.return_value = MagicMock(rss=1024, vms=2048)
        mock_proc.memory_percent.return_value = 1.0
        mock_proc.ppid.return_value = 1
        mock_proc.num_threads.return_value = 2
        mock_proc.nice.return_value = 0

        with patch("psutil.pid_exists", return_value=True), patch("psutil.Process", return_value=mock_proc):
            detail = ProcessService.get_process_detail(1234)
            self.assertEqual(detail["pid"], 1234)
            self.assertIsNone(detail["exe"])
            self.assertEqual(detail["cmdline"], [])

    def test_cpu_unprimed_returns_unavailable(self):
        """Verifies that an unprimed CPU collector marks metric unavailable rather than reporting 0%."""
        collector = MetricsCollector()
        collector._cpu_primed = False
        with patch("psutil.cpu_percent", return_value=0.0):
            cpu = collector.collect_cpu_metrics()
            self.assertFalse(cpu["available"])
            self.assertIsNone(cpu["total_percent"])

    def test_settings_change_while_detector_running_preserves_state(self):
        """Verifies dynamic settings update on running detector preserves alert state and applies new threshold."""
        detector = DetectionService(
            self.db,
            DetectionSettings(
                cpu=ResourceThreshold(warning=70.0, critical=90.0, recovery=60.0, persistence_samples=2, cooldown_seconds=30)
            )
        )
        t0 = 1000.0
        # Trigger warning alert with 2 samples at 75%
        detector.evaluate_snapshot(self._make_snapshot(cpu_val=75.0), current_time=t0)
        detector.evaluate_snapshot(self._make_snapshot(cpu_val=75.0), current_time=t0 + 5)
        active_alerts = self.db.get_alerts(status="active")
        self.assertEqual(len(active_alerts), 1)
        self.assertEqual(active_alerts[0]["severity"], "warning")
        orig_alert_id = active_alerts[0]["id"]

        # Dynamically lower critical threshold to 80.0 while running
        updated_settings = DetectionSettings(
            cpu=ResourceThreshold(warning=70.0, critical=80.0, recovery=60.0, persistence_samples=2, cooldown_seconds=30)
        )
        detector.update_settings(updated_settings)

        # Alert state must not be wiped
        self.assertEqual(detector._state["cpu_pressure"]["active_alert_id"], orig_alert_id)

        # Feed sample at 82% (now critical under updated 80% threshold)
        detector.evaluate_snapshot(self._make_snapshot(cpu_val=82.0), current_time=t0 + 10)
        alerts_now = self.db.get_alerts(status="active")
        self.assertEqual(len(alerts_now), 1)
        self.assertEqual(alerts_now[0]["id"], orig_alert_id, "Alert ID must persist, not create duplicate")
        self.assertEqual(alerts_now[0]["severity"], "critical", "Severity should escalate under new settings")

    def test_settings_refresh_database_error_safe_behavior(self):
        """Verifies DetectionService safely handles database errors during settings refresh without crashing or resetting state."""
        import sqlite3
        detector = DetectionService(
            self.db,
            DetectionSettings(
                cpu=ResourceThreshold(warning=70.0, critical=90.0, recovery=60.0, persistence_samples=2, cooldown_seconds=30)
            )
        )
        t0 = 1000.0
        # Trigger an active alert
        detector.evaluate_snapshot(self._make_snapshot(cpu_val=75.0), current_time=t0)
        detector.evaluate_snapshot(self._make_snapshot(cpu_val=75.0), current_time=t0 + 5)
        self.assertEqual(len(self.db.get_alerts(status="active")), 1)

        # Simulate transient database lock/error on get_settings
        with patch.object(self.db, "get_settings", side_effect=sqlite3.OperationalError("database is locked")):
            # evaluate_snapshot should not raise, should retain current settings and preserve active alert state
            alerts = detector.evaluate_snapshot(self._make_snapshot(cpu_val=75.0), current_time=t0 + 10)
            self.assertEqual(detector.settings.cpu.warning, 70.0)
            self.assertIsNotNone(detector._state["cpu_pressure"]["active_alert_id"])
            self.assertEqual(len(self.db.get_alerts(status="active")), 1)

    def test_warning_to_critical_to_recovery_lifecycle(self):
        """Verifies deterministic warning -> critical -> recovery transition sequence with clock injection."""
        detector = DetectionService(
            self.db,
            DetectionSettings(
                cpu=ResourceThreshold(warning=70.0, critical=85.0, recovery=55.0, persistence_samples=2, cooldown_seconds=30)
            )
        )
        t0 = 2000.0

        # Phase 1: Warning breach
        detector.evaluate_snapshot(self._make_snapshot(cpu_val=72.0), current_time=t0)
        self.assertEqual(len(self.db.get_alerts(status="active")), 0) # persistence = 2
        detector.evaluate_snapshot(self._make_snapshot(cpu_val=72.0), current_time=t0 + 5)
        alerts = self.db.get_alerts(status="active")
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["severity"], "warning")
        alert_id = alerts[0]["id"]

        # Phase 2: Escalate to Critical
        detector.evaluate_snapshot(self._make_snapshot(cpu_val=90.0), current_time=t0 + 10)
        detector.evaluate_snapshot(self._make_snapshot(cpu_val=92.0), current_time=t0 + 15)
        alerts = self.db.get_alerts(status="active")
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["id"], alert_id)
        self.assertEqual(alerts[0]["severity"], "critical")

        # Phase 3: Recovery
        detector.evaluate_snapshot(self._make_snapshot(cpu_val=50.0), current_time=t0 + 20)
        self.assertEqual(len(self.db.get_alerts(status="active")), 1) # persistence = 2
        detector.evaluate_snapshot(self._make_snapshot(cpu_val=48.0), current_time=t0 + 25)
        self.assertEqual(len(self.db.get_alerts(status="active")), 0)
        recovered = self.db.get_alerts(status="recovered")
        self.assertEqual(len(recovered), 1)
        self.assertEqual(recovered[0]["id"], alert_id)
        self.assertIsNotNone(recovered[0]["recovered_at"])

if __name__ == "__main__":
    unittest.main()
