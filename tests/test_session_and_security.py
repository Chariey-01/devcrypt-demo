"""Area 1 (session reliability) and Area 4 (CSRF/rate limiting) coverage. The main test suite
runs with WTF_CSRF_ENABLED/RATELIMIT_ENABLED off (see conftest.TestConfig) so every other test
file can post like a same-origin fetch() call without a token -- this file spins up its own app
with both re-enabled to verify the protections actually engage."""

import pytest

from app import create_app
from app.extensions import db
from app.models import Team
from tests.conftest import TestConfig


def _login_team(client, name="Alpha", key="ALPHA01"):
    # base_url="https://..." so this helper works unchanged whether or not the app under test
    # has force_https active (the cross-origin-config tests below do, via
    # SESSION_COOKIE_SECURE=True) -- the Werkzeug test client otherwise defaults to plain
    # http://localhost, which Talisman would 302-redirect before the view (and the login) ever
    # runs. Harmless for the default TestConfig too, where force_https is off regardless.
    return client.post(
        "/auth/team-login", data={"name": name, "key": key}, base_url="https://localhost"
    )


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
    token = page[start : page.index('"', start)]

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


def _https_enforced_app():
    class HTTPSEnforcedConfig(TestConfig):
        # Mirrors real production (SESSION_COOKIE_SECURE = not sqlite): this is the exact flag
        # that drives Talisman's force_https, off by default in TestConfig so the rest of the
        # suite can hit routes over plain http without every request 302-redirecting.
        SESSION_COOKIE_SECURE = True

    return create_app(HTTPSEnforcedConfig)


def test_healthz_is_reachable_without_https_redirect():
    # Regression test for a real incident: Railway's healthcheck probes the container directly
    # over plain HTTP (TLS terminates at Railway's edge, never reaching the container), so
    # force_https redirecting /healthz to https instead of returning 200/503 made every
    # deployment fail its healthcheck and get rolled back, even though the app itself was fine.
    app = _https_enforced_app()
    client = app.test_client()
    res = client.get("/healthz")
    assert res.status_code in (200, 503)
    assert "Location" not in res.headers


def test_unexempted_routes_still_redirect_to_https_when_enforced():
    # The other half of the same regression test: proves the /healthz exemption is scoped to
    # that one route only, not a global weakening of force_https for the rest of the app.
    app = _https_enforced_app()
    client = app.test_client()
    res = client.get("/")
    assert res.status_code == 302
    assert res.headers["Location"].startswith("https://")


def test_csrf_token_endpoint_returns_a_usable_token():
    # The Vercel-hosted player dashboard has no Flask-rendered <meta name="csrf-token"> tag to
    # read (that only exists on server-rendered pages) -- it fetches this instead. Proves the
    # token this JSON endpoint issues is interchangeable with the one a rendered page's hidden
    # input carries, since both come from the same session-bound generate_csrf()/csrf_token().
    app = _csrf_enabled_app()
    client = app.test_client()
    token = client.get("/auth/csrf-token").get_json()["csrfToken"]
    assert token

    res = client.post(
        "/auth/team-login", data={"name": "Alpha", "key": "ALPHA01", "csrf_token": token}
    )
    assert res.status_code == 302


def _cross_origin_app():
    class CrossOriginConfig(TestConfig):
        # Explicit overrides, not a re-derivation of app/config.py's conditionals -- same
        # class-body-evaluation-time limitation SESSION_COOKIE_SECURE already works around above.
        SESSION_COOKIE_SECURE = True
        SESSION_COOKIE_SAMESITE = "None"
        ALLOWED_ORIGINS = ["https://devcrypt-player.example.vercel.app"]

    app = create_app(CrossOriginConfig)
    with app.app_context():
        db.create_all()
        team = Team(name="Alpha", score=0, integrity=100)
        team.set_key("ALPHA01")
        db.session.add(team)
        db.session.commit()
    return app


def test_session_cookie_is_samesite_none_under_the_cross_origin_config():
    # Regression test for the Vercel split: without SameSite=None, a cross-origin fetch() from
    # the Vercel-hosted dashboard would never receive the session cookie Flask's own login sets,
    # breaking every authenticated request the React app makes back to this API.
    app = _cross_origin_app()
    client = app.test_client()
    res = _login_team(client)
    assert "SameSite=None" in res.headers.get("Set-Cookie", "")


def test_session_cookie_is_samesite_lax_under_the_default_test_config(client, app):
    with app.app_context():
        team = Team(name="Alpha", score=0, integrity=100)
        team.set_key("ALPHA01")
        db.session.add(team)
        db.session.commit()
    res = _login_team(client)
    assert "SameSite=Lax" in res.headers.get("Set-Cookie", "")


def test_cors_allows_the_configured_origin_on_missions_routes():
    app = _cross_origin_app()
    client = app.test_client()
    _login_team(client)
    origin = "https://devcrypt-player.example.vercel.app"
    res = client.get("/missions/status", headers={"Origin": origin})
    assert res.headers.get("Access-Control-Allow-Origin") == origin
    assert res.headers.get("Access-Control-Allow-Credentials") == "true"


def test_cors_rejects_an_unlisted_origin_on_missions_routes():
    app = _cross_origin_app()
    client = app.test_client()
    _login_team(client)
    res = client.get("/missions/status", headers={"Origin": "https://evil.example.com"})
    assert res.headers.get("Access-Control-Allow-Origin") != "https://evil.example.com"


def test_cors_is_not_applied_to_gm_dashboard_routes():
    # Proves the CORS scope is deliberately narrow (missions + the csrf-token route only), not
    # sitewide -- GM/Agent/Security/mod stay server-rendered, same-origin, no new attack surface.
    app = _cross_origin_app()
    client = app.test_client()
    origin = "https://devcrypt-player.example.vercel.app"
    res = client.get("/mod/", headers={"Origin": origin})
    assert "Access-Control-Allow-Origin" not in res.headers


def test_refuses_to_start_against_postgres_with_insecure_default_secrets():
    # Regression test for a real gap found in the production stabilization audit: SECRET_KEY,
    # EVENT_SALT, and VERCEL_APP_URL all fall back to well-known, non-secret defaults so a fresh
    # local checkout works with zero setup -- exactly the wrong behavior if one is ever left
    # unset in a real deploy. This must fail loudly at boot, not silently serve a guessable
    # secret or send every team's browser to localhost.
    class InsecureProductionConfig(TestConfig):
        SQLALCHEMY_DATABASE_URI = "postgresql://fake:fake@localhost/fake"
        SECRET_KEY = "devcrypt-demo-secret"  # the real Config's own insecure default

    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app(InsecureProductionConfig)


def test_starts_fine_against_postgres_once_real_secrets_are_set():
    # The other half: proves the check is scoped to the specific insecure default values, not
    # "always refuse non-SQLite" -- a real deploy with real secrets must boot normally.
    class RealProductionConfig(TestConfig):
        SQLALCHEMY_DATABASE_URI = "postgresql://fake:fake@localhost/fake"
        SECRET_KEY = "a-real-random-secret"
        EVENT_SALT = "a-real-random-salt"
        VERCEL_APP_URL = "https://devcrypt.vercel.app"

    create_app(RealProductionConfig)  # must not raise
