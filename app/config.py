import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "devcrypt-demo-secret")
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{BASE_DIR / 'devcrypt.db'}",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    EVENT_SALT = os.getenv("EVENT_SALT", "devcrypt-demo-event-salt")
