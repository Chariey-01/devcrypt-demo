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

from flask import Flask, render_template

from .config import Config
from .extensions import bcrypt, db, login_manager, migrate, socketio
from .blueprints.auth import auth_bp
from .blueprints.missions import missions_bp
from .blueprints.scoring import scoring_bp
from .blueprints.cipher import cipher_bp
from .blueprints.leaderboard import leaderboard_bp
from .blueprints.mod import mod_bp
from .blueprints.booth import booth_bp
from .blueprints.security import security_bp
from .blueprints.portals import portals_bp
from .blueprints.agent import agent_bp
from .icons import icon
from . import sockets  # noqa: F401 — registers the @socketio.on("connect") handler


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    socketio.init_app(app, cors_allowed_origins=app.config["SOCKETIO_CORS_ALLOWED_ORIGINS"])
    bcrypt.init_app(app)
    login_manager.init_app(app)

    app.jinja_env.globals["icon"] = icon

    app.register_blueprint(auth_bp)
    app.register_blueprint(missions_bp)
    app.register_blueprint(scoring_bp)
    app.register_blueprint(cipher_bp)
    app.register_blueprint(leaderboard_bp)
    app.register_blueprint(mod_bp)
    app.register_blueprint(booth_bp)
    app.register_blueprint(security_bp)
    app.register_blueprint(portals_bp)
    app.register_blueprint(agent_bp)

    @login_manager.user_loader
    def load_user(user_id):
        from .models import User

        return User.query.get(int(user_id))

    @app.route("/")
    def home():
        return render_template("index.html")

    @app.route("/healthz")
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
