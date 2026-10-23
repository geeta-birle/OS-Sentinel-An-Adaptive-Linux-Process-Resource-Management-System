import logging
import os
import time
import threading
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import psutil

logger = logging.getLogger(__name__)

class ProcessNotFoundError(Exception):
    """Raised when the specified PID does not exist."""
    pass

class ProcessAccessDeniedError(Exception):
    """Raised when access to process information is denied by operating system security."""
    pass

class ProcessService:
    """
    Read-only Linux / host process monitoring service.
    Safely inspects running processes with comprehensive exception handling for
    NoSuchProcess, AccessDenied, ZombieProcess, and process disappearance.
    Does not modify, terminate, suspend, or reprioritize any process.
    """

    ALLOWED_SORT_FIELDS = {
        "cpu_percent",
        "memory_percent",
        "memory_rss",
        "pid",
        "name",
        "status"
    }

    CACHE_TTL_SECONDS: float = 2.0
    _cached_raw_processes: Optional[List[Dict[str, Any]]] = None
    _cache_timestamp: float = 0.0
    _cache_lock: threading.Lock = threading.Lock()

    @classmethod
    def clear_cache(cls) -> None:
        """Clears the in-memory process listing cache."""
        with cls._cache_lock:
            cls._cached_raw_processes = None
            cls._cache_timestamp = 0.0

    @classmethod
    def _collect_raw_processes(cls) -> List[Dict[str, Any]]:
        """Collects raw process metrics in a single pass using psutil.process_iter with attrs."""
        attrs = ["pid", "name", "status", "cpu_percent", "memory_info", "username", "create_time"]
        try:
            total_memory = psutil.virtual_memory().total
        except Exception:
            total_memory = 1

        processes: List[Dict[str, Any]] = []
        for p in psutil.process_iter(attrs=attrs):
            try:
                # Fast path: use batched info dict populated by psutil.process_iter
                if hasattr(p, "info") and isinstance(p.info, dict) and p.info:
                    info = p.info
                    pid = info.get("pid")
                    name = info.get("name") or f"[{pid}]"
                    status = info.get("status") or "unknown"
                    cpu_percent = round(info.get("cpu_percent") or 0.0, 1)
                    mem_info = info.get("memory_info")
                    memory_rss = mem_info.rss if mem_info else 0
                    memory_percent = round((memory_rss / total_memory) * 100, 2) if total_memory else 0.0
                    username = info.get("username")
                    create_time = info.get("create_time")
                else:
                    # Fallback path for unit-test mocks where p.info is not a pre-populated dict
                    pid = p.pid
                    try:
                        name = p.name() or f"[{pid}]"
                    except (psutil.AccessDenied, psutil.ZombieProcess):
                        name = f"[{pid}]"
                    except (psutil.NoSuchProcess, ProcessLookupError, FileNotFoundError):
                        continue

                    try:
                        status = p.status()
                    except (psutil.AccessDenied, psutil.ZombieProcess):
                        status = "unknown"
                    except (psutil.NoSuchProcess, ProcessLookupError, FileNotFoundError):
                        continue

                    try:
                        cpu_percent = round(p.cpu_percent(interval=None), 1)
                    except Exception:
                        cpu_percent = 0.0

                    try:
                        mem_info = p.memory_info()
                        memory_rss = mem_info.rss
                    except Exception:
                        memory_rss = 0

                    try:
                        memory_percent = round(p.memory_percent(), 2)
                    except Exception:
                        memory_percent = 0.0

                    try:
                        username = p.username()
                    except Exception:
                        username = None

                    try:
                        create_time = p.create_time()
                    except Exception:
                        create_time = None

                processes.append({
                    "pid": pid,
                    "name": name,
                    "status": status,
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory_percent,
                    "memory_rss": memory_rss,
                    "username": username,
                    "create_time": create_time,
                })

            except (psutil.NoSuchProcess, ProcessLookupError, FileNotFoundError):
                continue
            except (psutil.ZombieProcess, psutil.AccessDenied):
                continue
            except Exception:
                continue

        return processes

    @classmethod
    def list_processes(
        cls,
        sort_by: str = "cpu_percent",
        order: str = "desc",
        limit: int = 50
    ) -> Dict[str, Any]:
        """
        Retrieves a sorted and bounded list of current processes without crashing on transient state changes.
        """
        if sort_by not in cls.ALLOWED_SORT_FIELDS:
            sort_by = "cpu_percent"

        is_reverse = order.lower() != "asc"
        limit = max(1, min(limit, 500))

        now_ts = time.time()
        with cls._cache_lock:
            if cls._cached_raw_processes is not None and (now_ts - cls._cache_timestamp) < cls.CACHE_TTL_SECONDS:
                raw_processes = list(cls._cached_raw_processes)
                cache_hit = True
                cache_age = round(now_ts - cls._cache_timestamp, 3)
            else:
                raw_processes = cls._collect_raw_processes()
                cls._cached_raw_processes = raw_processes
                cls._cache_timestamp = time.time()
                cache_hit = False
                cache_age = 0.0

        # Sort with None values treated as lowest priority
        def get_sort_key(item: Dict[str, Any]):
            val = item.get(sort_by)
            if val is None:
                return (0, "") if isinstance(sort_by, str) else 0
            if isinstance(val, str):
                return (1, val.lower())
            return (1, val)

        processes = list(raw_processes)
        processes.sort(key=get_sort_key, reverse=is_reverse)
        sliced_processes = processes[:limit]

        return {
            "total_count": len(processes),
            "returned_count": len(sliced_processes),
            "sort_by": sort_by,
            "order": "desc" if is_reverse else "asc",
            "limit": limit,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "cache_hit": cache_hit,
            "cache_age_seconds": cache_age,
            "processes": sliced_processes,
        }

    @classmethod
    def sanitize_cmdline(cls, cmdline: Optional[List[str]]) -> List[str]:
        """
        Redacts sensitive arguments (passwords, tokens, keys) from process command lines.
        """
        if not cmdline:
            return []
        sanitized = []
        skip_next = False
        sensitive_flags = {"--password", "-p", "--passwd", "--secret", "--token", "--api-key", "--apikey", "--auth-token"}
        sensitive_keywords = ("password", "passwd", "secret", "token", "apikey", "api_key", "api-key", "auth_token", "auth-token")

        for arg in cmdline:
            if skip_next:
                sanitized.append("***")
                skip_next = False
                continue

            if arg.lower() in sensitive_flags:
                sanitized.append(arg)
                skip_next = True
                continue

            if "=" in arg:
                key, _ = arg.split("=", 1)
                normalized_key = key.lower().replace("-", "_")
                if key.lower() in sensitive_flags or any(kw.replace("-", "_") in normalized_key for kw in sensitive_keywords):
                    sanitized.append(f"{key}=***")
                    continue

            sanitized.append(arg)
        return sanitized

    @classmethod
    def get_process_detail(cls, pid: int) -> Dict[str, Any]:
        """
        Returns granular details for a specific PID.
        Raises ProcessNotFoundError if not found, or handles AccessDenied gracefully.
        """
        if not psutil.pid_exists(pid):
            raise ProcessNotFoundError(f"Process with PID {pid} does not exist.")

        try:
            p = psutil.Process(pid)
        except psutil.NoSuchProcess:
            raise ProcessNotFoundError(f"Process with PID {pid} does not exist.")
        except psutil.AccessDenied:
            raise ProcessAccessDeniedError(f"Access denied to inspect PID {pid}.")

        try:
            # Basic identity
            try:
                name = p.name()
            except (psutil.AccessDenied, psutil.ZombieProcess):
                name = f"[{pid}]"

            try:
                status = p.status()
            except Exception:
                status = "unknown"

            # Executable & command line
            exe = None
            try:
                exe = p.exe()
            except (psutil.AccessDenied, psutil.ZombieProcess, FileNotFoundError):
                exe = None
            except Exception as e:
                logger.debug("Failed to read exe for PID %s: %s", pid, e)
                exe = None

            cmdline = []
            try:
                raw_cmdline = p.cmdline()
                cmdline = cls.sanitize_cmdline(raw_cmdline)
            except (psutil.AccessDenied, psutil.ZombieProcess, FileNotFoundError):
                cmdline = []
            except Exception as e:
                logger.debug("Failed to read cmdline for PID %s: %s", pid, e)
                cmdline = []

            # Ownership
            username = None
            try:
                username = p.username()
            except Exception:
                username = None

            # Timing & CPU
            create_time = None
            try:
                create_time = p.create_time()
            except Exception:
                pass

            cpu_percent = 0.0
            try:
                cpu_percent = round(p.cpu_percent(interval=None), 1)
            except Exception:
                pass

            # Memory
            memory_rss = 0
            memory_vms = 0
            try:
                mem_info = p.memory_info()
                memory_rss = mem_info.rss
                memory_vms = mem_info.vms
            except Exception:
                pass

            memory_percent = 0.0
            try:
                memory_percent = round(p.memory_percent(), 2)
            except Exception:
                pass

            # Hierarchy & threads
            ppid = None
            try:
                ppid = p.ppid()
            except Exception:
                pass

            num_threads = None
            try:
                num_threads = p.num_threads()
            except Exception:
                pass

            nice = None
            try:
                nice = p.nice()
            except Exception:
                pass

            return {
                "pid": pid,
                "name": name,
                "exe": exe,
                "cmdline": cmdline,
                "status": status,
                "username": username,
                "create_time": create_time,
                "cpu_percent": cpu_percent,
                "memory_percent": memory_percent,
                "memory_rss_bytes": memory_rss,
                "memory_vms_bytes": memory_vms,
                "ppid": ppid,
                "num_threads": num_threads,
                "nice": nice,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        except psutil.NoSuchProcess:
            raise ProcessNotFoundError(f"Process with PID {pid} terminated during inspection.")
        except psutil.AccessDenied:
            raise ProcessAccessDeniedError(f"Access denied to inspect PID {pid}.")
