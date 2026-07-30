"""Area 1 (session reliability) and Area 4 (CSRF/rate limiting) coverage. The main test suite
runs with WTF_CSRF_ENABLED/RATELIMIT_ENABLED off (see conftest.TestConfig) so every other test
file can post like a same-origin fetch() call without a token -- this file spins up its own app
with both re-enabled to verify the protections actually engage."""
from app import create_app
from app.extensions import db
from app.models import Team, User
from tests.conftest import TestConfig


def _login_team(client, name="Alpha", key="ALPHA01"):
    return client.post("/auth/team-login", data={"name": name, "key": key})


def test_team_session_survives_a_simulated_browser_restart(client, app):
    # session.permanent = True (set on login) is what makes the cookie outlive the browser
    # session instead of dying the moment the tab/browser closes -- this is the actual behavior
    # a team relies on to never need a moderator-issued replacement key over a refresh/restart.
    with app.app_context():
        team = Team(name="Alpha", score=0, integrity=100)
        team.set_key("ALPHA01")
        db.session.add(team)
        db.session.commit()

    _login_team(client)
    with client.session_transaction() as sess:
        assert sess.permanent is True


def test_deleted_team_session_gets_a_clean_401_not_a_crash(client, app):
    # Simulates the actual failure mode team_required now guards against: a cookie referencing
    # a team_id that no longer resolves (deleted team, or a stale/forged value).
    with client.session_transaction() as sess:
        sess["team_id"] = 999999

    res = client.get("/missions/status")
    assert res.status_code == 401
    assert "expired" in res.get_json()["error"].lower()
    with client.session_transaction() as sess:
        assert "team_id" not in sess


def test_deleted_team_session_navigation_redirects_to_team_login(client, app):
    with client.session_transaction() as sess:
        sess["team_id"] = 999999

    res = client.get("/missions/play", headers={"Accept": "text/html"})
    assert res.status_code == 302
    assert res.headers["Location"].endswith("/auth/team-login")


def _csrf_enabled_app():
    class CSRFEnabledConfig(TestConfig):
        WTF_CSRF_ENABLED = True

    app = create_app(CSRFEnabledConfig)
    with app.app_context():
        db.create_all()
        team = Team(name="Alpha", score=0, integrity=100)
        team.set_key("ALPHA01")
        db.session.add(team)
        db.session.commit()
    return app


def test_post_without_csrf_token_is_rejected():
    app = _csrf_enabled_app()
    client = app.test_client()
    res = client.post("/auth/team-login", data={"name": "Alpha", "key": "ALPHA01"})
    assert res.status_code == 400


def test_post_with_csrf_token_from_the_page_succeeds():
    app = _csrf_enabled_app()
    client = app.test_client()
    page = client.get("/auth/team-login").get_data(as_text=True)
    start = page.index('name="csrf_token" value="') + len('name="csrf_token" value="')
    token = page[start:page.index('"', start)]

    res = client.post(
        "/auth/team-login", data={"name": "Alpha", "key": "ALPHA01", "csrf_token": token}
    )
    assert res.status_code == 302


def _rate_limited_app():
    class RateLimitedConfig(TestConfig):
        RATELIMIT_ENABLED = True

    app = create_app(RateLimitedConfig)
    with app.app_context():
        db.create_all()
        team = Team(name="Alpha", score=0, integrity=100)
        team.set_key("ALPHA01")
        db.session.add(team)
        db.session.commit()
    return app


def test_repeated_failed_team_logins_are_rate_limited():
    app = _rate_limited_app()
    client = app.test_client()
    statuses = [
        client.post("/auth/team-login", data={"name": "Alpha", "key": "wrong"}).status_code
        for _ in range(15)
    ]
    assert 429 in statuses
