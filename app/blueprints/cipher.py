from flask import Blueprint, jsonify

from ..decorators import current_team, team_required
from ..models import Mission
from ..services.cipher_service import CipherService

cipher_bp = Blueprint("cipher", __name__, url_prefix="/cipher")
cipher_service = CipherService()


@cipher_bp.route("/health")
def health():
    return jsonify({"status": "ok"})


@cipher_bp.route("/board")
@team_required
def board():
    team = current_team()
    missions = Mission.query.order_by(Mission.order_index).all()
    return jsonify({"board": cipher_service.board_state(team, missions)})
