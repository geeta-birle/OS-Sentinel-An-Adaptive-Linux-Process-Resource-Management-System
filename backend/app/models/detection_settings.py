import math
from dataclasses import dataclass, asdict, field
from typing import Dict, Any, Tuple, Optional

@dataclass
class ResourceThreshold:
    warning: float
    critical: float
    recovery: float
    persistence_samples: int = 3
    cooldown_seconds: int = 60

    def validate(self, name: str) -> Optional[str]:
        if not (math.isfinite(self.warning) and math.isfinite(self.critical) and math.isfinite(self.recovery)):
            return f"For {name}, thresholds must be finite numbers."
        if not (0 <= self.recovery < self.warning < self.critical <= 100):
            return f"For {name}, thresholds must satisfy: 0 <= recovery ({self.recovery}) < warning ({self.warning}) < critical ({self.critical}) <= 100."
        if isinstance(self.persistence_samples, bool) or not (1 <= self.persistence_samples <= 30):
            return f"For {name}, persistence_samples must be an integer between 1 and 30."
        if isinstance(self.cooldown_seconds, bool) or not (5 <= self.cooldown_seconds <= 86400):
            return f"For {name}, cooldown_seconds must be an integer between 5 and 86400."
        return None

@dataclass
class LoadThreshold:
    warning_ratio: float = 1.5   # 1.5x logical CPU count
    critical_ratio: float = 2.5  # 2.5x logical CPU count
    recovery_ratio: float = 1.2  # 1.2x logical CPU count
    persistence_samples: int = 3
    cooldown_seconds: int = 60

    def validate(self) -> Optional[str]:
        if not (math.isfinite(self.warning_ratio) and math.isfinite(self.critical_ratio) and math.isfinite(self.recovery_ratio)):
            return "For load average, ratios must be finite numbers."
        if not (0 < self.recovery_ratio < self.warning_ratio < self.critical_ratio):
            return f"For load average, ratios must satisfy: 0 < recovery ({self.recovery_ratio}) < warning ({self.warning_ratio}) < critical ({self.critical_ratio})."
        if isinstance(self.persistence_samples, bool) or not (1 <= self.persistence_samples <= 30):
            return "For load average, persistence_samples must be an integer between 1 and 30."
        if isinstance(self.cooldown_seconds, bool) or not (5 <= self.cooldown_seconds <= 86400):
            return "For load average, cooldown_seconds must be an integer between 5 and 86400."
        return None

@dataclass
class DetectionSettings:
    cpu: ResourceThreshold = field(default_factory=lambda: ResourceThreshold(warning=75.0, critical=90.0, recovery=70.0, persistence_samples=3, cooldown_seconds=60))
    memory: ResourceThreshold = field(default_factory=lambda: ResourceThreshold(warning=80.0, critical=92.0, recovery=75.0, persistence_samples=3, cooldown_seconds=60))
    swap: ResourceThreshold = field(default_factory=lambda: ResourceThreshold(warning=50.0, critical=80.0, recovery=40.0, persistence_samples=3, cooldown_seconds=60))
    load: LoadThreshold = field(default_factory=LoadThreshold)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Tuple[Optional["DetectionSettings"], Optional[str]]:
        try:
            cpu_data = data.get("cpu", {})
            mem_data = data.get("memory", {})
            swap_data = data.get("swap", {})
            load_data = data.get("load", {})

            for sec_name, sec_dict in [("cpu", cpu_data), ("memory", mem_data), ("swap", swap_data), ("load", load_data)]:
                if isinstance(sec_dict.get("persistence_samples"), bool):
                    return None, f"Field 'persistence_samples' in {sec_name} cannot be a boolean."
                if isinstance(sec_dict.get("cooldown_seconds"), bool):
                    return None, f"Field 'cooldown_seconds' in {sec_name} cannot be a boolean."

            settings = cls(
                cpu=ResourceThreshold(
                    warning=float(cpu_data.get("warning", 75.0)),
                    critical=float(cpu_data.get("critical", 90.0)),
                    recovery=float(cpu_data.get("recovery", 70.0)),
                    persistence_samples=int(cpu_data.get("persistence_samples", 3)),
                    cooldown_seconds=int(cpu_data.get("cooldown_seconds", 60)),
                ),
                memory=ResourceThreshold(
                    warning=float(mem_data.get("warning", 80.0)),
                    critical=float(mem_data.get("critical", 92.0)),
                    recovery=float(mem_data.get("recovery", 75.0)),
                    persistence_samples=int(mem_data.get("persistence_samples", 3)),
                    cooldown_seconds=int(mem_data.get("cooldown_seconds", 60)),
                ),
                swap=ResourceThreshold(
                    warning=float(swap_data.get("warning", 50.0)),
                    critical=float(swap_data.get("critical", 80.0)),
                    recovery=float(swap_data.get("recovery", 40.0)),
                    persistence_samples=int(swap_data.get("persistence_samples", 3)),
                    cooldown_seconds=int(swap_data.get("cooldown_seconds", 60)),
                ),
                load=LoadThreshold(
                    warning_ratio=float(load_data.get("warning_ratio", 1.5)),
                    critical_ratio=float(load_data.get("critical_ratio", 2.5)),
                    recovery_ratio=float(load_data.get("recovery_ratio", 1.2)),
                    persistence_samples=int(load_data.get("persistence_samples", 3)),
                    cooldown_seconds=int(load_data.get("cooldown_seconds", 60)),
                )
            )

            # Validate each section
            err = settings.cpu.validate("CPU")
            if err: return None, err
            err = settings.memory.validate("Memory")
            if err: return None, err
            err = settings.swap.validate("Swap")
            if err: return None, err
            err = settings.load.validate()
            if err: return None, err

            return settings, None
        except (ValueError, TypeError) as e:
            return None, f"Invalid setting value type: {str(e)}"
