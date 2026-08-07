# If launched via `gunicorn -k gevent` (or the local `python3 run.py` dev entrypoint), gevent's
# monkey-patching has already run by the time this module is imported — gunicorn's own
# GeventWorker.patch() calls monkey.patch_all() before loading the app. That patching does NOT
# cover psycopg2 — without green-patching it too, a blocking libpq call from inside the single
# gevent process would stall every open WebSocket/request for the query's duration, silently
# defeating the whole point of the async worker. No-op under pytest/plain `flask run` (never
# monkey-patched there), so this is safe everywhere.
try:
    from gevent import monkey

    if monkey.is_module_patched("socket"):
        import psycogreen.gevent

        psycogreen.gevent.patch_psycopg()
except ImportError:
    pass

import logging
import os

from flask import Flask, render_template
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix

from . import sockets  # noqa: F401 — registers the @socketio.on("connect") handler
from .blueprints.agent import agent_bp
from .blueprints.auth import auth_bp
from .blueprints.cipher import cipher_bp
from .blueprints.leaderboard import leaderboard_bp
from .blueprints.missions import missions_bp
from .blueprints.mod import mod_bp
from .blueprints.portals import portals_bp
from .blueprints.scoring import scoring_bp
from .blueprints.security import security_bp
from .config import Config
from .errors import register_error_handlers
from .extensions import bcrypt, csrf, db, limiter, login_manager, migrate, socketio, talisman
from .icons import icon


