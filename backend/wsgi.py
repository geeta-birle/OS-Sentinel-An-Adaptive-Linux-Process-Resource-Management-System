"""
OS Sentinel - Production WSGI Application Entry Point
Suitable for deployment under Gunicorn (Linux/WSL2), Waitress (Windows/Linux), or uWSGI.
"""
import os
from app import create_app
from app.config import Config

class ProductionConfig(Config):
    DEBUG = False
    ENV = "production"

application = create_app(ProductionConfig)
app = application

if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "5000"))
    # Try waitress if available for production serving on Windows/Linux
    try:
        from waitress import serve
        print(f"Serving OS Sentinel via Waitress WSGI on http://{host}:{port}")
        serve(application, host=host, port=port)
    except ImportError:
        print(f"Starting OS Sentinel via standard WSGI runner on http://{host}:{port} (Debug: False)")
        application.run(host=host, port=port, debug=False)
