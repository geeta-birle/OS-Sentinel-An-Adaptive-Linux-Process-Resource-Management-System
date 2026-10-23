from flask import Blueprint, jsonify, request, current_app
from datetime import datetime, timezone
from app.services.system_service import SystemService
from app.services.process_service import (
    ProcessService,
    ProcessNotFoundError,
    ProcessAccessDeniedError
)
from app.storage.database import Database
from app.models.detection_settings import DetectionSettings
from app.services.detection_service import DetectionService
from app.services.recommendation_service import RecommendationService

api_bp = Blueprint("api_v1", __name__, url_prefix="/api/v1")

def get_db() -> Database:
    db_path = current_app.config.get("DB_PATH", "sentinel.db")
    return Database(db_path)

def get_detector() -> DetectionService:
    db = get_db()
    return DetectionService(db)

@api_bp.route("/health", methods=["GET"])
def health():
    """Service liveness probe."""
    return jsonify(SystemService.get_health_status()), 200

@api_bp.route("/health/readiness", methods=["GET"])
def readiness():
    """Service readiness probe verifying API, system inspector, and database availability."""
    db_ok = True
    try:
        db = get_db()
        db.get_count()
    except Exception:
        db_ok = False
    return jsonify(SystemService.get_readiness_status(db_available=db_ok)), 200

@api_bp.route("/system/summary", methods=["GET"])
def system_summary():
    """Returns genuine platform metadata and live system measurements."""
    return jsonify(SystemService.get_system_summary()), 200

@api_bp.route("/system/history", methods=["GET"])
def system_history():
    """
    Returns time-series history of collected system metrics.
    Query params:
      - limit: int (1..500, default 50)
      - since: ISO-8601 string (optional)
    """
    limit_str = request.args.get("limit", "50")
    try:
        limit = int(limit_str)
        if limit < 1 or limit > 500:
            return jsonify({
                "error": "Parameter 'limit' must be an integer between 1 and 500.",
                "code": "INVALID_PARAMETER"
            }), 400
    except ValueError:
        return jsonify({
            "error": "Parameter 'limit' must be a valid integer.",
            "code": "INVALID_PARAMETER"
        }), 400

    since = request.args.get("since")
    if since:
        try:
            datetime.fromisoformat(since.replace("Z", "+00:00"))
        except ValueError:
            return jsonify({
                "error": "Parameter 'since' must be a valid ISO 8601 timestamp (e.g. 2026-10-22T12:00:00Z).",
                "code": "INVALID_PARAMETER"
            }), 400

    try:
        db = get_db()
        records = db.get_history(limit=limit, since=since)
        return jsonify({
            "count": len(records),
            "limit": limit,
            "since": since,
            "history": records
        }), 200
    except Exception as e:
        return jsonify({
            "error": f"Failed to retrieve system history: {str(e)}",
            "code": "DATABASE_ERROR"
        }), 500

@api_bp.route("/processes", methods=["GET"])
def list_processes():
    """
    Returns safe, read-only list of system processes.
    Query params:
      - sort_by: cpu_percent | memory_percent | memory_rss | pid | name | status (default cpu_percent)
      - order: desc | asc (default desc)
      - limit: int (1..500, default 50)
    """
    sort_by = request.args.get("sort_by", "cpu_percent").lower()
    if sort_by not in ProcessService.ALLOWED_SORT_FIELDS:
        return jsonify({
            "error": f"Invalid 'sort_by' parameter '{sort_by}'. Allowed: {', '.join(sorted(ProcessService.ALLOWED_SORT_FIELDS))}.",
            "code": "INVALID_PARAMETER"
        }), 400

    order = request.args.get("order", "desc").lower()
    if order not in ("asc", "desc"):
        return jsonify({
            "error": f"Invalid 'order' parameter '{order}'. Allowed: asc, desc.",
            "code": "INVALID_PARAMETER"
        }), 400

    limit_str = request.args.get("limit", "50")
    try:
        limit = int(limit_str)
        if limit < 1 or limit > 500:
            return jsonify({
                "error": "Parameter 'limit' must be an integer between 1 and 500.",
                "code": "INVALID_PARAMETER"
            }), 400
    except ValueError:
        return jsonify({
            "error": "Parameter 'limit' must be a valid integer.",
            "code": "INVALID_PARAMETER"
        }), 400

    try:
        result = ProcessService.list_processes(sort_by=sort_by, order=order, limit=limit)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({
            "error": f"Error inspecting system processes: {str(e)}",
            "code": "PROCESS_INSPECTION_ERROR"
        }), 500

