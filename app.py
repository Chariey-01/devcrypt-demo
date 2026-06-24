from flask import (
    Flask, render_template, request, session,
    redirect, url_for, jsonify
)
import json
import time
import os

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "devcrypt-dev-secret-change-in-prod")

# Import vault data
import sys
sys.path.insert(0, os.path.dirname(__file__))
from data.vaults import VAULTS

VAULT_MAP = {v["id"]: v for v in VAULTS}

POINTS = {
    "mcq_correct": 100,
    "mcq_wrong_penalty": -30,
    "code_correct": 200,
    "time_bonus_per_second": 0.5,   # points per second left on clock
    "time_over_penalty": -2,        # points per second over the limit
}


# ── helpers ────────────────────────────────────────────────────────────────

def init_session(team_name: str, members: list[str]):
    session.clear()
    session["team"] = team_name
    session["members"] = members
    session["score"] = 0
    session["current_vault"] = 1
    session["vault_states"] = {
        str(i): {
            "unlocked": i == 1,
            "completed": False,
            "mcq_done": False,
            "mcq_answers": {},
            "code_submitted": False,
            "word_revealed": False,
            "timer_start": None,
            "time_used": None,
        }
        for i in range(1, 7)
    }
    # Cipher words (ROT-shifted display → revealed on solve)
    session["cipher_words"] = {
        str(i): {"cipher": _rot_word(VAULT_MAP[i]["cipher_word"]), "plain": VAULT_MAP[i]["cipher_word"], "revealed": False}
        for i in range(1, 7)
    }
    session.modified = True


def _rot_word(word: str, shift: int = 7) -> str:
    result = []
    for ch in word.upper():
        if ch.isalpha():
            result.append(chr((ord(ch) - 65 + shift) % 26 + 65))
        else:
            result.append(ch)
    return "".join(result)


def get_vault_state(vault_id: int) -> dict:
    return session["vault_states"][str(vault_id)]


def add_score(points: int):
    session["score"] = session.get("score", 0) + points
    session.modified = True


