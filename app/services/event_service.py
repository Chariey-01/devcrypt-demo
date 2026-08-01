from datetime import datetime

from ..extensions import db
from ..models import (
    Challenge,
    Event,
    EvidenceFile,
    Hint,
    KnowledgeOption,
    KnowledgeQuestion,
    Mission,
    TeamMission,
    TestCase,
)
from ..sockets import notify_global

# An event is "live" (publicly reachable) once it leaves draft and until it's wrapped up --
# these are the statuses ActiveEventConflict guards against having more than one of at a time.
_ACTIVE_STATUSES = ("not_started", "running", "paused")


def event_scope_filter(model, event_id):
    """OR-in rows that haven't been stamped with an event_id yet, so scoping stays additive
    during the Phase 1b/1c rollout instead of silently hiding legacy/test data that predates
    every creation path stamping it. The live production DB has no such rows (Phase 1a's
    migration backfilled everything to the one real Event), so in practice this only matters
    until Phase 1d makes event_id NOT NULL everywhere, at which point the IS NULL half never
    matches anything and this is a plain equality filter."""
    return db.or_(model.event_id == event_id, model.event_id.is_(None))


class ActiveEventConflict(Exception):
    """Raised when publishing/starting an event would leave more than one event publicly live
    at once -- the platform's locked-in design is exactly one live event at a time (see the
    Phase 1 roadmap). Callers (mod.py routes) turn this into a 409 with the conflicting event's
    name so a Game Master knows what to end/archive first."""

    def __init__(self, other_event):
        self.other_event = other_event
        super().__init__(f"'{other_event.name or 'Untitled event'}' is already live.")


