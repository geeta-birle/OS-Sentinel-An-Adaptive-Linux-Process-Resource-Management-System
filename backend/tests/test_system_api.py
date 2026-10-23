import os
import unittest
import json
import tempfile
from app import create_app
from app.config import Config

class TestConfig(Config):
    TESTING = True
    DEBUG = False
    ENABLE_BACKGROUND_COLLECTOR = False  # Avoid background thread in unit tests
    CORS_ORIGINS = ["http://localhost:5173", "http://testserver"]
    CORS_ALLOW_ALL = False

class SystemApiTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_api.db")

        class CustomConfig(TestConfig):
            DB_PATH = self.db_path

        self.app = create_app(CustomConfig)
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_healthz_endpoint(self):
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data.get("status"), "ok")

    def test_api_health_endpoint(self):
        response = self.client.get("/api/v1/health")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data.get("status"), "healthy")
        self.assertEqual(data.get("service"), "OS Sentinel Backend")
        self.assertIn("timestamp", data)
        self.assertIn("version", data)

    def test_api_readiness_endpoint(self):
        response = self.client.get("/api/v1/health/readiness")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data.get("status"), "ready")
        self.assertIn("checks", data)
        self.assertEqual(data["checks"].get("api"), "ok")
        self.assertEqual(data["checks"].get("system_inspector"), "ok")
        self.assertEqual(data["checks"].get("database"), "ok")

    def test_system_summary_endpoint(self):
        response = self.client.get("/api/v1/system/summary")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)

        # High level envelope
        self.assertEqual(data.get("status"), "online")
        self.assertEqual(data.get("service"), "OS Sentinel Backend")
        self.assertIn("Phase 3", data.get("phase", ""))

        # Host properties (backward-compatible)
        host = data.get("host", {})
        self.assertIn("hostname", host)
        self.assertIn("os", host)
        self.assertIn("cpu_cores_logical", host)
        self.assertGreater(host["cpu_cores_logical"], 0)
        self.assertIn("uptime_seconds", host)

        # Linux environment detection
        linux_env = data.get("linux_environment", {})
        self.assertIn("is_linux", linux_env)
        self.assertIn("is_wsl", linux_env)
        self.assertIn("scope", linux_env)
        self.assertIn("proc_fs_available", linux_env)

        # Live metrics verification (Phase 2 real telemetry)
        metrics = data.get("metrics", {})
        self.assertIn("cpu", metrics)
        self.assertTrue(metrics["cpu"].get("available"))
        self.assertGreaterEqual(metrics["cpu"].get("total_percent"), 0.0)

        self.assertIn("memory", metrics)
        self.assertTrue(metrics["memory"].get("available"))
        self.assertGreater(metrics["memory"].get("total_bytes"), 0)

        self.assertIn("swap", metrics)
        self.assertTrue(metrics["swap"].get("available"))

        self.assertIn("load_average", metrics)
        self.assertIn("supported", metrics["load_average"])

        phase_notes = data.get("phase_notes", {})
        self.assertTrue(phase_notes.get("live_metrics_collected"))

    def test_system_history_empty_and_populated(self):
        # Empty initial
        resp = self.client.get("/api/v1/system/history")
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertEqual(data.get("count"), 0)
        self.assertEqual(data.get("history"), [])

        # Trigger summary which creates and records if we populate SQLite
        from app.storage.database import Database
        db = Database(self.db_path)
        db.insert_metrics({
            "timestamp": "2026-10-22T12:00:00Z",
            "cpu": {"total_percent": 12.0},
            "memory": {"percent": 55.0}
        })

        resp2 = self.client.get("/api/v1/system/history?limit=10")
        self.assertEqual(resp2.status_code, 200)
        data2 = json.loads(resp2.data)
        self.assertEqual(data2.get("count"), 1)
        self.assertEqual(data2["history"][0]["cpu"]["total_percent"], 12.0)

    def test_system_history_invalid_parameters(self):
        # Invalid limit string
        r1 = self.client.get("/api/v1/system/history?limit=abc")
        self.assertEqual(r1.status_code, 400)
        d1 = json.loads(r1.data)
        self.assertEqual(d1.get("code"), "INVALID_PARAMETER")

        # Invalid limit out of bounds
        r2 = self.client.get("/api/v1/system/history?limit=999")
        self.assertEqual(r2.status_code, 400)

        # Invalid since format
        r3 = self.client.get("/api/v1/system/history?since=invalid-date")
        self.assertEqual(r3.status_code, 400)
        d3 = json.loads(r3.data)
        self.assertEqual(d3.get("code"), "INVALID_PARAMETER")

    def test_processes_list_endpoint(self):
        resp = self.client.get("/api/v1/processes?limit=5&sort_by=cpu_percent&order=desc")
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertIn("processes", data)
        self.assertLessEqual(data.get("returned_count"), 5)
        self.assertEqual(data.get("sort_by"), "cpu_percent")
        self.assertEqual(data.get("order"), "desc")

    def test_processes_invalid_parameters(self):
        # Invalid sort_by
        r1 = self.client.get("/api/v1/processes?sort_by=unsupported_col")
        self.assertEqual(r1.status_code, 400)
        d1 = json.loads(r1.data)
        self.assertEqual(d1.get("code"), "INVALID_PARAMETER")

        # Invalid order
        r2 = self.client.get("/api/v1/processes?order=diagonal")
        self.assertEqual(r2.status_code, 400)

        # Invalid limit
        r3 = self.client.get("/api/v1/processes?limit=-5")
        self.assertEqual(r3.status_code, 400)

    def test_process_detail_current_pid(self):
        current_pid = os.getpid()
        resp = self.client.get(f"/api/v1/processes/{current_pid}")
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertEqual(data.get("pid"), current_pid)
        self.assertIn("name", data)
        self.assertIn("status", data)

    def test_process_detail_non_existent_pid(self):
        resp = self.client.get("/api/v1/processes/99999999")
        self.assertEqual(resp.status_code, 404)
        data = json.loads(resp.data)
        self.assertEqual(data.get("code"), "PROCESS_NOT_FOUND")

    def test_cors_headers(self):
        origin = "http://localhost:5173"
        response = self.client.get("/api/v1/health", headers={"Origin": origin})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), origin)

    def test_cors_preflight_options(self):
        origin = "http://localhost:5173"
        response = self.client.open(
            "/api/v1/processes",
            method="OPTIONS",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET"
            }
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), origin)
        self.assertIn("GET", response.headers.get("Access-Control-Allow-Methods", ""))

    def test_cors_unauthorized_origin_rejected(self):
        unauthorized_origin = "http://malicious-site.com"
        response = self.client.get("/api/v1/health", headers={"Origin": unauthorized_origin})
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.headers.get("Access-Control-Allow-Origin"))

    def test_default_security_configuration(self):
        """Verifies default production configuration enforces secure defaults: loopback host, debug disabled, strict CORS."""
        from app.config import Config as BaseConfig
        self.assertFalse(BaseConfig.DEBUG, "DEBUG must default to False")
        self.assertEqual(BaseConfig.HOST, "127.0.0.1", "HOST must bind to loopback 127.0.0.1 by default")
        self.assertFalse(BaseConfig.CORS_ALLOW_ALL, "CORS_ALLOW_ALL must default to False")
        self.assertEqual(BaseConfig.ENV, "production", "ENV must default to production")

    def test_alerts_endpoint(self):
        # Empty alerts
        resp = self.client.get("/api/v1/alerts")
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertEqual(data.get("count"), 0)
        self.assertEqual(data.get("alerts"), [])

        # Insert active alert directly
        from app.storage.database import Database
        db = Database(self.db_path)
        alert_id = db.insert_alert({
            "alert_type": "cpu_pressure",
            "severity": "critical",
            "status": "active",
            "first_observed_at": "2026-10-22T10:00:00Z",
            "last_observed_at": "2026-10-22T10:01:00Z",
            "evidence": {"current_value_percent": 95.0},
            "explanation": "Test critical alert"
        })
        self.assertGreater(alert_id, 0)

        # Query all
        r2 = self.client.get("/api/v1/alerts?status=all")
        self.assertEqual(r2.status_code, 200)
        d2 = json.loads(r2.data)
        self.assertEqual(d2.get("count"), 1)
        self.assertEqual(d2["alerts"][0]["alert_type"], "cpu_pressure")

        # Query filtered by active
        r3 = self.client.get("/api/v1/alerts?status=active&severity=critical")
        self.assertEqual(r3.status_code, 200)
        d3 = json.loads(r3.data)
        self.assertEqual(d3.get("count"), 1)

        # Query filtered by recovered (none yet)
        r4 = self.client.get("/api/v1/alerts?status=recovered")
        self.assertEqual(r4.status_code, 200)
        d4 = json.loads(r4.data)
        self.assertEqual(d4.get("count"), 0)

    def test_alerts_invalid_parameters(self):
        # Invalid status
        r1 = self.client.get("/api/v1/alerts?status=invalid_status")
        self.assertEqual(r1.status_code, 400)
        d1 = json.loads(r1.data)
        self.assertEqual(d1.get("code"), "INVALID_PARAMETER")

        # Invalid severity
        r2 = self.client.get("/api/v1/alerts?severity=urgent")
        self.assertEqual(r2.status_code, 400)
        d2 = json.loads(r2.data)
        self.assertEqual(d2.get("code"), "INVALID_PARAMETER")

        # Invalid limit
        r3 = self.client.get("/api/v1/alerts?limit=0")
        self.assertEqual(r3.status_code, 400)

    def test_recommendations_endpoint(self):
        resp = self.client.get("/api/v1/recommendations")
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertIn("recommendations", data)
        self.assertGreater(data.get("count"), 0)
        # Verify schema
        first_rec = data["recommendations"][0]
        self.assertIn("title", first_rec)
        self.assertIn("reasoning", first_rec)
        self.assertIn("uncertainty_note", first_rec)
        self.assertIn("suggested_investigations", first_rec)

    def test_settings_endpoints(self):
        # GET settings
        resp = self.client.get("/api/v1/settings")
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertIn("cpu", data)
        self.assertIn("memory", data)
        self.assertIn("swap", data)
        self.assertIn("load", data)

        # PUT valid settings
        valid_update = {
            "cpu": {"warning": 70.0, "critical": 88.0, "recovery": 60.0, "persistence_samples": 4, "cooldown_seconds": 90},
            "memory": {"warning": 75.0, "critical": 90.0, "recovery": 65.0, "persistence_samples": 3, "cooldown_seconds": 60},
            "swap": {"warning": 40.0, "critical": 70.0, "recovery": 30.0, "persistence_samples": 3, "cooldown_seconds": 60},
            "load": {"warning_ratio": 1.8, "critical_ratio": 2.8, "recovery_ratio": 1.2, "persistence_samples": 3, "cooldown_seconds": 60}
        }
        r_put = self.client.put("/api/v1/settings", json=valid_update)
        self.assertEqual(r_put.status_code, 200)
        d_put = json.loads(r_put.data)
        self.assertEqual(d_put["settings"]["cpu"]["critical"], 88.0)
        self.assertEqual(d_put["settings"]["cpu"]["persistence_samples"], 4)

        # Verify persisted via subsequent GET
        r_verify = self.client.get("/api/v1/settings")
        d_verify = json.loads(r_verify.data)
        self.assertEqual(d_verify["cpu"]["critical"], 88.0)

        # PUT invalid settings (warning >= critical)
        invalid_update = {
            "cpu": {"warning": 95.0, "critical": 80.0, "recovery": 70.0}
        }
        r_err = self.client.put("/api/v1/settings", json=invalid_update)
        self.assertEqual(r_err.status_code, 400)
        d_err = json.loads(r_err.data)
        self.assertEqual(d_err.get("code"), "INVALID_SETTINGS")

if __name__ == "__main__":
    unittest.main()
