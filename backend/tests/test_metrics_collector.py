import unittest
from unittest.mock import patch, MagicMock
from collections import namedtuple
from app.services.metrics_collector import MetricsCollector

class MetricsCollectorTestCase(unittest.TestCase):
    def setUp(self):
        self.collector = MetricsCollector()

    def test_first_sample_cpu_priming(self):
        """Verifies that the collector initializes CPU baseline to prevent bogus 0% values."""
        self.assertTrue(self.collector._cpu_primed)
        cpu = self.collector.collect_cpu_metrics()
        self.assertTrue(cpu["available"])
        self.assertIn("total_percent", cpu)
        self.assertIn("per_core_percent", cpu)
        self.assertIn("logical_cores", cpu)
        self.assertGreaterEqual(cpu["total_percent"], 0.0)

    def test_platform_context_detection(self):
        """Tests that platform context accurately identifies the operating system and WSL2/Linux scope."""
        ctx = self.collector.detect_platform_context()
        self.assertIn("os", ctx)
        self.assertIn("is_linux", ctx)
        self.assertIn("is_wsl", ctx)
        self.assertIn("scope", ctx)
        self.assertIn("description", ctx)
        self.assertIn("proc_fs_available", ctx)
        # Never label Windows host as wsl2_linux_guest
        if ctx["os"].lower().startswith("win"):
            self.assertEqual(ctx["scope"], "windows_host")
            self.assertFalse(ctx["is_linux"])
            self.assertFalse(ctx["is_wsl"])

    def test_wsl2_detection_mock(self):
        """Tests that WSL2 kernel signatures in /proc/version or release are detected properly."""
        with patch("platform.system", return_value="Linux"), \
             patch("platform.release", return_value="6.18.33.2-microsoft-standard-WSL2"), \
             patch("platform.version", return_value="#1 SMP PREEMPT_DYNAMIC"), \
             patch("os.path.exists", return_value=True), \
             patch("os.path.isdir", return_value=True):
            
            ctx = MetricsCollector.detect_platform_context()
            self.assertTrue(ctx["is_linux"])
            self.assertTrue(ctx["is_wsl"])
            self.assertEqual(ctx["scope"], "wsl2_linux_guest")
            self.assertIn("WSL2", ctx["description"])

    def test_native_linux_detection_mock(self):
        """Tests native Linux detection when no WSL signatures exist."""
        with patch("platform.system", return_value="Linux"), \
             patch("platform.release", return_value="6.5.0-generic"), \
             patch("platform.version", return_value="#42-Ubuntu SMP"), \
             patch("os.path.exists", return_value=False), \
             patch("os.path.isdir", return_value=True):
            
            ctx = MetricsCollector.detect_platform_context()
            self.assertTrue(ctx["is_linux"])
            self.assertFalse(ctx["is_wsl"])
            self.assertEqual(ctx["scope"], "linux_native")

    def test_load_average_unavailable_handling(self):
        """Tests that when load average is unsupported, null is returned without fabricating numbers."""
        with patch("os.getloadavg", side_effect=AttributeError("no getloadavg on this platform"), create=True), \
             patch("os.path.exists", return_value=False), \
             patch("psutil.getloadavg", side_effect=AttributeError("not supported"), create=True):
            
            load = MetricsCollector.get_load_average()
            self.assertFalse(load["supported"])
            self.assertIsNone(load["load_1m"])
            self.assertIsNone(load["load_5m"])
            self.assertIsNone(load["load_15m"])

    def test_load_average_supported_mock(self):
        """Tests parsing of real/mocked load averages when supported."""
        with patch("os.getloadavg", return_value=(0.45, 0.72, 0.91), create=True):
            load = MetricsCollector.get_load_average()
            self.assertTrue(load["supported"])
            self.assertEqual(load["load_1m"], 0.45)
            self.assertEqual(load["load_5m"], 0.72)
            self.assertEqual(load["load_15m"], 0.91)

    def test_memory_metrics_collection(self):
        """Tests virtual memory collection and Linux buffer/cached attribute handling."""
        mem = MetricsCollector.collect_memory_metrics()
        self.assertTrue(mem["available"])
        self.assertGreater(mem["total_bytes"], 0)
        self.assertGreaterEqual(mem["percent"], 0.0)

    def test_memory_metrics_error_tolerance(self):
        """Verifies that unexpected memory inspection errors return unavailable without crashing."""
        with patch("psutil.virtual_memory", side_effect=RuntimeError("Test simulated read failure")):
            mem = MetricsCollector.collect_memory_metrics()
            self.assertFalse(mem["available"])
            self.assertIsNone(mem["total_bytes"])
            self.assertIn("Test simulated read failure", mem["error"])

    def test_swap_unconfigured_handling(self):
        """Verifies that disabled/zero swap (common in containers/WSL2) is handled gracefully."""
        SwapMock = namedtuple("SwapMock", ["total", "used", "free", "percent", "sin", "sout"])
        zero_swap = SwapMock(total=0, used=0, free=0, percent=0.0, sin=0, sout=0)
        with patch("psutil.swap_memory", return_value=zero_swap):
            swap = MetricsCollector.collect_swap_metrics()
            self.assertTrue(swap["available"])
            self.assertFalse(swap["swap_configured"])
            self.assertEqual(swap["percent"], 0.0)

if __name__ == "__main__":
    unittest.main()
