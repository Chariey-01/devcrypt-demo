# Must run before `from app import create_app` so app/__init__.py's monkey-patch check sees
# gevent already active during local dev too — otherwise local testing wouldn't exercise the
# same runtime as production (gunicorn -k gevent) and could pass locally while stalling on
# event day. `flask run`/`flask --app run.py run` never executes the block below, so it would
# silently skip this and Socket.IO would fall back to plain long-polling — use `python3 run.py`.
from gevent import monkey

monkey.patch_all()

from app import create_app  # noqa: E402 — must come after monkey.patch_all(), see comment above
from app.extensions import socketio  # noqa: E402

app = create_app()

if __name__ == "__main__":
    # use_reloader=False: Werkzeug's debug reloader re-execs the process, which trips gevent's
    # monkey-patched threading fork hooks (AssertionError in _ForkHooks.after_fork_in_child) and
    # the dev server never actually binds. debug=True still gives in-browser tracebacks; you
    # just restart `python3 run.py` by hand after an edit instead of it auto-reloading.
    socketio.run(app, host="0.0.0.0", port=5000, debug=True, use_reloader=False)
