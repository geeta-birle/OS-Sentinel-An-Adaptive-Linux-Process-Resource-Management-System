import os

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    ENV = os.getenv("FLASK_ENV", "production")
    DEBUG = os.getenv("FLASK_DEBUG", "0").lower() in ("1", "true", "yes")
    HOST = os.getenv("HOST", "127.0.0.1")
    PORT = int(os.getenv("PORT", "5000"))
    
    # CORS Origins: comma-separated list or '*'
    raw_cors = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    CORS_ORIGINS = [origin.strip() for origin in raw_cors.split(",") if origin.strip()]
    if "*" in raw_cors:
        CORS_ALLOW_ALL = True
    else:
        CORS_ALLOW_ALL = False

    APP_NAME = "OS Sentinel Backend"
    APP_VERSION = "0.3.0"
    PHASE = "Phase 3 - Explainable Adaptive Resource-Pressure Detection & Recommendations"

    # SQLite Storage & Metrics Engine Configuration
    default_db_dir = os.path.abspath(os.path.join(basedir, "..", "data"))
    DB_PATH = os.getenv("SENTINEL_DB_PATH", os.path.join(default_db_dir, "sentinel.db"))
    
    # Collector Settings
    METRICS_COLLECTION_INTERVAL = int(os.getenv("METRICS_COLLECTION_INTERVAL", "5"))
    METRICS_RETENTION_MAX_RECORDS = int(os.getenv("METRICS_RETENTION_MAX_RECORDS", "2000"))
    METRICS_RETENTION_HOURS = int(os.getenv("METRICS_RETENTION_HOURS", "24"))
    ENABLE_BACKGROUND_COLLECTOR = os.getenv("ENABLE_BACKGROUND_COLLECTOR", "1").lower() in ("1", "true", "yes")
