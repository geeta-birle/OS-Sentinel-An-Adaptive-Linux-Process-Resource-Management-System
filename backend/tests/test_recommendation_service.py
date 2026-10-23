import unittest
from app.services.recommendation_service import RecommendationService

class RecommendationServiceTestCase(unittest.TestCase):
    def test_nominal_baseline_recommendation(self):
        """Verifies that an empty alert list generates a baseline health recommendation with uncertainty note."""
        recs = RecommendationService.generate_recommendations([])
        self.assertEqual(len(recs), 1)
        r = recs[0]
        self.assertEqual(r["id"], "rec_baseline_nominal")
        self.assertEqual(r["category"], "general")
        self.assertEqual(r["severity"], "info")
        self.assertIn("reasoning", r)
        self.assertIn("uncertainty_note", r)
        self.assertGreater(len(r["suggested_investigations"]), 0)

    def test_cpu_pressure_recommendation(self):
        """Verifies mapping of CPU alert to non-destructive investigative guidance."""
        alert = {
            "alert_type": "cpu_pressure",
            "severity": "critical",
            "evidence": {
                "current_value_percent": 96.5,
                "logical_cores": 8,
                "threshold_warning_percent": 75.0,
                "threshold_critical_percent": 90.0,
            }
        }
        recs = RecommendationService.generate_recommendations([alert])
        self.assertEqual(len(recs), 1)
        r = recs[0]
        self.assertEqual(r["category"], "cpu")
        self.assertEqual(r["severity"], "critical")
        self.assertIn("sort_by=cpu_percent", " ".join(r["suggested_investigations"]))
        self.assertIn("malfunction", r["uncertainty_note"])

    def test_memory_pressure_recommendation_cautions_about_page_cache(self):
        """Verifies that memory recommendations explicitly address Linux page cache reclaimability."""
        alert = {
            "alert_type": "memory_pressure",
            "severity": "warning",
            "evidence": {
                "current_percent": 84.0,
                "available_bytes": 4000000000,
                "total_bytes": 16000000000,
            }
        }
        recs = RecommendationService.generate_recommendations([alert])
        self.assertEqual(len(recs), 1)
        r = recs[0]
        self.assertEqual(r["category"], "memory")
        # Must emphasize page cache nuance
        self.assertIn("cache", r["uncertainty_note"].lower())
        self.assertIn("sort_by=memory_rss", " ".join(r["suggested_investigations"]))

    def test_load_pressure_recommendation_cautions_about_io_wait(self):
        """Verifies load average guidance notes difference between CPU compute and I/O sleep."""
        alert = {
            "alert_type": "load_pressure",
            "severity": "warning",
            "evidence": {
                "load_1m": 12.0,
                "logical_cores": 4,
            }
        }
        recs = RecommendationService.generate_recommendations([alert])
        self.assertEqual(len(recs), 1)
        r = recs[0]
        self.assertEqual(r["category"], "load")
        self.assertIn("I/O", r["uncertainty_note"])

if __name__ == "__main__":
    unittest.main()
