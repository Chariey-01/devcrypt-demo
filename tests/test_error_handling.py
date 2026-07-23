"""Confirms 401/403 never strand a user on Werkzeug's stock error page — see the
_unauthorized/_forbidden handlers in app/__init__.py. AJAX-style requests (no explicit
text/html Accept, matching how this app's own fetch() calls behave) get a JSON body; a plain
browser navigation gets a friendly, on-brand page."""
from app.extensions import db
from app.models import User


def test_unauthenticated_ajax_request_gets_json_not_html(client):
    res = client.get("/mod/data")
    assert res.status_code == 401
    assert res.get_json() is not None
    assert "session" in res.get_json()["error"].lower()


def test_unauthenticated_page_navigation_redirects_to_login_with_flash(client):
    res = client.get("/mod/data", headers={"Accept": "text/html"})
    assert res.status_code == 302
    assert res.headers["Location"].endswith("/auth/login")


def test_wrong_role_ajax_request_gets_json_403(client, app):
    with app.app_context():
        agent = User(email="agent@test.local", role="booth_agent")
        agent.set_password("pw")
        db.session.add(agent)
        db.session.commit()
    client.post("/auth/login", data={"email": "agent@test.local", "password": "pw"})

    res = client.get("/mod/data")
    assert res.status_code == 403
    assert res.get_json() is not None


def test_wrong_role_page_navigation_gets_friendly_error_page_not_werkzeug_default(client, app):
    with app.app_context():
        agent = User(email="agent@test.local", role="booth_agent")
        agent.set_password("pw")
        db.session.add(agent)
        db.session.commit()
    client.post("/auth/login", data={"email": "agent@test.local", "password": "pw"})

    res = client.get("/mod/data", headers={"Accept": "text/html"})
    assert res.status_code == 403
    body = res.get_data(as_text=True)
    assert "Access Denied" in body
    assert "Internal Server Error" not in body
    # Not Werkzeug's stock page — that one's body is literally "<title>403 Forbidden</title>".
    assert "<title>403 Forbidden</title>" not in body
