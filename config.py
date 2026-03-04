import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DATABASE_PATH = os.getenv("MATCHBOX_DB_PATH", str(DATA_DIR / "matchbox.db"))
HOST = os.getenv("MATCHBOX_HOST", "0.0.0.0")
PORT = int(os.getenv("MATCHBOX_PORT", "8000"))

# Auth
SECRET_KEY = os.getenv("MATCHBOX_SECRET_KEY", secrets.token_hex(32))
SESSION_EXPIRY_HOURS = int(os.getenv("MATCHBOX_SESSION_EXPIRY_HOURS", "72"))

# Seed admin (used on first run only)
ADMIN_EMAIL = os.getenv("MATCHBOX_ADMIN_EMAIL", "")
ADMIN_PASSWORD = os.getenv("MATCHBOX_ADMIN_PASSWORD", "")