@api_bp.route("/processes/<int:pid>", methods=["GET"])
def process_detail(pid: int):
    """
    Returns granular read-only information for a specific PID.
    """
    if pid < 0:
        return jsonify({
            "error": "Process PID must be a non-negative integer.",
            "code": "INVALID_PID"
        }), 400

    try:
        detail = ProcessService.get_process_detail(pid)
        return jsonify(detail), 200
    except ProcessNotFoundError:
        return jsonify({
            "error": f"Process with PID {pid} not found.",
            "code": "PROCESS_NOT_FOUND"
        }), 404
    except ProcessAccessDeniedError:
        return jsonify({
            "error": f"Access denied inspecting process PID {pid}.",
            "code": "ACCESS_DENIED"
        }), 403
    except Exception as e:
        return jsonify({
            "error": f"Failed to inspect process PID {pid}: {str(e)}",
            "code": "PROCESS_INSPECTION_ERROR"
        }), 500

# --- Phase 3 Endpoints ---

@api_bp.route("/alerts", methods=["GET"])
def list_alerts():
    """
    Returns persisted resource pressure alerts.
    Query params:
      - status: active | recovered | all (default all)
      - severity: warning | critical (optional)
      - limit: int (1..500, default 50)
    """
    status_raw = request.args.get("status", "all").lower()
    if status_raw not in ("active", "recovered", "all"):
        return jsonify({
            "error": f"Invalid 'status' parameter '{status_raw}'. Allowed: active, recovered, all.",
            "code": "INVALID_PARAMETER"
        }), 400
    status_filter = None if status_raw == "all" else status_raw

    severity_filter = request.args.get("severity")
    if severity_filter:
        severity_filter = severity_filter.lower()
        if severity_filter not in ("warning", "critical"):
            return jsonify({
                "error": f"Invalid 'severity' parameter '{severity_filter}'. Allowed: warning, critical.",
                "code": "INVALID_PARAMETER"
            }), 400

    limit_str = request.args.get("limit", "50")
    try:
        limit = int(limit_str)
        if limit < 1 or limit > 500:
            return jsonify({
                "error": "Parameter 'limit' must be an integer between 1 and 500.",
                "code": "INVALID_PARAMETER"
            }), 400
    except ValueError:
        return jsonify({
            "error": "Parameter 'limit' must be a valid integer.",
            "code": "INVALID_PARAMETER"
        }), 400

    try:
        db = get_db()
        alerts = db.get_alerts(status=status_filter, severity=severity_filter, limit=limit)
        return jsonify({
            "count": len(alerts),
            "limit": limit,
            "status": status_raw,
            "severity": severity_filter,
            "alerts": alerts
        }), 200
    except Exception as e:
        return jsonify({
            "error": f"Failed to retrieve alerts: {str(e)}",
            "code": "DATABASE_ERROR"
        }), 500

@api_bp.route("/recommendations", methods=["GET"])
def get_recommendations():
    """
    Returns explainable, non-destructive investigative recommendations
    derived from current active alerts and telemetry.
    """
    try:
        db = get_db()
        active_alerts = db.get_alerts(status="active", limit=20)
        recs = RecommendationService.generate_recommendations(active_alerts)
        return jsonify({
            "count": len(recs),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "active_alerts_count": len(active_alerts),
            "recommendations": recs
        }), 200
    except Exception as e:
        return jsonify({
            "error": f"Failed to generate recommendations: {str(e)}",
            "code": "RECOMMENDATION_ERROR"
        }), 500

@api_bp.route("/settings", methods=["GET"])
def get_settings():
    """Returns current detection thresholds and persistence settings."""
    try:
        detector = get_detector()
        settings = detector.get_settings()
        return jsonify(settings.to_dict()), 200
    except Exception as e:
        return jsonify({
            "error": f"Failed to retrieve settings: {str(e)}",
            "code": "SETTINGS_ERROR"
        }), 500

@api_bp.route("/settings", methods=["PUT", "PATCH"])
def update_settings():
    """
    Updates configurable detection thresholds, persistence windows, and cooldowns.
    Validates all thresholds strictly.
    """
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({
            "error": "Request body must be a valid JSON object.",
            "code": "INVALID_PAYLOAD"
        }), 400

    settings, err = DetectionSettings.from_dict(payload)
    if err:
        return jsonify({
            "error": err,
            "code": "INVALID_SETTINGS"
        }), 400

    try:
        detector = get_detector()
        detector.update_settings(settings)
        return jsonify({
            "message": "Detection settings updated successfully.",
            "settings": settings.to_dict()
        }), 200
    except Exception as e:
        return jsonify({
            "error": f"Failed to persist settings: {str(e)}",
            "code": "DATABASE_ERROR"
        }), 500
