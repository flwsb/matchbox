import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DATABASE_PATH = os.getenv("MATCHBOX_DB_PATH", str(DATA_DIR / "matchbox.db"))
HOST = os.getenv("MATCHBOX_HOST", "0.0.0.0")
PORT = int(os.getenv("MATCHBOX_PORT", "8000"))
