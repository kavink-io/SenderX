import os
import sys

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app import create_app

app = create_app()

celery = app.celery


if __name__ == "__main__":
    print(f"Starting {app.config.get('APP_NAME', 'SenderX')} on http://127.0.0.1:5000 ...", flush=True)
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True,
        use_reloader=False
    )
