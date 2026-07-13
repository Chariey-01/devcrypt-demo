from flask import Blueprint, render_template

portals_bp = Blueprint("portals", __name__)


@portals_bp.route("/team")
def team_portal():
    return render_template("portals/team.html")


@portals_bp.route("/staff")
def staff_portal():
    return render_template("portals/staff.html")


@portals_bp.route("/moderator")
def moderator_portal():
    return render_template("portals/moderator.html")
