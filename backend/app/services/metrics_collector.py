import os
import sys
import platform
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple, List
import psutil

class MetricsCollector:
    """
    Collects factual Linux / host system metrics via psutil and /proc interfaces.
    Handles first-sample CPU baseline, unavailable metrics, platform differences,
    and WSL2 guest vs Windows host distinction.
    """

    def __init__(self):
        # Baseline priming for psutil CPU percentage calculation.
        # psutil.cpu_percent(interval=None) compares against the last call.
        # The very first call returns 0.0 or a meaningless value, so we prime it here.
        try:
            psutil.cpu_percent(interval=None)
            psutil.cpu_percent(percpu=True, interval=None)
            self._cpu_primed = True
        except Exception:
            self._cpu_primed = False

    @staticmethod
    def detect_platform_context() -> Dict[str, Any]:
        """
        Accurately identifies platform, distinguishing WSL2 Linux guest from native Linux and Windows.
        Never labels Windows host-wide measurements as Linux-only.
        """
        system_name = platform.system()
        is_linux = system_name.lower() == "linux"
        is_wsl = False
        wsl_distro = os.getenv("WSL_DISTRO_NAME", None)

        if is_linux:
            # Check for WSL signatures in kernel version or /proc/version
            try:
                release_str = platform.release().lower()
                version_str = platform.version().lower()
                if "microsoft" in release_str or "wsl" in release_str or "microsoft" in version_str:
                    is_wsl = True
            except Exception:
                pass

            if not is_wsl and os.path.exists("/proc/version"):
                try:
                    with open("/proc/version", "r", encoding="utf-8") as f:
                        content = f.read().lower()
                        if "microsoft" in content or "wsl" in content:
                            is_wsl = True
                except Exception:
                    pass

        if is_wsl:
            scope = "wsl2_linux_guest"
            description = (
                "Running inside an Ubuntu/Linux containerized VM under WSL2. "
                "Kernel metrics reflect the WSL2 guest kernel. CPU cores are shared with the Windows host, "
                "and maximum memory is constrained by the WSL2 VM allocation (.wslconfig)."
            )
        elif is_linux:
            scope = "linux_native"
            description = "Running on native Linux. Full kernel /proc and sysfs interfaces available."
        elif system_name.lower().startswith("win"):
            scope = "windows_host"
            description = "Running directly on the Windows host OS. Linux-specific interfaces (/proc, load averages) are unavailable."
        else:
            scope = f"{system_name.lower()}_environment"
            description = f"Running on {system_name}."

        return {
            "os": system_name,
            "os_release": platform.release(),
            "os_version": platform.version(),
            "architecture": platform.machine(),
            "is_linux": is_linux,
            "is_wsl": is_wsl,
            "wsl_distribution": wsl_distro,
            "scope": scope,
            "description": description,
            "proc_fs_available": os.path.isdir("/proc"),
        }

    @staticmethod
    def get_real_uptime_seconds() -> Optional[float]:
        """
        Retrieves actual uptime without mock values.
        Prioritizes /proc/uptime under Linux, falls back to psutil.boot_time().
        """
        if os.path.exists("/proc/uptime"):
            try:
                with open("/proc/uptime", "r", encoding="utf-8") as f:
                    uptime_str = f.readline().split()[0]
                    return round(float(uptime_str), 2)
            except Exception:
                pass

        try:
            boot_time = psutil.boot_time()
            if boot_time > 0:
                return round(time.time() - boot_time, 2)
        except Exception:
            pass

        return None

    @staticmethod
    def get_load_average() -> Dict[str, Any]:
        """
        Retrieves 1, 5, 15 minute load averages if supported by OS.
        On Windows, returns supported: False with null values (never synthetic).
        """
        # Try os.getloadavg()
        if hasattr(os, "getloadavg"):
            try:
                l1, l5, l15 = os.getloadavg()
                return {
                    "supported": True,
                    "load_1m": round(l1, 2),
                    "load_5m": round(l5, 2),
                    "load_15m": round(l15, 2),
                }
            except Exception:
                pass

        # Try /proc/loadavg directly on Linux
        if os.path.exists("/proc/loadavg"):
            try:
                with open("/proc/loadavg", "r", encoding="utf-8") as f:
                    parts = f.readline().split()
                    return {
                        "supported": True,
                        "load_1m": round(float(parts[0]), 2),
                        "load_5m": round(float(parts[1]), 2),
                        "load_15m": round(float(parts[2]), 2),
                    }
            except Exception:
                pass

        # Try psutil.getloadavg() if available
        if hasattr(psutil, "getloadavg"):
            try:
                l1, l5, l15 = psutil.getloadavg()
                return {
                    "supported": True,
                    "load_1m": round(l1, 2),
                    "load_5m": round(l5, 2),
                    "load_15m": round(l15, 2),
                }
            except Exception:
                pass

        return {
            "supported": False,
            "load_1m": None,
            "load_5m": None,
            "load_15m": None,
            "reason": "Load average is not supported on this operating system/platform."
        }

    def collect_cpu_metrics(self) -> Dict[str, Any]:
        """
        Collects real CPU metrics. Ensures baseline priming has occurred.
        """
        if not self._cpu_primed:
            try:
                psutil.cpu_percent(interval=None)
                psutil.cpu_percent(percpu=True, interval=None)
                self._cpu_primed = True
                return {
                    "available": False,
                    "error": "CPU baseline was not primed; initial baseline sample established.",
                    "total_percent": None,
                    "per_core_percent": [],
                    "logical_cores": psutil.cpu_count(logical=True),
                    "physical_cores": psutil.cpu_count(logical=False),
                    "baseline_primed": False,
                }
            except Exception as e:
                return {
                    "available": False,
                    "error": f"Failed to prime CPU metrics: {str(e)}",
                    "total_percent": None,
                    "per_core_percent": [],
                    "logical_cores": os.cpu_count(),
                    "physical_cores": None,
                    "baseline_primed": False,
                }

        try:
            # interval=None calculates delta since last call without blocking the HTTP request
            total_percent = psutil.cpu_percent(interval=None)
            per_core = psutil.cpu_percent(percpu=True, interval=None)
            logical_cores = psutil.cpu_count(logical=True)
            physical_cores = psutil.cpu_count(logical=False)

            return {
                "available": True,
                "total_percent": round(total_percent, 1),
                "per_core_percent": [round(c, 1) for c in per_core],
                "logical_cores": logical_cores,
                "physical_cores": physical_cores,
                "baseline_primed": self._cpu_primed,
            }
        except Exception as e:
            return {
                "available": False,
                "error": str(e),
                "total_percent": None,
                "per_core_percent": [],
                "logical_cores": os.cpu_count(),
                "physical_cores": None,
            }

    @staticmethod
    def collect_memory_metrics() -> Dict[str, Any]:
        """
        Collects real virtual memory metrics. Never fabricates values.
        """
        try:
            vm = psutil.virtual_memory()
            mem_data = {
                "available": True,
                "total_bytes": vm.total,
                "used_bytes": vm.used,
                "free_bytes": vm.free,
                "available_bytes": vm.available,
                "percent": round(vm.percent, 1),
            }
            # Linux specific memory counters
            if hasattr(vm, "buffers"):
                mem_data["buffers_bytes"] = vm.buffers
            if hasattr(vm, "cached"):
                mem_data["cached_bytes"] = vm.cached
            if hasattr(vm, "shared"):
                mem_data["shared_bytes"] = getattr(vm, "shared", None)

            return mem_data
        except Exception as e:
            return {
                "available": False,
                "error": str(e),
                "total_bytes": None,
                "used_bytes": None,
                "free_bytes": None,
                "available_bytes": None,
                "percent": None,
            }

    @staticmethod
    def collect_swap_metrics() -> Dict[str, Any]:
        """
        Collects swap memory metrics. Gracefully handles systems without swap configured.
        """
        try:
            sm = psutil.swap_memory()
            is_configured = sm.total > 0
            return {
                "available": True,
                "swap_configured": is_configured,
                "total_bytes": sm.total,
                "used_bytes": sm.used,
                "free_bytes": sm.free,
                "percent": round(sm.percent, 1) if is_configured else 0.0,
                "sin_bytes": getattr(sm, "sin", None),
                "sout_bytes": getattr(sm, "sout", None),
            }
        except Exception as e:
            return {
                "available": False,
                "error": str(e),
                "swap_configured": False,
                "total_bytes": None,
                "used_bytes": None,
                "free_bytes": None,
                "percent": None,
            }

    def collect_all_metrics(self) -> Dict[str, Any]:
        """
        Gathers complete, factual snapshot of system metrics.
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        platform_ctx = self.detect_platform_context()
        uptime_seconds = self.get_real_uptime_seconds()
        load_avg = self.get_load_average()
        cpu = self.collect_cpu_metrics()
        memory = self.collect_memory_metrics()
        swap = self.collect_swap_metrics()

        return {
            "timestamp": timestamp,
            "platform_context": platform_ctx,
            "uptime_seconds": uptime_seconds,
            "load_average": load_avg,
            "cpu": cpu,
            "memory": memory,
            "swap": swap,
        }

# Global singleton collector instance
metrics_collector = MetricsCollector()
