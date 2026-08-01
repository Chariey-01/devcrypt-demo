import logging

from flask import request
from flask_login import current_user
from flask_socketio import join_room

from .decorators import current_team
from .extensions import socketio

logger = logging.getLogger("devcrypt.sockets")

# Push-triggers-refresh, not push-carries-state: every emit below is a bare "something changed,
# go refetch" ping with no game-state payload. The browser responds by calling the exact same
# refresh() function its poll loop already calls (app/static/app.js, mod_admin.js) — so there is
# no second rendering/serialization path to keep in sync with the REST endpoints, and no way for
# a socket payload to leak anything those endpoints already filter (hidden test cases,
# solution_code, another team's cipher_value). A dropped WebSocket just means the existing poll
# loop keeps everyone current until it reconnects, exactly the fallback SYSTEM.md sec.6 promises.


def _resolve_event_id():
    # A logged-in team's own event_id is authoritative for itself, regardless of which event
    # is currently "active" -- a team's session stays meaningful even if the GM has moved on to
    # publishing a different event. Staff and anonymous connections (e.g. the public
    # leaderboard) have no per-connection event of their own yet -- Phase 1c's event switcher
    # will set session["event_id"] for staff who manage more than one event; until then (and
    # for staff/anonymous connections generally), the currently active event is correct, since
    # it's the only one that's ever publicly relevant.
    team = current_team()
    if team:
        return team.event_id
    if current_user.is_authenticated and current_user.event_id:
        return current_user.event_id
    from .services.event_service import EventService  # local import: avoids a circular import

    return EventService().get_active_event().id


@socketio.on("connect")
def handle_connect():
    team = current_team()
    event_id = _resolve_event_id()
    if team:
        join_room(f"team-{team.id}")
        logger.info("socket connect sid=%s team=%r", request.sid, team.name)
    elif current_user.is_authenticated:
        logger.info(
            "socket connect sid=%s user=%r role=%s",
            request.sid,
            current_user.email,
            current_user.role,
        )
    else:
        logger.info("socket connect sid=%s anonymous", request.sid)
    join_room(f"event-{event_id}")
    if current_user.is_authenticated and current_user.role == "game_master":
        join_room(f"mod-{event_id}")


@socketio.on("disconnect")
def handle_disconnect():
    logger.info("socket disconnect sid=%s", request.sid)


def notify_team(team_id, event_type):
    socketio.emit("team_update", {"type": event_type}, room=f"team-{team_id}")


def notify_mod(event_type, event_id):
    socketio.emit("mod_update", {"type": event_type}, room=f"mod-{event_id}")


def notify_global(event_type, event_id):
    socketio.emit("event_update", {"type": event_type}, room=f"event-{event_id}")
