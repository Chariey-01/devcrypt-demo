"""One-shot safety check before migration caa6e552ffd4 (unique constraint on
team_knowledge_answers). Run against production BEFORE that migration if it's ever
reordered/reapplied from scratch against unfamiliar data -- a duplicate (team_mission_id,
question_id) pair would make the ALTER fail outright. Exits non-zero if any duplicates exist.

    railway run --service web --environment production -- python3 scripts/check_no_duplicate_answers.py
"""

import sys

from app import create_app
from app.extensions import db
from app.models import TeamKnowledgeAnswer

app = create_app()
with app.app_context():
    rows = (
        db.session.query(
            TeamKnowledgeAnswer.team_mission_id,
            TeamKnowledgeAnswer.question_id,
            db.func.count().label("n"),
        )
        .group_by(TeamKnowledgeAnswer.team_mission_id, TeamKnowledgeAnswer.question_id)
        .having(db.func.count() > 1)
        .all()
    )
    if rows:
        print(f"FOUND {len(rows)} duplicate (team_mission_id, question_id) group(s):")
        for team_mission_id, question_id, n in rows:
            print(f"  team_mission_id={team_mission_id} question_id={question_id} count={n}")
        sys.exit(1)
    print("No duplicates found -- safe to apply the unique constraint.")
