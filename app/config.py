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
    # The React player dashboard is hosted cross-origin on Vercel, so the session cookie set by
    # Flask's own (same-origin) login must still be sendable on the fetch() calls it makes back
    # to this API -- SameSite=Lax blocks that for anything but a top-level navigation. Only
    # needed in production (where the cross-origin split actually exists); local dev stays
    # same-origin (Flask + a local Vite dev server) and keeps the stricter Lax default. Same
    # SQLite-vs-Postgres signal already used by engine_options_for()/SESSION_COOKIE_SECURE below
    # -- SameSite=None is silently ignored by browsers without Secure=True anyway, so this can
    # never end up None over plain HTTP.
    SESSION_COOKIE_SAMESITE = "Lax" if SQLALCHEMY_DATABASE_URI.startswith("sqlite") else "None"
    # Secure cookies are only sent over HTTPS. The local demo path (SQLite, per DEPLOYMENT.md)
    # deliberately runs over plain HTTP on the venue LAN with no TLS — forcing Secure there would
    # silently break every team/staff login. Production (Postgres, per DEPLOYMENT.md's Railway/
    # Render instructions) always gets HTTPS from the platform's TLS termination, so it's safe —
    # and worth enforcing — to require Secure there. Same SQLite-vs-Postgres signal already used
    # by engine_options_for() above, not a new env var.
    SESSION_COOKIE_SECURE = not SQLALCHEMY_DATABASE_URI.startswith("sqlite")

    # Single source of truth for every cross-origin trust decision this app makes: Socket.IO's
    # CORS (below), the REST CORS applied to the player-facing blueprints (app/__init__.py), and
    # nothing else -- GM/Agent/Security/mod stay server-rendered, same-origin, and never consult
    # this. Comma-separated so local Vite dev (http://localhost:5173) and the production Vercel
    # domain can both be trusted at once without two separate env vars. Unset falls back to "*"
    # (local demo, LAN IP varies per laptop); set ALLOWED_ORIGIN to the real Vercel URL(s) for
    # production, e.g. "https://devcrypt.vercel.app".
    _allowed_origin_env = os.getenv("ALLOWED_ORIGIN", "*")
    ALLOWED_ORIGINS = (
        "*"
        if _allowed_origin_env == "*"
        else [origin.strip() for origin in _allowed_origin_env.split(",") if origin.strip()]
    )

    # Socket.IO's handshake carries the session cookie like any other request, so an overly
    # permissive CORS setting here would let a third-party site open a session-authenticated
    # WebSocket connection on a logged-in visitor's behalf. Low actual impact today (every
    # push payload is a stateless {"type": "..."} ping, never a score/flag/fragment — see
    # app/sockets.py), but tightened anyway as defense in depth.
    SOCKETIO_CORS_ALLOWED_ORIGINS = ALLOWED_ORIGINS

    # Where an authenticated team lands after /missions/play -- the standalone Vite/React app,
    # no longer served by Flask itself. Defaults to Vite's own local dev server port so local
    # development keeps working without an env var; must be set to the real Vercel production
    # URL in production.
    VERCEL_APP_URL = os.getenv("VERCEL_APP_URL", "http://localhost:5173")


# Fallback values above exist so a fresh local checkout runs with zero setup -- exactly the
# wrong behavior in production, where an unset env var should fail loudly at boot, not silently
# serve a known, guessable secret (SECRET_KEY/EVENT_SALT) or redirect every team to localhost
# (VERCEL_APP_URL). Checked once, in create_app(), against the same SQLite-vs-Postgres signal
# used throughout this file rather than a new env var of its own.
INSECURE_PRODUCTION_DEFAULTS = {
    "SECRET_KEY": "devcrypt-demo-secret",
    "EVENT_SALT": "devcrypt-demo-event-salt",
    "VERCEL_APP_URL": "http://localhost:5173",
}


def fail_if_production_secrets_are_unset(app):
    if app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite"):
        return  # local/demo path -- these fallbacks are the whole point there
    unset = [
        name
        for name, insecure_value in INSECURE_PRODUCTION_DEFAULTS.items()
        if app.config.get(name) == insecure_value
    ]
    if unset:
        raise RuntimeError(
            "Refusing to start against a non-SQLite database with insecure default value(s) "
            f"still set for: {', '.join(unset)}. Set real values via environment variables "
            "before deploying -- see docs/DEPLOYMENT_CHECKLIST.md."
        )
