import os

import pytest

from app import create_app
from app.config import Config, engine_options_for
from app.extensions import db
from app.models import User


class TestConfig(Config):
    # Defaults to the fast in-memory SQLite every local `pytest` run has always used --
    # TEST_DATABASE_URL is only set in CI's test-backend-postgres job (a postgres:16 service
    # container), so this same suite also runs against real Postgres there. That job exists
    # because a past incident (AdminResetService's bulk-delete bypassing cascade behavior) only
    # broke on Postgres's real FK enforcement and passed every local SQLite test.
    SQLALCHEMY_DATABASE_URI = os.environ.get("TEST_DATABASE_URL", "sqlite:///:memory:")
    SQLALCHEMY_ENGINE_OPTIONS = engine_options_for(SQLALCHEMY_DATABASE_URI)
    SECRET_KEY = "test-secret"
    EVENT_SALT = "test-salt"
    # Explicitly unset regardless of the developer's local .env -- Config.FINAL_FLAG_CIPHERTEXT/
    # FINAL_FLAG_MISSION_IDS are read from os.getenv() at class-body time, so without this
    # override, a developer's local final-flag QA setup would silently leak into every test run
    # (see test_final_flag_not_configured_returns_404, which specifically asserts the unset case).
    FINAL_FLAG_CIPHERTEXT = None
    FINAL_FLAG_MISSION_IDS = []
    # The test client posts forms/JSON directly, with no browser-driven CSRF-token round trip
    # and no real per-client IP to rate-limit against -- both are exercised by their own
    # dedicated tests (test_csrf.py, test_rate_limiting.py) using an app instance that
    # re-enables them explicitly. Standard Flask-WTF/Flask-Limiter testing practice.
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False
    # Config.SESSION_COOKIE_SECURE is computed once, at Config's own class-body evaluation time,
    # from *its* SQLALCHEMY_DATABASE_URI (i.e. whatever DATABASE_URL is in the developer's local
    # .env -- often a real Postgres URL for local QA against a shared dev DB). Overriding
    # SQLALCHEMY_DATABASE_URI here to sqlite (above) does NOT retroactively recompute that
    # inherited class attribute, so without this explicit override tests would inherit
    # SESSION_COOKIE_SECURE=True from whatever the developer's .env happens to point at --
    # and Talisman's force_https (app/__init__.py) is keyed off exactly this flag, which was
    # 302-redirecting every plain-http test-client request before this line was added.
    SESSION_COOKIE_SECURE = False
    # Same class-body-evaluation-time gotcha as SESSION_COOKIE_SECURE above, for the same
    # reason: Config.SESSION_COOKIE_SAMESITE is computed once from *Config's own*
    # SQLALCHEMY_DATABASE_URI, not TestConfig's overridden one. Without this, a developer with a
    # real Postgres DATABASE_URL in their local .env would inherit SameSite=None here, which
    # Werkzeug's test client (plain http) silently drops -- session cookies would stop being
    # sent between requests in the same test, breaking anything that logs in and then acts.
    SESSION_COOKIE_SAMESITE = "Lax"


@pytest.fixture
def app():
    application = create_app(TestConfig)
    # create_app() no longer creates tables itself (that unconditional call raced Flask-Migrate
    # in production — see app/__init__.py). Tests own their schema setup directly instead, same
    # as seed.py already does for the local demo DB.
    with application.app_context():
        db.create_all()
    yield application
    # In-memory SQLite is already a blank slate per test (a fresh engine = a fresh :memory: DB),
    # but TEST_DATABASE_URL pointed at a real, persistent Postgres container (CI's
    # test-backend-postgres job) would otherwise leak rows from one test into the next. Cheap
    # and harmless for the SQLite case, required for correctness in the Postgres one.
    with application.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def two_agents(app):
    with app.app_context():
        agent_a = User(email="agent-a@test.local", role="booth_agent")
        agent_a.set_password("pw")
        agent_b = User(email="agent-b@test.local", role="booth_agent")
        agent_b.set_password("pw")
        db.session.add_all([agent_a, agent_b])
        db.session.commit()
        return agent_a.id, agent_b.id
