import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _normalize_db_url(url):
    # SQLAlchemy 2.x requires the "postgresql://" scheme; some providers
    # (Heroku-style convention) still hand out "postgres://".
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://"):]
    return url


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "devcrypt-demo-secret")
    SQLALCHEMY_DATABASE_URI = _normalize_db_url(
        os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'devcrypt.db'}")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    EVENT_SALT = os.getenv("EVENT_SALT", "devcrypt-demo-event-salt")