def _configure_logging():
    # logging.basicConfig() is a no-op once the root logger already has a handler — safe to call
    # on every create_app() (tests construct the app repeatedly) without stacking duplicate
    # handlers. This also means Flask's own default exception logging (unhandled 500s, logged via
    # app.logger.error(..., exc_info=...) in Flask's handle_exception) picks up this format/level
    # for free, since Flask only attaches its own default handler when no handler is found
    # anywhere up the logger chain.
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def create_app(config_class=Config):
    _configure_logging()
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Railway (and any platform fronting the app with a TLS-terminating proxy) sits in front of
    # this single gunicorn worker, so request.remote_addr would otherwise always be the proxy's
    # own IP — wrong for both audit-log IP capture (app/services/audit_service.py) and
    # rate-limit keying (Flask-Limiter, below). x_for=1 trusts exactly one hop of
    # X-Forwarded-For, matching Railway's single reverse-proxy topology.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1)  # type: ignore[method-assign]

    db.init_app(app)
    if app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite"):
        # SQLite does not enforce foreign key constraints by default, unlike Postgres (what
        # actually runs in production). Without this, a bug that violates a real FK constraint
        # — like AdminResetService's bulk-delete-bypasses-cascade incident, caught live against
        # production Postgres after passing every local test — passes silently here too, and the
        # first place it's ever actually caught is production. This makes local/test behavior
        # match production's real constraint enforcement instead of being quietly more lenient.
        from sqlalchemy import event
        from sqlalchemy.engine import Engine

        @event.listens_for(Engine, "connect")
        def _enable_sqlite_foreign_keys(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    migrate.init_app(app, db)
    socketio.init_app(app, cors_allowed_origins=app.config["SOCKETIO_CORS_ALLOWED_ORIGINS"])
    bcrypt.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)
    talisman.init_app(
        app,
        # Mirrors the same SQLite(local/LAN)-vs-Postgres(production) split already used by
        # SESSION_COOKIE_SECURE — forcing HTTPS on the venue's plain-HTTP LAN demo path would
        # break every team/staff login there.
        force_https=app.config["SESSION_COOKIE_SECURE"],
        session_cookie_secure=app.config["SESSION_COOKIE_SECURE"],
        # Talisman defaults this to "Lax" and applies it by overwriting
        # app.config["SESSION_COOKIE_SAMESITE"] unconditionally at init time -- without this
        # explicit pass-through, it silently clobbers the SameSite=None the Vercel split needs
        # in production, regardless of what Config computed.
        session_cookie_samesite=app.config["SESSION_COOKIE_SAMESITE"],
        content_security_policy={
            "default-src": "'self'",
            "script-src": "'self'",
            # Inline style="" attributes and JS-set progress-bar widths are used throughout the
            # templates -- eliminating them is a larger CSS refactor, deliberately out of scope
            # here. script-src above stays strict with zero exceptions instead.
            "style-src": ["'self'", "'unsafe-inline'"],
            "img-src": ["'self'", "data:"],  # data: URIs used by generate_credential's QR PNG
            "connect-src": "'self'",
        },
    )

    # Only the player-facing JSON API needs to answer a cross-origin browser: the React
    # dashboard is now a standalone app on Vercel (see frontend/), calling back to this API
    # with credentials included. Every other blueprint (GM/Agent/Security/mod) stays
    # server-rendered and same-origin, so it's deliberately not in this resources map at all --
    # narrower than a sitewide CORS() call, and correctly re-reads app.config on every
    # create_app() call (including TestConfig in tests), unlike binding CORS to a blueprint
    # object at import time would.
    CORS(
        app,
        resources={
            r"/missions/*": {
                "origins": app.config["ALLOWED_ORIGINS"],
                "supports_credentials": True,
            },
            r"/auth/csrf-token": {
                "origins": app.config["ALLOWED_ORIGINS"],
                "supports_credentials": True,
            },
        },
    )

    app.jinja_env.globals["icon"] = icon

    app.register_blueprint(auth_bp)
    app.register_blueprint(missions_bp)
    app.register_blueprint(scoring_bp)
    app.register_blueprint(cipher_bp)
    app.register_blueprint(leaderboard_bp)
    app.register_blueprint(mod_bp)
    app.register_blueprint(security_bp)
    app.register_blueprint(portals_bp)
    app.register_blueprint(agent_bp)

    @login_manager.user_loader
    def load_user(user_id):
        from .models import User

        return User.query.get(int(user_id))

    register_error_handlers(app)

    @app.route("/")
    def home():
        return render_template("index.html")

    @app.route("/healthz")
    # Railway's healthcheck probes the container directly over plain HTTP -- TLS terminates at
    # Railway's edge, never reaching the container itself -- so force_https (correctly enforced
    # for every real, proxied request via Talisman's own X-Forwarded-Proto check) would otherwise
    # 302-redirect the healthcheck instead of returning 200, and Railway tears the deployment
    # down as unhealthy. This is Flask-Talisman's own documented per-view exemption mechanism,
    # scoped to exactly this route -- everything else keeps full HTTPS enforcement. /healthz
    # returns no session cookie and no user data, so there is nothing here for HTTPS to protect.
    @talisman(force_https=False)
    def healthz():
        # Round-trips the DB so a monitor/uptime-pinger catches a dead connection pool or a
        # sleeping free-tier host, not just "the process is technically still running."
        from sqlalchemy import text

        try:
            db.session.execute(text("SELECT 1"))
            return {"status": "ok"}, 200
        except Exception as exc:
            return {"status": "error", "detail": str(exc)}, 503

    # No unconditional db.create_all() here. It used to run on every boot for zero-setup local
    # demos, but that silently races Flask-Migrate: `flask db upgrade` loads this module (to
    # discover the `app` object) before Alembic's own CREATE TABLE statements run, so create_all()
    # would already have created every table from current models.py — then the migration's own
    # `CREATE TABLE`/`ADD COLUMN` fails with "already exists" on a genuinely fresh database.
    # Confirmed live: `flask db upgrade` against an empty SQLite file crashed exactly this way.
    # Schema creation is now each caller's explicit responsibility: seed.py calls db.create_all()
    # itself (already documented as the mandatory first local-demo step in DEPLOYMENT.md),
    # tests/conftest.py's `app` fixture does the same for its in-memory DB, and production is
    # expected to run `flask db upgrade` — the only mechanism that can also ALTER an existing
    # table, which create_all() was never able to do anyway.
    return app
