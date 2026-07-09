from functools import wraps

from flask import abort, redirect, session, url_for
from flask_login import current_user


def team_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("team_id"):
            return redirect(url_for("auth.team_login"))
        return view(*args, **kwargs)

    return wrapped


def roles_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role not in roles:
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator


def current_team():
    from .models import Team

    team_id = session.get("team_id")
    return Team.query.get(team_id) if team_id else None
