"""Idempotently sync app/knowledge_bank.py's hardcoded question pool into the database.

Safe to run repeatedly (including against production once the event's real booths exist):
for each of the 6 sponsor booths, replaces that booth's entire KnowledgeQuestion set with
whatever is currently in knowledge_bank.py. Re-running after editing the bank picks up the
edits; re-running with no changes is a no-op in effect (old rows deleted, identical new rows
created).

Touches ONLY KnowledgeQuestion/KnowledgeOption (and, as an unavoidable consequence, any
TeamKnowledgeAnswer rows already recorded against the questions being replaced -- see the
warning below). Never touches Team/TeamMission/Fragment/CodeSubmission/Challenge/TestCase or
any other table.

**Answer-history warning**: replacing a booth's questions deletes any TeamKnowledgeAnswer rows
already recorded against its old questions (a real team's cipher-reveal progress from
already-answered questions). Fine to run freely before an event starts. Do NOT run mid-event
against a booth teams have already started answering, without accepting that their Knowledge
Check progress for that booth resets -- their cipher board will re-derive correctly on their
next answer, but already-revealed letters from replaced questions won't persist. Cross-check
with scripts/verify_missions.py first if unsure.

Usage:
    python3 scripts/sync_knowledge_bank.py             # prints a summary, asks to confirm
    python3 scripts/sync_knowledge_bank.py --yes        # skip the confirmation prompt
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.knowledge_bank import BOOTH_QUESTION_BANKS
from app.models import KnowledgeOption, KnowledgeQuestion, Mission


def sync_knowledge_bank(quiet=False):
    """Pure sync logic, callable from inside an existing app context (e.g. scripts/seed.py) as
    well as from this file's own CLI. Returns (booths_synced, questions_created)."""
    plan = []
    for booth_id, bank_questions in BOOTH_QUESTION_BANKS.items():
        mission = Mission.query.filter_by(booth_id=booth_id).first()
        if mission is None:
            if not quiet:
                print(f"booth_id={booth_id}: no Mission row found -- skipping.")
            continue
        plan.append((mission, bank_questions))

    total_created = 0
    for mission, bank_questions in plan:
        # Deleting via the ORM (not a bulk .delete()) so the cascades fixed in app/models.py
        # (KnowledgeQuestion -> KnowledgeOption -> TeamKnowledgeAnswer) actually fire.
        for old_question in list(mission.knowledge_questions):
            db.session.delete(old_question)
        db.session.flush()

        for order_index, bank_q in enumerate(bank_questions):
            question = KnowledgeQuestion(
                mission_id=mission.id,
                question_text=bank_q.text,
                order_index=order_index,
            )
            db.session.add(question)
            db.session.flush()
            for i, option_text in enumerate(bank_q.options):
                db.session.add(
                    KnowledgeOption(
                        question_id=question.id,
                        option_text=option_text,
                        is_correct=(i == bank_q.correct_index),
                    )
                )
            total_created += 1

    db.session.commit()
    return len(plan), total_created


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--yes", action="store_true", help="Apply without an interactive confirm prompt."
    )
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        preview = []
        for booth_id, bank_questions in BOOTH_QUESTION_BANKS.items():
            mission = Mission.query.filter_by(booth_id=booth_id).first()
            if mission is None:
                print(f"booth_id={booth_id}: no Mission row found -- skipping.")
                continue
            preview.append((mission, len(mission.knowledge_questions), len(bank_questions)))

        if not preview:
            print("No matching booths found -- nothing to do.")
            return

        print(f"{len(preview)} booth(s) will have their Knowledge Check replaced:\n")
        for mission, existing_count, new_count in preview:
            print(
                f"  booth_id={mission.booth_id} ({mission.title}): {existing_count} existing question(s) -> {new_count} from knowledge_bank.py"
            )
        print()

        if not args.yes:
            answer = input("Apply these changes? [y/N] ").strip().lower()
            if answer != "y":
                print("Aborted -- no changes made.")
                return

        booths_synced, total_created = sync_knowledge_bank()
        print(f"Synced {total_created} question(s) across {booths_synced} booth(s).")


if __name__ == "__main__":
    main()
