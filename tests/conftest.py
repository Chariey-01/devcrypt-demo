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
