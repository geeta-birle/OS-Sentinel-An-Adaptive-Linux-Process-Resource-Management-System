from typing import List, Dict, Any, Optional

class RecommendationService:
    """
    Maps active and historical resource-pressure alerts to human-readable,
    conservative, and strictly non-destructive investigative recommendations.
    Always includes explicit reasoning and uncertainty caveats.
    """

    @classmethod
    def generate_recommendations(
        cls,
        active_alerts: List[Dict[str, Any]],
        current_snapshot: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Produces human-readable investigative guidance based on active alert evidence.
        Never suggests or executes destructive actions.
        """
        recommendations: List[Dict[str, Any]] = []

        if not active_alerts:
            recommendations.append({
                "id": "rec_baseline_nominal",
                "category": "general",
                "severity": "info",
                "title": "System Operating Within Configured Baselines",
                "description": "No sustained resource pressure detected across monitored subsystems.",
                "suggested_investigations": [
                    "Continue monitoring historical trends via GET /api/v1/system/history.",
                    "Verify threshold suitability in GET /api/v1/settings for your environment workload."
                ],
                "reasoning": "All collected telemetry values are within normal operating bounds or have not breached persistence thresholds.",
                "uncertainty_note": "Short transient bursts are intentionally filtered to prevent alert fatigue and do not generate recommendations."
            })
            return recommendations

        for alert in active_alerts:
            alert_type = alert.get("alert_type")
            severity = alert.get("severity", "warning")
            evidence = alert.get("evidence", {})

            if alert_type == "cpu_pressure":
                recommendations.append(cls._cpu_recommendation(severity, evidence))
            elif alert_type == "memory_pressure":
                recommendations.append(cls._memory_recommendation(severity, evidence))
            elif alert_type == "swap_pressure":
                recommendations.append(cls._swap_recommendation(severity, evidence))
            elif alert_type == "load_pressure":
                recommendations.append(cls._load_recommendation(severity, evidence))

        return recommendations

    @staticmethod
    def _cpu_recommendation(severity: str, evidence: Dict[str, Any]) -> Dict[str, Any]:
        val = evidence.get("current_value_percent", "N/A")
        cores = evidence.get("logical_cores", "N/A")
        return {
            "id": f"rec_cpu_{severity}",
            "category": "cpu",
            "severity": severity,
            "title": "Investigate High CPU Utilization and Compute Bottlenecks",
            "description": f"Sustained CPU utilization observed at {val}% across {cores} logical cores.",
            "suggested_investigations": [
                "Inspect the top compute consumers using GET /api/v1/processes?sort_by=cpu_percent&limit=10.",
                "Review process details via GET /api/v1/processes/<pid> to determine whether threads are parallelized.",
                "Check whether high CPU corresponds to expected intentional workloads (e.g. compilation, video transcoding, build tasks) versus runaway spin-loops."
            ],
            "reasoning": f"CPU utilization remained above the {evidence.get('threshold_warning_percent', 75)}% threshold throughout the rolling persistence window.",
            "uncertainty_note": "High CPU utilization alone does not indicate a malfunction. Legitimate high-throughput tasks rightfully utilize available CPU capacity."
        }

    @staticmethod
    def _memory_recommendation(severity: str, evidence: Dict[str, Any]) -> Dict[str, Any]:
        val = evidence.get("current_percent", "N/A")
        avail_gb = round(evidence.get("available_bytes", 0) / (1024**3), 2)
        return {
            "id": f"rec_memory_{severity}",
            "category": "memory",
            "severity": severity,
            "title": "Investigate Memory Consumption & Evaluate Buffer Cache",
            "description": f"Virtual memory usage is elevated at {val}% with {avail_gb} GB reported available.",
            "suggested_investigations": [
                "Inspect resident set size (RSS) per process using GET /api/v1/processes?sort_by=memory_rss&limit=10 to find top memory holders.",
                "Evaluate whether memory is consumed by application heaps (RSS) or reclaimable Linux kernel buffers and page cache (buffers_bytes/cached_bytes).",
                "Check swap utilization in GET /api/v1/system/summary to verify whether memory pressure is forcing disk paging."
            ],
            "reasoning": f"Memory usage exceeded the {evidence.get('threshold_warning_percent', 80)}% threshold across consecutive samples.",
            "uncertainty_note": "High memory usage alone does NOT indicate a leak or problem. Operating systems (particularly Linux) aggressively cache files in unused memory, which is reclaimed instantaneously on demand."
        }

    @staticmethod
    def _swap_recommendation(severity: str, evidence: Dict[str, Any]) -> Dict[str, Any]:
        val = evidence.get("current_percent", "N/A")
        return {
            "id": f"rec_swap_{severity}",
            "category": "swap",
            "severity": severity,
            "title": "Evaluate Swap Utilization and Memory Thrashing Risks",
            "description": f"Swap space consumption has reached {val}%.",
            "suggested_investigations": [
                "Correlate swap consumption with physical RAM pressure to determine if the system is experiencing thrashing.",
                "Identify whether inactive long-running background daemons have simply been paged out to conserve physical RAM.",
                "Review memory-intensive processes using GET /api/v1/processes?sort_by=memory_rss."
            ],
            "reasoning": f"Swap consumption exceeded the configured threshold ({evidence.get('threshold_warning_percent', 50)}%).",
            "uncertainty_note": "Some Linux distributions and WSL2 configurations proactively swap out idle memory to maintain larger I/O page caches without hurting responsiveness."
        }

    @staticmethod
    def _load_recommendation(severity: str, evidence: Dict[str, Any]) -> Dict[str, Any]:
        l1 = evidence.get("load_1m", "N/A")
        cores = evidence.get("logical_cores", "N/A")
        return {
            "id": f"rec_load_{severity}",
            "category": "load",
            "severity": severity,
            "title": "Evaluate Run-Queue and Task Saturation",
            "description": f"1-minute load average ({l1}) exceeds recommended ratio for a {cores}-core system.",
            "suggested_investigations": [
                "Determine if load is driven by runnable CPU tasks (high CPU %) or uninterruptible disk I/O sleep (D state threads).",
                "Check process statuses via GET /api/v1/processes to identify threads waiting on storage or network I/O.",
                "Compare 1m, 5m, and 15m load trends via GET /api/v1/system/summary to evaluate if load is escalating or declining."
            ],
            "reasoning": f"Load average exceeded the threshold ratio relative to total logical CPU cores.",
            "uncertainty_note": "Load averages reflect both CPU-demand and uninterruptible I/O wait states. A high load with low CPU utilization typically indicates storage I/O latency rather than compute bottlenecks."
        }
