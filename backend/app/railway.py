"""Run the Railway API and worker together on a shared document volume."""

import os
import subprocess
import sys
import time

def main():
    python = sys.executable
    os.environ["AUTO_CREATE_SCHEMA"] = "0"
    # Render secret files can be uploaded from Windows with CRLF line endings.
    for name in ("DATABASE_URL", "SESSION_SECRET", "REVIEWER_PASSWORD"):
        if name in os.environ:
            os.environ[name] = os.environ[name].rstrip(chr(13))
    if not os.environ.get("DATABASE_URL"):
        raise RuntimeError("Set DATABASE_URL to the hosted PostgreSQL connection URL.")
    if not os.environ.get("SESSION_SECRET"):
        raise RuntimeError("Set SESSION_SECRET to a persistent random value.")
    subprocess.run([python, "-m", "backend.app.migrate"], check=True)
    api = subprocess.Popen([python, "-m", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0",
                            "--port", os.getenv("PORT", "8000")])
    worker = subprocess.Popen([python, "-m", "backend.app.worker"])
    try:
        while api.poll() is None and worker.poll() is None:
            time.sleep(1)
        return 1
    finally:
        for process in (api, worker):
            if process.poll() is None:
                process.terminate()
        for process in (api, worker):
            process.wait()

if __name__ == "__main__":
    raise SystemExit(main())