def check_code_answer(vault_id: int, user_answer: str) -> bool:
    vault = VAULT_MAP[vault_id]
    keywords = vault["coding_challenge"]["solution_keywords"]
    answer_lower = user_answer.lower()
    hits = sum(1 for kw in keywords if kw.lower() in answer_lower)
    # Need at least 50% of keywords to pass
    return hits >= max(2, len(keywords) // 2)


# ── routes ─────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        team_name = request.form.get("team_name", "").strip()
        members_raw = request.form.get("members", "")
        members = [m.strip() for m in members_raw.split(",") if m.strip()]
        if not team_name or not members:
            return render_template("register.html", error="Team name and at least one member required.")
        init_session(team_name, members)
        return redirect(url_for("vault", vault_id=1))
    return render_template("register.html")


@app.route("/vault/<int:vault_id>")
def vault(vault_id: int):
    if "team" not in session:
        return redirect(url_for("index"))
    if vault_id < 1 or vault_id > 6:
        return redirect(url_for("index"))

    state = get_vault_state(vault_id)
    if not state["unlocked"]:
        return redirect(url_for("vault", vault_id=session.get("current_vault", 1)))

    vault_data = VAULT_MAP[vault_id]
    cipher_words = session["cipher_words"]

    # Start timer on first visit
    if state["timer_start"] is None and not state["completed"]:
        session["vault_states"][str(vault_id)]["timer_start"] = time.time()
        session.modified = True

    return render_template(
        "vault.html",
        vault=vault_data,
        state=state,
        cipher_words=cipher_words,
        score=session["score"],
        team=session["team"],
        total_vaults=6,
    )


@app.route("/vault/<int:vault_id>/mcq", methods=["POST"])
def submit_mcq(vault_id: int):
    if "team" not in session:
        return jsonify({"error": "no session"}), 403

    vault_data = VAULT_MAP[vault_id]
    state = get_vault_state(vault_id)

    if state["mcq_done"]:
        return jsonify({"error": "already submitted"}), 400

    results = {}
    total_correct = 0
    for q in vault_data["mcq"]:
        qid = q["id"]
        user_ans = request.form.get(qid, "").strip().upper()
        correct = user_ans == q["answer"]
        results[qid] = {"correct": correct, "correct_answer": q["answer"]}
        if correct:
            add_score(POINTS["mcq_correct"])
            total_correct += 1
        else:
            add_score(POINTS["mcq_wrong_penalty"])

    session["vault_states"][str(vault_id)]["mcq_done"] = True
    session["vault_states"][str(vault_id)]["mcq_answers"] = results
    session.modified = True

    return jsonify({"results": results, "score": session["score"], "total_correct": total_correct})


@app.route("/vault/<int:vault_id>/code", methods=["POST"])
def submit_code(vault_id: int):
    if "team" not in session:
        return jsonify({"error": "no session"}), 403

    state = get_vault_state(vault_id)
    if state["code_submitted"]:
        return jsonify({"error": "already submitted"}), 400

    user_code = request.form.get("code", "").strip()
    passed = check_code_answer(vault_id, user_code)

    # Calculate time bonus/penalty
    vault_data = VAULT_MAP[vault_id]
    timer_start = state["timer_start"] or time.time()
    elapsed = time.time() - timer_start
    time_limit = vault_data["timer"]
    time_remaining = time_limit - elapsed

    if passed:
        add_score(POINTS["code_correct"])
        if time_remaining > 0:
            add_score(int(time_remaining * POINTS["time_bonus_per_second"]))
        else:
            add_score(int(time_remaining * abs(POINTS["time_over_penalty"])))  # negative

        # Reveal cipher word and unlock next vault
        session["cipher_words"][str(vault_id)]["revealed"] = True
        session["vault_states"][str(vault_id)]["word_revealed"] = True
        session["vault_states"][str(vault_id)]["completed"] = True
        session["vault_states"][str(vault_id)]["code_submitted"] = True
        session["vault_states"][str(vault_id)]["time_used"] = int(elapsed)

        if vault_id < 6:
            session["vault_states"][str(vault_id + 1)]["unlocked"] = True
            session["current_vault"] = vault_id + 1

        session.modified = True
        return jsonify({
            "passed": True,
            "score": session["score"],
            "revealed_word": VAULT_MAP[vault_id]["cipher_word"],
            "next_vault": vault_id + 1 if vault_id < 6 else None,
            "time_used": int(elapsed),
        })
    else:
        add_score(POINTS["mcq_wrong_penalty"])
        session["vault_states"][str(vault_id)]["code_submitted"] = False
        session.modified = True
        return jsonify({"passed": False, "score": session["score"]})


@app.route("/board")
def leaderboard():
    if "team" not in session:
        return redirect(url_for("index"))

    vaults_status = []
    for i in range(1, 7):
        state = get_vault_state(i)
        vaults_status.append({
            "id": i,
            "title": VAULT_MAP[i]["title"],
            "completed": state["completed"],
            "word": session["cipher_words"][str(i)]["plain"] if state["word_revealed"] else None,
            "cipher": session["cipher_words"][str(i)]["cipher"],
            "time_used": state.get("time_used"),
            "timer": VAULT_MAP[i]["timer"],
        })

    all_done = all(v["completed"] for v in vaults_status)
    flag = "FLAG{RESTORE}" if all_done else None

    return render_template(
        "leaderboard.html",
        team=session["team"],
        members=session["members"],
        score=session["score"],
        vaults=vaults_status,
        flag=flag,
    )


@app.route("/api/timer/<int:vault_id>")
def get_timer(vault_id: int):
    if "team" not in session:
        return jsonify({"error": "no session"}), 403
    state = get_vault_state(vault_id)
    vault_data = VAULT_MAP[vault_id]
    if state["timer_start"] is None:
        return jsonify({"remaining": vault_data["timer"], "expired": False})
    elapsed = time.time() - state["timer_start"]
    remaining = max(0, vault_data["timer"] - elapsed)
    return jsonify({"remaining": int(remaining), "elapsed": int(elapsed), "expired": remaining <= 0})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
