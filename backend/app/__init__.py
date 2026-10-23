import atexit
from flask import Flask, request, jsonify, make_response
from app.config import Config
from app.api.routes import api_bp
from app.storage.database import Database
from app.services.background_collector import background_collector

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize SQLite schema
    db_path = app.config.get("DB_PATH")
    if db_path:
        try:
            Database(db_path)
        except Exception as e:
            app.logger.error(f"Failed to initialize SQLite database at {db_path}: {e}")

    # Register API blueprint
    app.register_blueprint(api_bp)

    # Start background metric collector (respects testing/reloader guards)
    if app.config.get("ENABLE_BACKGROUND_COLLECTOR", True):
        background_collector.start(app.config)
        atexit.register(background_collector.stop)

    # Top-level health probe
    @app.route("/healthz", methods=["GET"])
    def healthz():
        return jsonify({"status": "ok"}), 200

    # Development CORS handler
    @app.before_request
    def handle_preflight():
        if request.method == "OPTIONS":
            response = make_response("", 204)
            origin = request.headers.get("Origin")
            allowed_origins = app.config.get("CORS_ORIGINS", [])
            allow_all = app.config.get("CORS_ALLOW_ALL", False)

            if allow_all:
                response.headers["Access-Control-Allow-Origin"] = "*"
            elif origin and origin in allowed_origins:
                response.headers["Access-Control-Allow-Origin"] = origin

            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With"
            return response

    @app.after_request
    def add_cors_headers(response):
        origin = request.headers.get("Origin")
        allowed_origins = app.config.get("CORS_ORIGINS", [])
        allow_all = app.config.get("CORS_ALLOW_ALL", False)

        if allow_all:
            response.headers["Access-Control-Allow-Origin"] = "*"
        elif origin and origin in allowed_origins:
            response.headers["Access-Control-Allow-Origin"] = origin

        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With"
        return response

    return app
