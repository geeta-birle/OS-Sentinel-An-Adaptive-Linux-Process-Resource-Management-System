import os
import sys
import platform
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from app.services.metrics_collector import metrics_collector

class SystemService:
    """
    High-level system inspection and health service.
    Combines static host metadata with real, non-fabricated telemetry.
    """

    @classmethod
    def get_real_uptime_seconds(cls) -> Optional[float]:
        return metrics_collector.get_real_uptime_seconds()

    @classmethod
    def get_system_summary(cls) -> Dict[str, Any]:
        """
        Produces genuine platform summary integrated with live measurements.
        Preserves backward compatibility with Phase 1 schemas.
        """
        snapshot = metrics_collector.collect_all_metrics()
        platform_ctx = snapshot.get("platform_context", {})
        uptime_seconds = snapshot.get("uptime_seconds")

        return {
            "status": "online",
            "timestamp": snapshot.get("timestamp"),
            "service": "OS Sentinel Backend",
            "phase": "Phase 3 - Explainable Adaptive Resource-Pressure Detection & Recommendations",
            "host": {
                "hostname": platform.node(),
                "os": platform.system(),
                "os_release": platform.release(),
                "os_version": platform.version(),
                "architecture": platform.machine(),
                "cpu_cores_logical": os.cpu_count(),
                "uptime_seconds": uptime_seconds,
            },
            "runtime": {
                "python_version": sys.version.split()[0],
                "platform": sys.platform,
            },
            "linux_environment": {
                "is_linux": platform_ctx.get("is_linux", False),
                "is_wsl": platform_ctx.get("is_wsl", False),
                "scope": platform_ctx.get("scope", "unknown"),
                "proc_fs_available": platform_ctx.get("proc_fs_available", False),
            },
            "phase_notes": {
                "live_metrics_collected": True,
                "message": "Phase 3 active: live telemetry, resource pressure detection, and recommendations enabled."
            },
            "metrics": {
                "cpu": snapshot.get("cpu"),
                "memory": snapshot.get("memory"),
                "swap": snapshot.get("swap"),
                "load_average": snapshot.get("load_average"),
                "platform_context": platform_ctx,
            }
        }

    @classmethod
    def get_health_status(cls) -> Dict[str, Any]:
        return {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service": "OS Sentinel Backend",
            "version": "0.3.0"
        }

    @classmethod
    def get_readiness_status(cls, db_available: bool = True) -> Dict[str, Any]:
        return {
            "status": "ready" if db_available else "degraded",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service": "OS Sentinel Backend",
            "checks": {
                "api": "ok",
                "system_inspector": "ok",
                "database": "ok" if db_available else "unavailable"
            }
        }
