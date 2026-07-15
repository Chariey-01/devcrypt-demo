from flask_login import current_user
from flask_socketio import join_room

from .decorators import current_team
from .extensions import socketio

# Push-triggers-refresh, not push-carries-state: every emit below is a bare "something changed,
# go refetch" ping with no game-state payload. The browser responds by calling the exact same
# refresh() function its poll loop already calls (app/static/app.js, mod_admin.js) — so there is
# no second rendering/serialization path to keep in sync with the REST endpoints, and no way for
# a socket payload to leak anything those endpoints already filter (hidden test cases,
# solution_code, another team's cipher_value). A dropped WebSocket just means the existing poll
# loop keeps everyone current until it reconnects, exactly the fallback SYSTEM.md sec.6 promises.


@socketio.on("connect")
def handle_connect():
    team = current_team()
    if team:
        join_room(f"team-{team.id}")
    if current_user.is_authenticated and current_user.role == "game_master":
        join_room("mod")


def notify_team(team_id, event_type):
    socketio.emit("team_update", {"type": event_type}, room=f"team-{team_id}")


def notify_mod(event_type):
    socketio.emit("mod_update", {"type": event_type}, room="mod")


def notify_global(event_type):
    socketio.emit("event_update", {"type": event_type})
