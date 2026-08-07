import json
import random
from datetime import datetime, timedelta

from flask import current_app
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..knowledge_bank import category_for_text
from ..models import Fragment, Mission, TeamMission
from ..sockets import notify_global, notify_mod, notify_team
from .audit_service import AuditService
from .cipher_service import CipherService
from .event_service import EventService
from .scoring_service import ScoringService

KNOWLEDGE_CHECK_POOL_SIZE = 5


def _team_event_id(team):
    # Falls back to the active event for a team row that predates event_id being stamped
    # everywhere (test fixtures, pre-migration data) -- never leaves a push notification with
    # nowhere real to go.
    return team.event_id or EventService().get_active_event().id


class MissionService:
    def __init__(self, scoring=None, cipher=None, audit=None):
        self.scoring = scoring or ScoringService()
        self.cipher = cipher or CipherService()
        self.audit = audit or AuditService()

    def next_mission(self, missions, current_mission_id=None):
        if current_mission_id:
            for mission in missions:
                if mission.id == current_mission_id:
                    return mission
            return None
        return missions[0] if missions else None

    def ordered_for_team(self, team, missions):
        # Full circular rotation for the physical-booth event model: a team assigned to start
        # at booth N visits N, then every other booth in order, wrapping around, ending right
        # before N again — e.g. starting at booth 4 of 6 visits 4,5,6,1,2,3. Equivalent to the
        # modular-arithmetic formula next = (n % count) + 1 applied repeatedly; expressed here
        # as a list rotation, which is the same thing without needing booth numbers to be a
        # contiguous 1..N range.
        #
        # No mission is special-cased out of rotation. An earlier version always pinned the
        # highest-order_index mission last for every team regardless of starting booth — that
        # doesn't fit an event where every booth, including that one, can be any team's
        # starting point (confirmed against the event's actual physical rotation design).
        if not getattr(team, "starting_mission_id", None) or len(missions) <= 1:
            return missions
        start_index = next(
            (i for i, m in enumerate(missions) if m.id == team.starting_mission_id), None
        )
        if start_index is None:
            return missions
        return missions[start_index:] + missions[:start_index]

    def current_mission_for(self, team, missions):
        tm_map = {tm.mission_id: tm for tm in team.team_missions}
        for mission in self.ordered_for_team(team, missions):
            team_mission = tm_map.get(mission.id)
            if not team_mission or team_mission.status not in (
                "passed",
                "overridden",
                "soft_locked",
            ):
                return mission, team_mission
        return None, None

    def freeze_submission(self, team_mission, mission, at=None, grading_status="graded"):
        # Called the instant a deciding submission is *received* — before the grading engine
        # runs, before a Booth Agent reviews it — so neither of those durations can ever count
        # against the team's recorded time. Idempotent: once frozen, later calls (a resubmit
        # spam-click while manual review is pending, or complete_mission() firing later when the
        # Agent actually resolves it) are no-ops, since the official finish time is whichever
        # instant this was first called for this attempt. grading_status is set here too, not
        # left for the caller to set separately — "pending_review" for manual-review queuing,
        # "graded" (the default) for the auto/cipher paths where the outcome is already known
        # synchronously — so the whole freeze is one atomic transition instead of two.
        if team_mission.submitted_at is not None:
            return
        now = at or datetime.utcnow()
        team_mission.submitted_at = now
        elapsed = (now - team_mission.started_at).total_seconds() if team_mission.started_at else 0
        team_mission.elapsed_seconds = int(elapsed)
        if mission.time_limit is not None:
            team_mission.time_remaining = int(mission.time_limit - elapsed)
            team_mission.submission_status = (
                "on_time" if elapsed <= mission.time_limit else "overtime"
            )
        else:
            team_mission.time_remaining = None
            team_mission.submission_status = "on_time"
        team_mission.grading_status = grading_status

    def unfreeze_submission(self, team_mission):
        # Sends a team back to a live-countdown state for another attempt — used when a Booth
        # Agent rejects/retries a manual-review submission, or a Game Master resets a mission.
        team_mission.submitted_at = None
        team_mission.elapsed_seconds = None
        team_mission.time_remaining = None
        team_mission.submission_status = None
        team_mission.grading_status = None

    def get_or_create_team_mission(self, team, mission, event_running=True, _retried=False):
        # event_running gates the timer, not the row's existence -- a team browsing the
        # dashboard before the Game Master starts (or during a pause) still needs its
        # TeamMission row (attempts/hints/knowledge answers persist across that wait), it just
        # must not have its clock ticking yet. Stamping started_at unconditionally here used to
        # be exactly why missions showed "overdue" the instant a team logged in: the row got
        # created (and the clock started) on first page load, long before the event actually
        # began.
        team_mission = TeamMission.query.filter_by(team_id=team.id, mission_id=mission.id).first()
        if not team_mission:
            team_mission = TeamMission(
                team_id=team.id,
                mission_id=mission.id,
                status="in_progress",
                started_at=datetime.utcnow() if event_running else None,
            )
            db.session.add(team_mission)
            try:
                db.session.flush()  # assigns team_mission.id for the audit log below
                self.audit.log(
                    None,
                    "team",
                    "mission_opened",
                    "team_mission",
                    team_mission.id,
                    team_id=team.id,
                    metadata=f"{team.name}: {mission.title}",
                )
                db.session.commit()
            except IntegrityError:
                # Two tabs (or a poll racing a page load) both saw no existing row and both
                # tried to create one -- team_id+mission_id's UniqueConstraint rejects the
                # second insert. Same shape as complete_mission's Fragment race below: discard
                # this attempt and use whichever row actually won, instead of a raw 500.
                db.session.rollback()
                team_mission = TeamMission.query.filter_by(
                    team_id=team.id, mission_id=mission.id
                ).first()
                if team_mission is None and not _retried:
                    # Rarer interleaving (found via testing, not just theorized): the rollback
                    # discarded this attempt, but whatever else conflicted with it hadn't
                    # durably committed either -- genuinely nothing exists now. One bounded
                    # retry is safe: there's no more conflict left to lose to in the normal
                    # case, so it either finds a row that landed in between, or creates one
                    # cleanly. _retried caps this at one attempt -- a second, persistent
                    # failure (this should never happen twice in a row for a real transient
                    # race) raises for real instead of silently looping.
                    return self.get_or_create_team_mission(
                        team, mission, event_running, _retried=True
                    )
        elif (
            team_mission.started_at is None and event_running and team_mission.submitted_at is None
        ):
            # Row already existed (created while the event wasn't running yet), and this is the
            # first poll since it actually went live -- start the clock for real now.
            team_mission.started_at = datetime.utcnow()
            db.session.commit()
        return team_mission

    def extend_timer(self, team_mission, seconds, actor=None, actor_role="game_master"):
        # Narrow moderator recovery lever for a single team whose own session died mid-event
        # while everyone else kept playing -- a global EventService.pause() would penalize
        # every other team's clock too, which isn't the right fix for one team's bad luck.
        if team_mission.started_at is None or team_mission.submitted_at is not None:
            return False
        team_mission.started_at += timedelta(seconds=seconds)
        self.audit.log(
            actor,
            actor_role,
            "timer_extended",
            "team_mission",
            team_mission.id,
            team_id=team_mission.team_id,
            metadata=f"+{seconds}s",
        )
        db.session.commit()
        notify_team(team_mission.team_id, "timer_extended")
        return True

    def assign_knowledge_subset(self, team_mission, mission, pool_size=KNOWLEDGE_CHECK_POOL_SIZE):
        # Chosen once per team per booth, then persisted -- every later call (a page reload, a
        # poll tick) returns the exact same questions in the exact same order, never reshuffled
        # mid-booth. A booth with fewer questions than pool_size just serves all of them.
        all_questions = mission.knowledge_questions
        if team_mission.knowledge_question_pool:
            assigned_ids = team_mission.assigned_question_ids()
            by_id = {q.id: q for q in all_questions}
            matched = [by_id[qid] for qid in assigned_ids if qid in by_id]
            if matched:
                return matched
            # None of the stored ids resolve to a real question anymore -- this booth's
            # questions were replaced (scripts/sync_knowledge_bank.py) after this team was
            # already assigned a subset. Falling through to reassign fresh rather than silently
            # returning an empty list, which would make knowledge_check_complete trivially true
            # (0 answers >= 0 questions) and skip the Knowledge Check entirely.

        chosen = self._pick_category_balanced(all_questions, pool_size)
        team_mission.knowledge_question_pool = json.dumps([q.id for q in chosen])
        db.session.commit()
        return chosen

    def _pick_category_balanced(self, all_questions, pool_size):
        # Draws pool_size questions spread across as many distinct categories as the pool
        # actually has (one per category per pass, cycling for a second pass only if pool_size
        # exceeds the category count) instead of a flat random.sample, which could otherwise
        # hand one team all 5 questions from the same discipline by chance. Falls back to
        # plain randomness within a single "Uncategorized" bucket for any question whose text
        # doesn't match app/knowledge_bank.py (e.g. a test fixture) -- never errors.
        if len(all_questions) <= pool_size:
            return list(all_questions)

        by_category: dict[str, list] = {}
        for q in all_questions:
            category = category_for_text(q.question_text) or "Uncategorized"
            by_category.setdefault(category, []).append(q)
        for bucket in by_category.values():
            random.shuffle(bucket)

        categories = list(by_category.keys())
        random.shuffle(categories)

        chosen: list = []
        while len(chosen) < pool_size and any(by_category.values()):
            for category in categories:
                if len(chosen) >= pool_size:
                    break
                bucket = by_category[category]
                if bucket:
                    chosen.append(bucket.pop())
        return chosen

    def complete_mission(
        self,
        team,
        team_mission,
        mission,
        status,
        actor=None,
        actor_role="team",
        grading_result=None,
        submitted_at=None,
    ):
        if team_mission.status in ("passed", "overridden", "soft_locked"):
            # Already resolved — a double-click, a race between two actors, or a stale
            # reference must not re-award score or insert a second Fragment. This is a
            # fast-path check only, not a race-safe lock: see the IntegrityError handling
            # around the commit below for what actually makes concurrent duplicates safe.
            return None

        # Row-lock the team before touching its score: two teammates submitting from
        # different devices at the same moment would otherwise both read the same starting
        # team.score in Python and one's ScoringService update would silently clobber the
        # other's. FOR UPDATE makes the second request's transaction block here until the
        # first commits, so it re-reads the true post-first-award score instead of a stale one.
        db.session.refresh(team, with_for_update=True)

        # Freeze now if this deciding submission hasn't already been frozen earlier in its
        # lifecycle (manual-review queuing calls freeze_submission at submit time, long before
        # a Booth Agent gets here to resolve it — that freeze wins and this is a no-op). For the
        # auto-graded/cipher paths, which decide pass/fail synchronously, the caller passes the
        # timestamp captured *before* grading ran, so grading time is never counted either.
        self.freeze_submission(team_mission, mission, at=submitted_at)
        team_mission.grading_status = "graded"

        on_time = team_mission.submission_status != "overtime"

        if status == "passed":
            if grading_result is not None:
                # Auto-graded (sandboxed test suite) pass — weighted-percent scoring instead
                # of the flat manual-review score. Everything below (fragment, advance,
                # audit) is identical either way.
                self.scoring.score_auto_graded_pass(
                    team, team_mission, mission.challenge, grading_result, on_time
                )
            else:
                self.scoring.score_mission_pass(team, team_mission, mission, on_time)
        else:
            self.scoring.apply_override_penalty(team, team_mission)

        team_mission.status = status
        team_mission.completed_at = datetime.utcnow()
        team_mission.submission_text = None

        fragment_value = self.cipher.generate_fragment(
            team.id, mission.id, current_app.config["EVENT_SALT"]
        )
        db.session.add(
            Fragment(team_id=team.id, mission_id=mission.id, cipher_value=fragment_value)
        )

        # Everything from here through the commit is wrapped in one try/except: SQLAlchemy's
        # autoflush means the pending Fragment insert (and its UNIQUE(team_id, mission_id)
        # constraint) can get flushed to the DB by *any* subsequent query in this block — not
        # just the explicit commit() at the end — so the IntegrityError from a concurrent
        # duplicate can surface as early as the very next `Mission.query...` line. Confirmed
        # live: with only the final commit() wrapped, 10 simultaneous identical submissions for
        # one team still crashed with a raw 500, because autoflush inside `Mission.query...`
        # threw before that commit() was ever reached.
        try:
            missions = Mission.query.order_by(Mission.order_index).all()
            next_mission, _ = self.current_mission_for(team, missions)
            team.booth_current = next_mission.id if next_mission else None

            self.audit.log(
                actor,
                actor_role,
                f"mission_{status}",
                "team_mission",
                team_mission.id,
                team_id=team.id,
                result=status,
                score_delta=team_mission.score,
            )
            db.session.commit()
        except IntegrityError:
            # Concurrent duplicate: another request for the same team/mission committed first
            # in the window between the status check above and this commit — under gevent's
            # cooperative concurrency, two requests for the same team can both pass that check
            # before either commits. Fragment's unique (team_id, mission_id) constraint is the
            # real race-safe guard; this just turns the resulting IntegrityError into the same
            # graceful "already resolved" outcome as the fast-path check above, instead of a raw
            # 500. Discards every in-memory change this attempt made (score deltas, status,
            # booth_current) — correct, since none of it should apply if a concurrent request
            # already won.
            db.session.rollback()
            return None
        event_id = _team_event_id(team)
        notify_team(team.id, "mission_result")
        notify_mod("mission_result", event_id)
        # Lazy import — avoids a circular import (analytics_service imports MissionService).
        from .analytics_service import AnalyticsService

        AnalyticsService(mission_service=self).snapshot_leaderboard()
        notify_global("leaderboard_refresh", event_id)
        return fragment_value

    def soft_lock_mission(
        self, team, team_mission, mission, min_attempts, actor=None, actor_role="team"
    ):
        # Deliberately NOT a call into complete_mission with a new status value: soft-locking
        # must never insert a Fragment (that's the one thing complete_mission always does,
        # right after freeze/score/status), and it pays a flat participation amount instead of
        # any of the pass/override scoring paths. Sharing complete_mission's Fragment-insert
        # line for this would mean either special-casing it there (fragile) or accepting a
        # Fragment nobody should have — so this stays a parallel, shorter method instead.
        if team_mission.status in ("passed", "overridden", "soft_locked"):
            return False
        if team_mission.attempts < min_attempts:
            return False

        db.session.refresh(team, with_for_update=True)
        self.freeze_submission(team_mission, mission)
        self.scoring.score_soft_lock(team, team_mission)
        team_mission.status = "soft_locked"
        team_mission.completed_at = datetime.utcnow()
        team_mission.submission_text = None

        missions = Mission.query.order_by(Mission.order_index).all()
        next_mission, _ = self.current_mission_for(team, missions)
        team.booth_current = next_mission.id if next_mission else None

        self.audit.log(
            actor,
            actor_role,
            "mission_soft_locked",
            "team_mission",
            team_mission.id,
            team_id=team.id,
            result="soft_locked",
            score_delta=team_mission.score,
        )
        db.session.commit()

        event_id = _team_event_id(team)
        notify_team(team.id, "mission_result")
        notify_mod("mission_result", event_id)
        from .analytics_service import AnalyticsService

        AnalyticsService(mission_service=self).snapshot_leaderboard()
        notify_global("leaderboard_refresh", event_id)
        return True
