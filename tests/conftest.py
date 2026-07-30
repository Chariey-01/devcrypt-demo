import pytest

from app import create_app
from app.config import Config, engine_options_for
from app.extensions import db
from app.models import User


class TestConfig(Config):
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
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


@pytest.fixture
def app():
    application = create_app(TestConfig)
    # create_app() no longer creates tables itself (that unconditional call raced Flask-Migrate
    # in production — see app/__init__.py). Tests own their schema setup directly instead, same
    # as seed.py already does for the local demo DB.
    with application.app_context():
        db.create_all()
    yield application


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
