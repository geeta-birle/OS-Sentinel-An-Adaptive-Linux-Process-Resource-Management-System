import os
import time
import unittest
import tempfile
from unittest.mock import patch, MagicMock
from app.services.background_collector import BackgroundMetricsCollector
from app.storage.database import Database

class BackgroundCollectorTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_bg.db")
        self.collector = BackgroundMetricsCollector()

    def tearDown(self):
        self.collector.stop(timeout=1.0)
        self.temp_dir.cleanup()

    def test_start_and_stop_collector(self):
        config = {
            "ENABLE_BACKGROUND_COLLECTOR": True,
            "DEBUG": False,
            "DB_PATH": self.db_path,
            "METRICS_COLLECTION_INTERVAL": 1,
            "METRICS_RETENTION_MAX_RECORDS": 50,
            "METRICS_RETENTION_HOURS": 1,
        }

        started = self.collector.start(config)
        self.assertTrue(started)
        self.assertTrue(self.collector.is_running())

        # Second start call should be idempotent (no duplicate thread)
        started_again = self.collector.start(config)
        self.assertTrue(started_again)

        # Wait a short moment to allow at least one sample to record
        time.sleep(1.2)
        db = Database(self.db_path)
        self.assertGreater(db.get_count(), 0)

        # Stop collector
        self.collector.stop(timeout=1.5)
        self.assertFalse(self.collector.is_running())

    def test_werkzeug_reloader_guard(self):
        """Verifies that in debug mode, the master reloader process does not launch the collector."""
        config = {
            "ENABLE_BACKGROUND_COLLECTOR": True,
            "DEBUG": True,
            "DB_PATH": self.db_path,
            "METRICS_COLLECTION_INTERVAL": 1,
        }

        # Simulate Werkzeug master process (WERKZEUG_RUN_MAIN is unset)
        with patch.dict(os.environ, {"FLASK_ENV": "development", "WERKZEUG_RUN_MAIN": ""}):
            # Ensure collector is stopped first
            self.collector.stop(timeout=0.5)
            started = self.collector.start(config)
            self.assertFalse(started)
            self.assertFalse(self.collector.is_running())

if __name__ == "__main__":
    unittest.main()
