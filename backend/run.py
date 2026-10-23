import os
from app import create_app
from app.config import Config

app = create_app(Config)

if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "0").lower() in ("1", "true", "yes")
    print(f"Starting OS Sentinel Backend on http://{host}:{port} (Debug: {debug})")
    if debug:
        print("WARNING: Flask debug mode is enabled. Do not use in production.")
    app.run(host=host, port=port, debug=debug)
