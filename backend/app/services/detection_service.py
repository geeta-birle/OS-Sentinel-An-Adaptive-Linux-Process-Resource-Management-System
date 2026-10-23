import json
import logging
import math
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from app.models.detection_settings import DetectionSettings
from app.storage.database import Database

logger = logging.getLogger(__name__)

class DetectionService:
    """
    Explainable, deterministic resource-pressure detection engine.
    Evaluates CPU, memory, swap, and load average metrics against configurable thresholds,
    suppresses isolated transient spikes via rolling persistence windows, handles missing data,
    enforces per-alert cooldowns, and tracks stateful recovery.
    """

    def __init__(self, db: Database, settings: Optional[DetectionSettings] = None):
        self.db = db
        if settings is not None:
            self.settings = settings
        else:
            self.settings = DetectionSettings()
            self.get_settings()
        # In-memory rolling tracker for each alert type
        # Key: alert_type -> dict of rolling state
        self._state: Dict[str, Dict[str, Any]] = {}
        self._init_state()

    def _init_state(self) -> None:
        for alert_type in ("cpu_pressure", "memory_pressure", "swap_pressure", "load_pressure"):
            self._state[alert_type] = {
                "consecutive_critical": 0,
                "consecutive_warning": 0,
                "consecutive_recovery": 0,
                "active_alert_id": None,
                "active_severity": None,
                "first_breach_time": None,
                "last_alert_triggered_at": 0.0,  # epoch seconds
            }

    def update_settings(self, new_settings: DetectionSettings) -> None:
        self.settings = new_settings
        self.db.save_settings("detection_settings", new_settings.to_dict())

    def get_settings(self) -> DetectionSettings:
        try:
            saved = self.db.get_settings("detection_settings")
            if saved:
                loaded, err = DetectionSettings.from_dict(saved)
                if loaded and not err:
                    self.settings = loaded
        except Exception as e:
            # Retain current self.settings, log error, do NOT reset alert state or crash loop
            logger.error(f"Failed to refresh detection settings from database: {e}")
        return self.settings

    def evaluate_snapshot(
        self,
        snapshot: Dict[str, Any],
        current_time: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Evaluates a complete metric snapshot deterministically.
        Supports controllable clock injection via `current_time` (epoch seconds).
        Returns list of newly triggered or updated active alert dicts.
        """
        now_ts = current_time if current_time is not None else time.time()
        iso_now = datetime.fromtimestamp(now_ts, tz=timezone.utc).isoformat()

        # Sync active alerts and persisted settings from DB
        self.get_settings()
        self._sync_active_alerts_from_db()

        active_events = []

        # 1. CPU Evaluation
        cpu_event = self._evaluate_cpu(snapshot, now_ts, iso_now)
        if cpu_event:
            active_events.append(cpu_event)

        # 2. Memory Evaluation
        mem_event = self._evaluate_memory(snapshot, now_ts, iso_now)
        if mem_event:
            active_events.append(mem_event)

        # 3. Swap Evaluation
        swap_event = self._evaluate_swap(snapshot, now_ts, iso_now)
        if swap_event:
            active_events.append(swap_event)

        # 4. Load Average Evaluation
        load_event = self._evaluate_load(snapshot, now_ts, iso_now)
        if load_event:
            active_events.append(load_event)

        return active_events

    def _sync_active_alerts_from_db(self) -> None:
        try:
            for alert_type in self._state:
                active = self.db.get_active_alert_by_type(alert_type)
                if active and self._state[alert_type]["active_alert_id"] is None:
                    self._state[alert_type]["active_alert_id"] = active["id"]
                    self._state[alert_type]["active_severity"] = active["severity"]
                    self._state[alert_type]["first_breach_time"] = active["first_observed_at"]
        except Exception as e:
            logger.error(f"Failed to sync active alerts from database: {e}")

    def _evaluate_cpu(
        self,
        snapshot: Dict[str, Any],
        now_ts: float,
        iso_now: str
    ) -> Optional[Dict[str, Any]]:
        alert_type = "cpu_pressure"
        cpu_data = snapshot.get("cpu", {})
        if not cpu_data.get("available") or cpu_data.get("total_percent") is None:
            # Missing or unprimed sample; reset breach and recovery counters safely
            self._state[alert_type]["consecutive_critical"] = 0
            self._state[alert_type]["consecutive_warning"] = 0
            self._state[alert_type]["consecutive_recovery"] = 0
            return None

        try:
            val = float(cpu_data["total_percent"])
        except (ValueError, TypeError):
            self._state[alert_type]["consecutive_critical"] = 0
            self._state[alert_type]["consecutive_warning"] = 0
            self._state[alert_type]["consecutive_recovery"] = 0
            return None

        if not math.isfinite(val):
            self._state[alert_type]["consecutive_critical"] = 0
            self._state[alert_type]["consecutive_warning"] = 0
            self._state[alert_type]["consecutive_recovery"] = 0
            return None

        thresh = self.settings.cpu
        st = self._state[alert_type]

        evidence = {
            "current_value_percent": val,
            "threshold_warning_percent": thresh.warning,
            "threshold_critical_percent": thresh.critical,
            "recovery_threshold_percent": thresh.recovery,
            "logical_cores": cpu_data.get("logical_cores"),
            "per_core_percent": cpu_data.get("per_core_percent", []),
        }

        explanation = (
            f"Observed total CPU utilization at {val}% across {cpu_data.get('logical_cores', 'N/A')} logical cores. "
            f"Configured warning threshold is {thresh.warning}%, critical threshold is {thresh.critical}%."
        )

        return self._process_threshold_evaluation(
            alert_type=alert_type,
            val=val,
            warn_threshold=thresh.warning,
            crit_threshold=thresh.critical,
            rec_threshold=thresh.recovery,
            persistence_needed=thresh.persistence_samples,
            cooldown_seconds=thresh.cooldown_seconds,
            evidence=evidence,
            explanation=explanation,
            now_ts=now_ts,
            iso_now=iso_now
        )

    def _evaluate_memory(
        self,
        snapshot: Dict[str, Any],
        now_ts: float,
        iso_now: str
    ) -> Optional[Dict[str, Any]]:
        alert_type = "memory_pressure"
        mem_data = snapshot.get("memory", {})
        if not mem_data.get("available") or mem_data.get("percent") is None:
            self._state[alert_type]["consecutive_critical"] = 0
            self._state[alert_type]["consecutive_warning"] = 0
            self._state[alert_type]["consecutive_recovery"] = 0
            return None

        try:
            val = float(mem_data["percent"])
        except (ValueError, TypeError):
            self._state[alert_type]["consecutive_critical"] = 0
            self._state[alert_type]["consecutive_warning"] = 0
            self._state[alert_type]["consecutive_recovery"] = 0
            return None

        if not math.isfinite(val):
            self._state[alert_type]["consecutive_critical"] = 0
            self._state[alert_type]["consecutive_warning"] = 0
            self._state[alert_type]["consecutive_recovery"] = 0
            return None

        thresh = self.settings.memory

        total_bytes = mem_data.get("total_bytes") or 1
        available_bytes = mem_data.get("available_bytes") or 0
        used_bytes = mem_data.get("used_bytes") or 0

        evidence = {
            "current_percent": val,
            "used_bytes": used_bytes,
            "available_bytes": available_bytes,
            "total_bytes": total_bytes,
            "buffers_bytes": mem_data.get("buffers_bytes"),
            "cached_bytes": mem_data.get("cached_bytes"),
            "threshold_warning_percent": thresh.warning,
            "threshold_critical_percent": thresh.critical,
            "recovery_threshold_percent": thresh.recovery,
        }

        explanation = (
            f"Observed virtual memory consumption at {val}% (used {round(used_bytes/(1024**3), 2)} GB "
            f"of {round(total_bytes/(1024**3), 2)} GB total). "
            f"Remaining available memory is {round(available_bytes/(1024**3), 2)} GB. "
            f"Note: Linux kernel cache/buffers are considered reclaimable and are not an inherent malfunction."
        )

        return self._process_threshold_evaluation(
            alert_type=alert_type,
            val=val,
            warn_threshold=thresh.warning,
            crit_threshold=thresh.critical,
            rec_threshold=thresh.recovery,
            persistence_needed=thresh.persistence_samples,
            cooldown_seconds=thresh.cooldown_seconds,
            evidence=evidence,
            explanation=explanation,
            now_ts=now_ts,
            iso_now=iso_now
        )

    def _evaluate_swap(
        self,
        snapshot: Dict[str, Any],
        now_ts: float,
        iso_now: str
    ) -> Optional[Dict[str, Any]]:
        alert_type = "swap_pressure"
        swap_data = snapshot.get("swap", {})
        # If swap is unconfigured (0 bytes) or unavailable, skip without error
        if not swap_data.get("available") or not swap_data.get("swap_configured"):
            self._state[alert_type]["consecutive_critical"] = 0
            self._state[alert_type]["consecutive_warning"] = 0
            self._state[alert_type]["consecutive_recovery"] = 0
            return None

        try:
            val = float(swap_data.get("percent") or 0.0)
        except (ValueError, TypeError):
            self._state[alert_type]["consecutive_critical"] = 0
            self._state[alert_type]["consecutive_warning"] = 0
            self._state[alert_type]["consecutive_recovery"] = 0
            return None

        if not math.isfinite(val):
            self._state[alert_type]["consecutive_critical"] = 0
            self._state[alert_type]["consecutive_warning"] = 0
            self._state[alert_type]["consecutive_recovery"] = 0
            return None

        thresh = self.settings.swap

        evidence = {
            "current_percent": val,
            "used_bytes": swap_data.get("used_bytes"),
            "total_bytes": swap_data.get("total_bytes"),
            "threshold_warning_percent": thresh.warning,
            "threshold_critical_percent": thresh.critical,
            "recovery_threshold_percent": thresh.recovery,
        }

        explanation = (
            f"Observed swap space consumption at {val}% (used {swap_data.get('used_bytes', 0)} bytes). "
            f"High swap consumption coupled with memory pressure suggests active paging."
        )

        return self._process_threshold_evaluation(
            alert_type=alert_type,
            val=val,
            warn_threshold=thresh.warning,
            crit_threshold=thresh.critical,
            rec_threshold=thresh.recovery,
            persistence_needed=thresh.persistence_samples,
            cooldown_seconds=thresh.cooldown_seconds,
            evidence=evidence,
            explanation=explanation,
            now_ts=now_ts,
            iso_now=iso_now
        )

    def _evaluate_load(
        self,
        snapshot: Dict[str, Any],
        now_ts: float,
        iso_now: str
    ) -> Optional[Dict[str, Any]]:
        alert_type = "load_pressure"
        load_data = snapshot.get("load_average", {})
        # Unsupported on Windows host
        if not load_data.get("supported") or load_data.get("load_1m") is None:
            self._state[alert_type]["consecutive_critical"] = 0
            self._state[alert_type]["consecutive_warning"] = 0
            self._state[alert_type]["consecutive_recovery"] = 0
            return None

        try:
            load_1m = float(load_data["load_1m"])
        except (ValueError, TypeError):
            self._state[alert_type]["consecutive_critical"] = 0
            self._state[alert_type]["consecutive_warning"] = 0
            self._state[alert_type]["consecutive_recovery"] = 0
            return None

        if not math.isfinite(load_1m):
            self._state[alert_type]["consecutive_critical"] = 0
            self._state[alert_type]["consecutive_warning"] = 0
            self._state[alert_type]["consecutive_recovery"] = 0
            return None

        logical_cores = snapshot.get("host", {}).get("cpu_cores_logical") or snapshot.get("cpu", {}).get("logical_cores") or 1
        thresh = self.settings.load

        warn_val = thresh.warning_ratio * logical_cores
        crit_val = thresh.critical_ratio * logical_cores
        rec_val = thresh.recovery_ratio * logical_cores

        evidence = {
            "load_1m": load_1m,
            "load_5m": load_data.get("load_5m"),
            "load_15m": load_data.get("load_15m"),
            "logical_cores": logical_cores,
            "warning_threshold_load": round(warn_val, 2),
            "critical_threshold_load": round(crit_val, 2),
            "recovery_threshold_load": round(rec_val, 2),
        }

        explanation = (
            f"Observed 1-minute load average at {load_1m} on a {logical_cores}-core system "
            f"(warning threshold is {round(warn_val, 2)}, critical is {round(crit_val, 2)}). "
            f"Load average represents task queue saturation (runnable + uninterruptible I/O threads)."
        )

        return self._process_threshold_evaluation(
            alert_type=alert_type,
            val=load_1m,
            warn_threshold=warn_val,
            crit_threshold=crit_val,
            rec_threshold=rec_val,
            persistence_needed=thresh.persistence_samples,
            cooldown_seconds=thresh.cooldown_seconds,
            evidence=evidence,
            explanation=explanation,
            now_ts=now_ts,
            iso_now=iso_now
        )

    def _process_threshold_evaluation(
        self,
        alert_type: str,
        val: float,
        warn_threshold: float,
        crit_threshold: float,
        rec_threshold: float,
        persistence_needed: int,
        cooldown_seconds: int,
        evidence: Dict[str, Any],
        explanation: str,
        now_ts: float,
        iso_now: str
    ) -> Optional[Dict[str, Any]]:
        st = self._state[alert_type]

        # Check breach level
        is_critical = val >= crit_threshold
        is_warning = (val >= warn_threshold) and not is_critical
        is_recovering = val <= rec_threshold

        if is_critical:
            st["consecutive_critical"] += 1
            st["consecutive_warning"] += 1
            st["consecutive_recovery"] = 0
            target_severity = "critical"
        elif is_warning:
            st["consecutive_critical"] = 0
            st["consecutive_warning"] += 1
            st["consecutive_recovery"] = 0
            target_severity = "warning"
        elif is_recovering:
            st["consecutive_critical"] = 0
            st["consecutive_warning"] = 0
            st["consecutive_recovery"] += 1
            target_severity = None
        else:
            # In intermediate hysteresis band (between recovery and warning)
            st["consecutive_critical"] = 0
            st["consecutive_warning"] = 0
            st["consecutive_recovery"] = 0
            target_severity = None

        active_id = st["active_alert_id"]

        # Case A: Handle Active Alert
        if active_id is not None:
            # Check for Recovery
            if is_recovering and st["consecutive_recovery"] >= persistence_needed:
                # Alert recovered
                self.db.update_alert(active_id, {
                    "status": "recovered",
                    "recovered_at": iso_now,
                    "last_observed_at": iso_now,
                })
                st["active_alert_id"] = None
                st["active_severity"] = None
                st["first_breach_time"] = None
                st["consecutive_recovery"] = 0
                return None

            # Still under pressure: update active alert timestamps and evidence
            updated_severity = target_severity if target_severity else st["active_severity"]
            self.db.update_alert(active_id, {
                "last_observed_at": iso_now,
                "severity": updated_severity,
                "evidence": evidence,
                "explanation": explanation
            })
            return {
                "id": active_id,
                "alert_type": alert_type,
                "severity": updated_severity,
                "status": "active",
                "first_observed_at": st["first_breach_time"],
                "last_observed_at": iso_now,
                "evidence": evidence,
                "explanation": explanation
            }

        # Case B: No Active Alert -> Check if Persistence Threshold is met
        breach_count = st["consecutive_critical"] if target_severity == "critical" else st["consecutive_warning"]
        if target_severity and breach_count >= persistence_needed:
            # Check per-alert cooldown to prevent spamming
            if (now_ts - st["last_alert_triggered_at"]) < cooldown_seconds:
                # Suppressed due to cooldown
                return None

            # Trigger New Alert
            first_observed = st["first_breach_time"] or iso_now
            new_alert = {
                "alert_type": alert_type,
                "severity": target_severity,
                "status": "active",
                "first_observed_at": first_observed,
                "last_observed_at": iso_now,
                "evidence": evidence,
                "explanation": explanation
            }
            alert_id = self.db.insert_alert(new_alert)
            st["active_alert_id"] = alert_id
            st["active_severity"] = target_severity
            st["first_breach_time"] = first_observed
            st["last_alert_triggered_at"] = now_ts
            st["consecutive_recovery"] = 0

            new_alert["id"] = alert_id
            return new_alert

        # Store first breach timestamp if beginning a new streak
        if (is_critical or is_warning) and breach_count == 1:
            st["first_breach_time"] = iso_now

        return None
