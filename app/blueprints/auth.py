import logging
from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_user, logout_user

from ..extensions import db
from ..models import User
from ..repositories.team_repo import TeamRepository

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")
team_repo = TeamRepository()
logger = logging.getLogger("devcrypt.auth")

STAFF_DESTINATIONS = {
    "booth_agent": "agent.dashboard",
    "security_officer": "security.dashboard",
    "game_master": "mod.dashboard",
}


@auth_bp.route("/health")
def health():
    return {"status": "ok"}


@auth_bp.route("/team-login", methods=["GET", "POST"])
def team_login():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        key = request.form.get("key", "").strip()
        team = team_repo.get_team_by_name(name) if name else None
        if not team or not key or not team.check_key(key):
            logger.warning("team login failed name=%r", name)
            flash("Invalid team name or key.", "error")
            return render_template("auth/team_login.html"), 401
        session["team_id"] = team.id
        logger.info("team login ok team=%r team_id=%s", team.name, team.id)
        return redirect(url_for("missions.play"))
    return render_template("auth/team_login.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            logger.warning("staff login failed email=%r", email)
            flash("Invalid email or password.", "error")
            return render_template("auth/login.html"), 401
        if not user.is_active:
            logger.warning("staff login rejected — deactivated account email=%r", email)
            flash("This account has been deactivated. Contact your Game Master.", "error")
            return render_template("auth/login.html"), 401
        login_user(user)
        user.last_login_at = datetime.utcnow()
        db.session.commit()
        logger.info("staff login ok email=%r role=%s user_id=%s", user.email, user.role, user.id)
        return redirect(url_for(STAFF_DESTINATIONS.get(user.role, "home")))
    return render_template("auth/login.html")


@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.pop("team_id", None)
    if current_user.is_authenticated:
        logout_user()
    return redirect(url_for("home"))