class EventService:
    def get_active_event(self):
        # The one event currently live for players (see _ACTIVE_STATUSES) -- falls back to the
        # most recently created event of any status if none are active yet (matches the
        # single-event behavior from before Phase 1c: a brand-new install with one draft event
        # still resolves to it), and lazily creates a fresh draft if the table is empty.
        event = (
            Event.query.filter(Event.status.in_(_ACTIVE_STATUSES)).order_by(Event.id.desc()).first()
            or Event.query.order_by(Event.id.desc()).first()
        )
        if not event:
            event = Event(status="draft")
            db.session.add(event)
            db.session.commit()
        return event

    def get_event(self, event_id):
        return Event.query.get(event_id)

    def list_events(self):
        return Event.query.order_by(Event.id.desc()).all()

    def create_event(self, name=None):
        event = Event(status="draft", name=(name or "").strip() or None)
        db.session.add(event)
        db.session.commit()
        return event

    def _resolve(self, event_id):
        return self.get_event(event_id) if event_id is not None else self.get_active_event()

    def _ensure_no_other_active(self, event_id):
        other = (
            Event.query.filter(Event.status.in_(_ACTIVE_STATUSES), Event.id != event_id)
            .order_by(Event.id.desc())
            .first()
        )
        if other is not None:
            raise ActiveEventConflict(other)

    def publish(self, event_id=None):
        state = self._resolve(event_id)
        if state.status == "draft":
            self._ensure_no_other_active(state.id)
            state.status = "not_started"
        db.session.commit()
        return state

    def archive(self, event_id=None):
        state = self._resolve(event_id)
        state.status = "archived"
        db.session.commit()
        return state

    def start(self, event_id=None):
        state = self._resolve(event_id)
        if state.status == "paused" and state.paused_at is not None:
            # Resuming, not starting fresh -- give back exactly the wall-clock duration the
            # event was paused for, to every mission still in progress, so a pause never eats
            # into a team's remaining time. A team that hasn't reached a booth yet (started_at
            # still NULL) is untouched -- its clock starts for real the next time it polls,
            # same as MissionService.get_or_create_team_mission handles for a not-yet-started
            # event. Scoped to this event's own missions -- resuming Event A must never touch
            # Event B's in-progress teams.
            pause_duration = datetime.utcnow() - state.paused_at
            in_progress = (
                TeamMission.query.join(Mission, TeamMission.mission_id == Mission.id)
                .filter(
                    TeamMission.submitted_at.is_(None),
                    TeamMission.started_at.isnot(None),
                    event_scope_filter(Mission, state.id),
                )
                .all()
            )
            for team_mission in in_progress:
                team_mission.started_at += pause_duration
            state.paused_at = None
        else:
            self._ensure_no_other_active(state.id)
            state.started_at = datetime.utcnow()
        state.status = "running"
        db.session.commit()
        notify_global("event_start", state.id)
        return state

    def pause(self, event_id=None):
        state = self._resolve(event_id)
        state.status = "paused"
        state.paused_at = datetime.utcnow()
        db.session.commit()
        notify_global("event_pause", state.id)
        return state

    def end(self, event_id=None):
        state = self._resolve(event_id)
        state.status = "ended"
        db.session.commit()
        notify_global("event_end", state.id)
        return state

    def broadcast(self, message, event_id=None):
        state = self._resolve(event_id)
        state.broadcast_message = message
        state.broadcast_at = datetime.utcnow()
        db.session.commit()
        notify_global("broadcast", state.id)
        return state

    def duplicate_event(self, source_event_id, name=None):
        """Clones a event's *content* (missions, challenges, test cases, hints, evidence,
        knowledge questions) into a brand-new draft Event -- never teams, scores, or logs,
        since the whole point is starting next year's Career Fair fresh. Mirrors
        app/blueprints/agent.py's per-mission duplicate_mission, one level up."""
        source = self.get_event(source_event_id)
        new_event = Event(
            status="draft", name=name or (f"{source.name} (copy)" if source.name else None)
        )
        db.session.add(new_event)
        db.session.flush()

        missions = (
            Mission.query.filter(event_scope_filter(Mission, source.id))
            .order_by(Mission.order_index)
            .all()
        )
        for mission in missions:
            copy = Mission(
                booth_id=mission.booth_id,
                title=mission.title,
                type=mission.type,
                narrative=mission.narrative,
                tagline=mission.tagline,
                cipher_word=mission.cipher_word,
                order_index=mission.order_index,
                time_limit=mission.time_limit,
                owner_agent_id=mission.owner_agent_id,
                # Every duplicated mission starts as a draft regardless of the source's status
                # -- a fresh event's content should always be reviewed/republished deliberately,
                # never accidentally already live the moment it's copied.
                status="draft",
                event_id=new_event.id,
            )
            db.session.add(copy)
            db.session.flush()

            for asset in mission.evidence_files:
                db.session.add(
                    EvidenceFile(
                        mission_id=copy.id,
                        label=asset.label,
                        file_type=asset.file_type,
                        content=asset.content,
                        data=asset.data,
                        mime_type=asset.mime_type,
                        filename=asset.filename,
                    )
                )

            for question in mission.knowledge_questions:
                new_question = KnowledgeQuestion(
                    mission_id=copy.id,
                    question_text=question.question_text,
                    order_index=question.order_index,
                )
                db.session.add(new_question)
                db.session.flush()
                for option in question.options:
                    db.session.add(
                        KnowledgeOption(
                            question_id=new_question.id,
                            option_text=option.option_text,
                            is_correct=option.is_correct,
                        )
                    )

            if mission.challenge:
                src = mission.challenge
                challenge = Challenge(
                    mission_id=copy.id,
                    type=src.type,
                    prompt=src.prompt,
                    steps=src.steps,
                    answer_key=src.answer_key,
                    hint_text=src.hint_text,
                    title=src.title,
                    language=src.language,
                    function_signature=src.function_signature,
                    starter_code=src.starter_code,
                    solution_code=src.solution_code,
                    grading_mode=src.grading_mode,
                    pass_threshold=src.pass_threshold,
                    max_attempts=src.max_attempts,
                    bonus_points=src.bonus_points,
                    time_limit_seconds=src.time_limit_seconds,
                    test_code=src.test_code,
                    difficulty=src.difficulty,
                )
                db.session.add(challenge)
                db.session.flush()
                for tc in src.test_cases:
                    db.session.add(
                        TestCase(
                            challenge_id=challenge.id,
                            name=tc.name,
                            input_data=tc.input_data,
                            expected_output=tc.expected_output,
                            weight=tc.weight,
                            visibility=tc.visibility,
                            failure_message=tc.failure_message,
                            order_index=tc.order_index,
                        )
                    )
                for hint in src.hints:
                    db.session.add(
                        Hint(
                            challenge_id=challenge.id,
                            text=hint.text,
                            point_cost=hint.point_cost,
                            order_index=hint.order_index,
                        )
                    )

        db.session.commit()
        return new_event
