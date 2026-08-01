import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def _normalize_db_url(url):
    # SQLAlchemy 2.x requires the "postgresql://" scheme; some providers
    # (Heroku-style convention) still hand out "postgres://".
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://") :]
    return url


def engine_options_for(db_url):
    # SQLite (the local demo / test path) uses StaticPool/NullPool under the hood and errors
    # out on QueuePool-only kwargs like pool_size/max_overflow, so those are Postgres-only.
    if db_url.startswith("sqlite"):
        return {}
    # Managed Postgres (Supabase/Render/Railway free & low tiers) drops idle connections
    # after a few minutes. Without pool_pre_ping, the next query on a dead connection raises
    # OperationalError instead of transparently reconnecting — the classic "worked all through
    # setup, then 500s mid-event after a quiet stretch between booth visits" failure.
    #
    # pool_size/max_overflow: the Procfile runs a single gevent worker (-w 1 -k gevent, needed
    # for real WebSocket support — see app/sockets.py), so there is exactly one process and
    # therefore exactly one connection pool, shared by every concurrent greenthread (HTTP
    # requests, poll responses, socket connect handlers, and the pre/post-grading DB writes).
    # Grading itself no longer holds a connection during the up-to-30s test run — that's a
    # subprocess call (app/services/grading_service.py), not a DB operation — so connections
    # are only held briefly for the CodeSubmission insert and the completion commit. 20 total
    # (10 + 10) was load-tested (loadtest.py) against 50 teams submitting simultaneously with
    # zero connection-pool errors — see DEPLOYMENT.md's "Surviving a live event" for the actual
    # numbers. Re-check against whatever Postgres plan is actually provisioned before the event
    # if the worker count in the Procfile ever changes, or re-run loadtest.py to confirm.
    return {
        "pool_pre_ping": True,
        "pool_recycle": 280,
        "pool_size": 10,
        "max_overflow": 10,
    }


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "devcrypt-demo-secret")
    SQLALCHEMY_DATABASE_URI = _normalize_db_url(
        os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'devcrypt.db'}")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = engine_options_for(SQLALCHEMY_DATABASE_URI)
    EVENT_SALT = os.getenv("EVENT_SALT", "devcrypt-demo-event-salt")

    # Slightly above the 5MB evidence-file cap enforced in app/blueprints/agent.py, leaving
    # headroom for multipart form overhead -- lets Flask reject an oversized upload before
    # buffering the whole thing into memory.
    MAX_CONTENT_LENGTH = 6 * 1024 * 1024

    # Server-only final-flag material — see app/services/final_flag_service.py and
    # scripts/derive_final_flag.py. Never set in seed data, never committed, never sent to the
    # client except via the one gated route once a team has actually finished every vault.
    FINAL_FLAG_CIPHERTEXT = os.getenv("FINAL_FLAG_CIPHERTEXT") or None
    # Comma-separated Mission ids that must ALL be passed to unlock the flag — fixed at whatever
    # set derive_final_flag.py was run against, deliberately NOT "every currently published
    # mission" (that would silently change the master key, and therefore break decryption of an
    # already-generated ciphertext, the moment a mission is added/removed/republished later).
    FINAL_FLAG_MISSION_IDS = [
        int(x) for x in (os.getenv("FINAL_FLAG_MISSION_IDS") or "").split(",") if x.strip()
    ]

    # A team refreshing, closing a tab, or dropping WiFi mid-event must never be forced back to
    # a moderator for a new key — all real progress is already server-side (Postgres). Default
    # 8h comfortably spans a one-day event; override per-event via env without a redeploy.
    PERMANENT_SESSION_LIFETIME = timedelta(hours=int(os.getenv("SESSION_LIFETIME_HOURS", "8")))

    # Flask-WTF's default (1hr) would expire a CSRF token on a team's tab left open mid-event —
    # tie validity to the session lifetime above instead of a fixed short window.
    WTF_CSRF_TIME_LIMIT = None

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    # Secure cookies are only sent over HTTPS. The local demo path (SQLite, per DEPLOYMENT.md)
    # deliberately runs over plain HTTP on the venue LAN with no TLS — forcing Secure there would
    # silently break every team/staff login. Production (Postgres, per DEPLOYMENT.md's Railway/
    # Render instructions) always gets HTTPS from the platform's TLS termination, so it's safe —
    # and worth enforcing — to require Secure there. Same SQLite-vs-Postgres signal already used
    # by engine_options_for() above, not a new env var.
    SESSION_COOKIE_SECURE = not SQLALCHEMY_DATABASE_URI.startswith("sqlite")

    # Socket.IO's handshake carries the session cookie like any other request, so an overly
    # permissive CORS setting here would let a third-party site open a session-authenticated
    # WebSocket connection on a logged-in visitor's behalf. Low actual impact today (every
    # push payload is a stateless {"type": "..."} ping, never a score/flag/fragment — see
    # app/sockets.py), but tightened anyway as defense in depth. Unset (local demo, LAN IP
    # varies per laptop) falls back to "*"; set ALLOWED_ORIGIN to the real deployed URL
    # (e.g. https://devcrypt.up.railway.app) for production.
    SOCKETIO_CORS_ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGIN", "*")
