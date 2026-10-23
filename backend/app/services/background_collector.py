import os
import time
import threading
import logging
from typing import Optional
from app.services.metrics_collector import metrics_collector
from app.storage.database import Database

logger = logging.getLogger(__name__)

class BackgroundMetricsCollector:
    """
    Manages a single background daemon thread for periodic system metric sampling and retention pruning.
    Prevents duplicate background threads during Flask development server reloads.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super(BackgroundMetricsCollector, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized") and self._initialized:
            return
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._running = False
        self._initialized = True
        self._prune_counter = 0

    def start(self, config: dict) -> bool:
        """
        Starts the background sampling loop if enabled and not already running.
        Protects against Werkzeug dual-process reloader duplicates.
        """
        if not config.get("ENABLE_BACKGROUND_COLLECTOR", True):
            return False

        # In Flask debug reloader mode, the master process sets WERKZEUG_RUN_MAIN=None
        # while the worker child sets WERKZEUG_RUN_MAIN='true'.
        # Only launch the thread in the active worker child to prevent duplicate collectors.
        is_debug = config.get("DEBUG", False)
        werkzeug_child = os.environ.get("WERKZEUG_RUN_MAIN") == "true"
        if is_debug and not werkzeug_child and os.environ.get("FLASK_ENV") == "development":
            return False

        with self._lock:
            if self._running:
                return True

            db_path = config.get("DB_PATH")
            interval = max(1, config.get("METRICS_COLLECTION_INTERVAL", 5))
            max_records = config.get("METRICS_RETENTION_MAX_RECORDS", 2000)
            retention_hours = config.get("METRICS_RETENTION_HOURS", 24)

            self._stop_event.clear()
            self._running = True

            self._thread = threading.Thread(
                target=self._run_loop,
                args=(db_path, interval, max_records, retention_hours),
                name="OS-Sentinel-Collector",
                daemon=True
            )
            self._thread.start()
            return True

    def stop(self, timeout: float = 2.0) -> None:
        """
        Signals the collector loop to stop and waits for the thread to exit.
        """
        with self._lock:
            if not self._running:
                return
            self._stop_event.set()
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=timeout)
            self._running = False

    def is_running(self) -> bool:
        return self._running and self._thread is not None and self._thread.is_alive()

    def _run_loop(self, db_path: str, interval: int, max_records: int, retention_hours: int) -> None:
        db = Database(db_path)
        from app.services.detection_service import DetectionService
        detector = DetectionService(db)

        # Immediate first sample on start
        try:
            snapshot = metrics_collector.collect_all_metrics()
            db.insert_metrics(snapshot)
            detector.evaluate_snapshot(snapshot)
        except Exception as e:
            logger.error(f"Error recording initial metrics snapshot: {e}")

        while not self._stop_event.is_set():
            # Wait for next interval or stop signal
            if self._stop_event.wait(timeout=interval):
                break

            try:
                snapshot = metrics_collector.collect_all_metrics()
                db.insert_metrics(snapshot)
                detector.evaluate_snapshot(snapshot)
                self._prune_counter += 1

                # Prune every 10 intervals
                if self._prune_counter >= 10:
                    self._prune_counter = 0
                    db.prune_history(max_records=max_records, retention_hours=retention_hours)
            except Exception as e:
                logger.error(f"Error in background metrics collector: {e}")

# Global instance
background_collector = BackgroundMetricsCollector()
