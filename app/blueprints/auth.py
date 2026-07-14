from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_user, logout_user

from ..models import User
from ..repositories.team_repo import TeamRepository

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")
team_repo = TeamRepository()

STAFF_DESTINATIONS = {
    "booth_agent": "booth.select_booth",
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
            flash("Invalid team name or key.", "error")
            return render_template("auth/team_login.html"), 401
        session["team_id"] = team.id
        return redirect(url_for("missions.play"))
    return render_template("auth/team_login.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            flash("Invalid email or password.", "error")
            return render_template("auth/login.html"), 401
        login_user(user)
        return redirect(url_for(STAFF_DESTINATIONS.get(user.role, "home")))
    return render_template("auth/login.html")


@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.pop("team_id", None)
    if current_user.is_authenticated:
        logout_user()
    return redirect(url_for("home"))
