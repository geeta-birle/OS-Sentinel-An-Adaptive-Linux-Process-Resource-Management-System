import os
import unittest
from unittest.mock import patch, MagicMock
import psutil
from app.services.process_service import (
    ProcessService,
    ProcessNotFoundError,
    ProcessAccessDeniedError
)

class ProcessServiceTestCase(unittest.TestCase):
    def test_list_current_processes(self):
        """Verifies real process listing returns valid schema and requested limits."""
        res = ProcessService.list_processes(sort_by="cpu_percent", order="desc", limit=10)
        self.assertIn("processes", res)
        self.assertIn("total_count", res)
        self.assertIn("returned_count", res)
        self.assertLessEqual(res["returned_count"], 10)
        self.assertGreater(len(res["processes"]), 0)

        # Inspect first process structure
        first_proc = res["processes"][0]
        self.assertIn("pid", first_proc)
        self.assertIn("name", first_proc)
        self.assertIn("status", first_proc)
        self.assertIn("cpu_percent", first_proc)
        self.assertIn("memory_percent", first_proc)
        self.assertIn("memory_rss", first_proc)

    def test_sorting_and_order(self):
        """Verifies that processes can be sorted ascending or descending by pid or name."""
        res_asc = ProcessService.list_processes(sort_by="pid", order="asc", limit=15)
        pids_asc = [p["pid"] for p in res_asc["processes"]]
        self.assertEqual(pids_asc, sorted(pids_asc))

        res_desc = ProcessService.list_processes(sort_by="pid", order="desc", limit=15)
        pids_desc = [p["pid"] for p in res_desc["processes"]]
        self.assertEqual(pids_desc, sorted(pids_desc, reverse=True))

    def test_disappearing_process_handling(self):
        """Verifies that NoSuchProcess raised during iteration does not crash the service."""
        mock_p1 = MagicMock()
        mock_p1.pid = 101
        mock_p1.name.return_value = "systemd"
        mock_p1.status.return_value = "running"
        mock_p1.cpu_percent.return_value = 0.5
        mock_p1.memory_percent.return_value = 1.0
        mock_p1.memory_info.return_value = MagicMock(rss=1024000)
        mock_p1.username.return_value = "root"
        mock_p1.create_time.return_value = 1000.0

        mock_p2 = MagicMock()
        mock_p2.pid = 102
        mock_p2.name.side_effect = psutil.NoSuchProcess(102, "simulated消失")

        mock_p3 = MagicMock()
        mock_p3.pid = 103
        mock_p3.name.side_effect = psutil.AccessDenied(103, "simulated access denied")
        mock_p3.status.side_effect = psutil.AccessDenied(103, "simulated access denied")
        mock_p3.cpu_percent.return_value = 0.0
        mock_p3.memory_percent.return_value = 0.0
        mock_p3.memory_info.side_effect = psutil.AccessDenied(103)
        mock_p3.username.side_effect = psutil.AccessDenied(103)
        mock_p3.create_time.side_effect = psutil.AccessDenied(103)

        with patch("psutil.process_iter", return_value=[mock_p1, mock_p2, mock_p3]):
            result = ProcessService.list_processes(limit=10)
            # mock_p2 disappeared so it must be omitted. mock_p1 and mock_p3 (with fallback) are safely handled.
            self.assertEqual(result["returned_count"], 2)
            returned_pids = [p["pid"] for p in result["processes"]]
            self.assertIn(101, returned_pids)
            self.assertNotIn(102, returned_pids)
            self.assertIn(103, returned_pids)

    def test_get_process_detail_current_pid(self):
        """Verifies detail inspection of the current executing Python process."""
        current_pid = os.getpid()
        detail = ProcessService.get_process_detail(current_pid)
        self.assertEqual(detail["pid"], current_pid)
        self.assertIn("name", detail)
        self.assertIn("memory_rss_bytes", detail)
        self.assertIn("cpu_percent", detail)
        self.assertIn("status", detail)

    def test_get_process_detail_not_found(self):
        """Verifies ProcessNotFoundError is raised when PID does not exist."""
        non_existent_pid = 99999999
        with self.assertRaises(ProcessNotFoundError):
            ProcessService.get_process_detail(non_existent_pid)

    def test_get_process_detail_access_denied(self):
        """Verifies ProcessAccessDeniedError is raised when process access is denied."""
        with patch("psutil.pid_exists", return_value=True), \
             patch("psutil.Process", side_effect=psutil.AccessDenied(1, "Access denied")):
            with self.assertRaises(ProcessAccessDeniedError):
                ProcessService.get_process_detail(1)

    def test_sanitize_cmdline(self):
        """Verifies process command line secrets (passwords, tokens, keys) are sanitized."""
        raw = [
            "python", "worker.py",
            "--password=supersecret",
            "--token", "secret123",
            "-p", "dbpass",
            "--api-key=secret_key_abc",
            "--api-key", "secret_key_xyz",
            "--secret=topsecret",
            "-p=inlinepass",
            "--token=tok12345",
            "--verbose",
            "--host", "127.0.0.1",
            "--port=5000"
        ]
        sanitized = ProcessService.sanitize_cmdline(raw)
        self.assertEqual(sanitized[0], "python")
        self.assertEqual(sanitized[1], "worker.py")
        self.assertEqual(sanitized[2], "--password=***")
        self.assertEqual(sanitized[3], "--token")
        self.assertEqual(sanitized[4], "***")
        self.assertEqual(sanitized[5], "-p")
        self.assertEqual(sanitized[6], "***")
        self.assertEqual(sanitized[7], "--api-key=***")
        self.assertEqual(sanitized[8], "--api-key")
        self.assertEqual(sanitized[9], "***")
        self.assertEqual(sanitized[10], "--secret=***")
        self.assertEqual(sanitized[11], "-p=***")
        self.assertEqual(sanitized[12], "--token=***")
        self.assertEqual(sanitized[13], "--verbose")
        self.assertEqual(sanitized[14], "--host")
        self.assertEqual(sanitized[15], "127.0.0.1")
        self.assertEqual(sanitized[16], "--port=5000")

if __name__ == "__main__":
    unittest.main()
