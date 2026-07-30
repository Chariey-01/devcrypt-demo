import json
from datetime import datetime

from flask_login import UserMixin

from .extensions import bcrypt, db


team_players = db.Table(
    "team_players",
    db.Column("team_id", db.Integer, db.ForeignKey("teams.id"), primary_key=True),
    db.Column("user_id", db.Integer, db.ForeignKey("users.id"), primary_key=True),
)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # Display-only, distinct from the email used to actually log in — surfaced in the Game
    # Master's Booth Agent Management panel so "who is this" doesn't require memorizing emails.
    full_name = db.Column(db.String(120), nullable=True)
    # Deactivated staff accounts can't log in (see auth.login) but are never deleted implicitly
    # — a Game Master can always reactivate one, and any missions they own stay theirs.
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    last_login_at = db.Column(db.DateTime, nullable=True)

    teams = db.relationship("Team", secondary=team_players, back_populates="players")

    def set_password(self, raw_password):
        self.password_hash = bcrypt.generate_password_hash(raw_password).decode("utf-8")

    def check_password(self, raw_password):
        return bcrypt.check_password_hash(self.password_hash, raw_password)


class Team(db.Model):
    __tablename__ = "teams"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    key_hash = db.Column(db.String(128), unique=True, nullable=False)
    score = db.Column(db.Integer, default=0)
    integrity = db.Column(db.Integer, default=100)
    booth_current = db.Column(db.Integer, db.ForeignKey("missions.id"), nullable=True)
    hints_used = db.Column(db.Integer, default=0)
    # Running per-category breakdown of `score` above, purely for dashboard display (which
    # category earned/cost how much) — never the source of truth for the total itself. Kept in
    # lockstep with every ScoringService.award_points(..., category=...) call; not necessarily
    # individually floor-clamped at 0 the way the total is (a deductions figure reads naturally
    # as negative), so these are display-only and can drift slightly from a literal sum if the
    # total ever gets floor-clamped — that's expected, not a bug.
    mcq_points = db.Column(db.Integer, default=0, nullable=False)
    coding_points = db.Column(db.Integer, default=0, nullable=False)
    cipher_points = db.Column(db.Integer, default=0, nullable=False)
    hint_points = db.Column(db.Integer, default=0, nullable=False)
    time_bonus_points = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # NULL = legacy behavior (start at order_index 0). Set by the Game Master to place a
    # team at a specific booth first.
    starting_mission_id = db.Column(db.Integer, db.ForeignKey("missions.id"), nullable=True)

    players = db.relationship("User", secondary=team_players, back_populates="teams")
    current_mission = db.relationship("Mission", foreign_keys=[booth_current])
    starting_mission = db.relationship("Mission", foreign_keys=[starting_mission_id])
    team_missions = db.relationship("TeamMission", backref="team", cascade="all, delete-orphan")
    fragments = db.relationship("Fragment", backref="team", cascade="all, delete-orphan")
    clearance_stamps = db.relationship("ClearanceStamp", backref="team", cascade="all, delete-orphan")
    leaderboard_snapshots = db.relationship("LeaderboardSnapshot", backref="team", cascade="all, delete-orphan")
    members = db.relationship("TeamMember", backref="team", cascade="all, delete-orphan")

    def set_key(self, raw_key):
        self.key_hash = bcrypt.generate_password_hash(raw_key).decode("utf-8")

    def check_key(self, raw_key):
        return bcrypt.check_password_hash(self.key_hash, raw_key)


class TeamMember(db.Model):
    __tablename__ = "team_members"

    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=True)


class Mission(db.Model):
    __tablename__ = "missions"

    id = db.Column(db.Integer, primary_key=True)
    booth_id = db.Column(db.Integer, nullable=True)
    title = db.Column(db.String(120), nullable=False)
    type = db.Column(db.String(40), nullable=False)
    narrative = db.Column(db.Text, nullable=False)
    # Short employer-facing line shown on the cipher card and booth panel, distinct from the
    # full narrative paragraph. Nullable — rows without one just render no tagline.
    tagline = db.Column(db.String(255), nullable=True)
    cipher_word = db.Column(db.String(20), nullable=False)
    order_index = db.Column(db.Integer, default=0)
    time_limit = db.Column(db.Integer, nullable=True)
    # NULL = unowned (legacy rows predating Agent ownership). Set = this mission is a
    # stakeholder booth managed exclusively by that Agent (see app/blueprints/agent.py).
    owner_agent_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    # "draft" (agent-authoring, invisible to players) | "published" (default — every mission
    # created before this field existed stays visible with zero behavior change) | "archived".
    status = db.Column(db.String(20), default="published", nullable=False)

    evidence_files = db.relationship("EvidenceFile", backref="mission", cascade="all, delete-orphan")
    challenges = db.relationship("Challenge", backref="mission", cascade="all, delete-orphan")
    knowledge_questions = db.relationship(
        "KnowledgeQuestion", backref="mission", cascade="all, delete-orphan",
        order_by="KnowledgeQuestion.order_index",
    )
    team_missions = db.relationship("TeamMission", backref="mission", cascade="all, delete-orphan")
    fragments = db.relationship("Fragment", backref="mission", cascade="all, delete-orphan")
    owner_agent = db.relationship("User", foreign_keys=[owner_agent_id])

    @property
    def challenge(self):
        return self.challenges[0] if self.challenges else None


class EvidenceFile(db.Model):
    __tablename__ = "evidence_files"

    id = db.Column(db.Integer, primary_key=True)
    mission_id = db.Column(db.Integer, db.ForeignKey("missions.id"), nullable=False)
    label = db.Column(db.String(80), nullable=False)
    file_type = db.Column(db.String(40), nullable=False)
    content = db.Column(db.Text, nullable=False)
    # Real uploaded file (image/PDF), stored as bytes in the DB rather than local disk since
    # Railway has no persistent filesystem guarantee. NULL/"" content for these rows -- text-mode
    # assets (the original use case) leave these three columns NULL instead.
    data = db.Column(db.LargeBinary, nullable=True)
    mime_type = db.Column(db.String(100), nullable=True)
    filename = db.Column(db.String(255), nullable=True)


class KnowledgeQuestion(db.Model):
    """A booth's pre-challenge "Knowledge Check" — general discipline trivia, unrelated to the
    coding problem itself (see the removed MCQ system, which WAS tied 1:1 to the challenge; this
    is deliberately a separate, earlier stage — see cipher_service.revealed_indices for the
    cipher-reveal tie-in, and TeamKnowledgeAnswer for the per-team answer record)."""

    __tablename__ = "knowledge_questions"

    id = db.Column(db.Integer, primary_key=True)
    mission_id = db.Column(db.Integer, db.ForeignKey("missions.id"), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    order_index = db.Column(db.Integer, default=0)

    options = db.relationship("KnowledgeOption", backref="question", cascade="all, delete-orphan")


class KnowledgeOption(db.Model):
    __tablename__ = "knowledge_options"

    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey("knowledge_questions.id"), nullable=False)
    option_text = db.Column(db.String(255), nullable=False)
    is_correct = db.Column(db.Boolean, default=False)


class Challenge(db.Model):
    __tablename__ = "challenges"

    id = db.Column(db.Integer, primary_key=True)
    mission_id = db.Column(db.Integer, db.ForeignKey("missions.id"), nullable=False)
    type = db.Column(db.String(20), nullable=False)
    prompt = db.Column(db.Text, nullable=False)
    steps = db.Column(db.Text, nullable=True)
    answer_key = db.Column(db.String(255), nullable=True)
    hint_text = db.Column(db.Text, nullable=True)

    # --- Agent-managed, auto-graded coding challenges (additive; NULL/default reproduces
    # the legacy manual-review behavior above) ---
    title = db.Column(db.String(120), nullable=True)
    language = db.Column(db.String(20), default="python")
    function_signature = db.Column(db.Text, nullable=True)
    starter_code = db.Column(db.Text, nullable=True)
    # PRIVATE — server-side only. Never included in any player-facing serializer.
    solution_code = db.Column(db.Text, nullable=True)
    # "manual_review" (default, legacy booth-agent queue), "auto" (sandboxed TestCase grading),
    # or "pytest" (sandboxed hidden-test-file grading — see test_code below).
    grading_mode = db.Column(db.String(20), default="manual_review")
    pass_threshold = db.Column(db.Integer, default=80)
    max_attempts = db.Column(db.Integer, nullable=True)
    bonus_points = db.Column(db.Integer, default=0)
    # Whole-suite subprocess timeout in "pytest" mode (vs. a per-TestCase timeout in "auto" mode).
    time_limit_seconds = db.Column(db.Integer, default=5)
    # PRIVATE — server-side only, never player-facing. Raw source of a hidden pytest test file,
    # run against the player's submission when grading_mode == "pytest" (see
    # GradingEngine._run_pytest_suite). NULL for every other grading_mode.
    test_code = db.Column(db.Text, nullable=True)
    # Agent-declared, optional. "easy" | "medium" | "hard" — display/filter hint only, no
    # behavioral coupling (distinct from the empirically-observed pass-rate shown in Analytics).
    difficulty = db.Column(db.String(20), nullable=True)

    test_cases = db.relationship(
        "TestCase", backref="challenge", cascade="all, delete-orphan", order_by="TestCase.order_index"
    )
    hints = db.relationship(
        "Hint", backref="challenge", cascade="all, delete-orphan", order_by="Hint.order_index"
    )


class TestCase(db.Model):
    __tablename__ = "test_cases"

    id = db.Column(db.Integer, primary_key=True)
    challenge_id = db.Column(db.Integer, db.ForeignKey("challenges.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    input_data = db.Column(db.Text, nullable=True)
    expected_output = db.Column(db.Text, nullable=False)
    weight = db.Column(db.Integer, default=1)
    visibility = db.Column(db.String(10), default="visible")  # "visible" | "hidden"
    failure_message = db.Column(db.Text, nullable=True)
    order_index = db.Column(db.Integer, default=0)


class Hint(db.Model):
    __tablename__ = "hints"

    id = db.Column(db.Integer, primary_key=True)
    challenge_id = db.Column(db.Integer, db.ForeignKey("challenges.id"), nullable=False)
    order_index = db.Column(db.Integer, default=0)
    text = db.Column(db.Text, nullable=False)
    point_cost = db.Column(db.Integer, nullable=True)


class CodeSubmission(db.Model):
    __tablename__ = "code_submissions"

    id = db.Column(db.Integer, primary_key=True)
    team_mission_id = db.Column(db.Integer, db.ForeignKey("team_missions.id"), nullable=False)
    code = db.Column(db.Text, nullable=False)
    mode = db.Column(db.String(20), nullable=False)  # "run_visible" | "submit"
    total_tests = db.Column(db.Integer, default=0)
    passed_tests = db.Column(db.Integer, default=0)
    weighted_score = db.Column(db.Integer, default=0)
    percent_score = db.Column(db.Integer, default=0)
    passed = db.Column(db.Boolean, default=False)
    results_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Explicit cascade -- without it, deleting a TeamMission (e.g. via Mission delete cascading
    # down, DELETE /agent/missions/<id>) hits a NOT NULL FK violation on any CodeSubmission row
    # still pointing at it instead of being deleted along with it. TeamKnowledgeAnswer below gets
    # this right already; this relationship was the one admin_reset_service.py had to work around
    # with a manual bulk-delete for the team-reset path specifically -- this fixes it at the
    # source so every delete path (not just team-reset) is safe.
    team_mission = db.relationship("TeamMission", backref=db.backref("code_submissions", cascade="all, delete-orphan"))


class TeamMission(db.Model):
    __tablename__ = "team_missions"

    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=False)
    mission_id = db.Column(db.Integer, db.ForeignKey("missions.id"), nullable=False)
    status = db.Column(db.String(20), default="not_started")
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    attempts = db.Column(db.Integer, default=0)
    score = db.Column(db.Integer, default=0)
    # Highest percent_score seen across every auto-graded submission for this booth, whether or
    # not it cleared pass_threshold — lets a below-threshold resubmission be scored as the
    # *delta* against the previous best instead of stacking full credit on every attempt.
    best_percent_score = db.Column(db.Integer, default=0)
    integrity_delta = db.Column(db.Integer, default=0)
    submission_text = db.Column(db.Text, nullable=True)
    penalty_until = db.Column(db.DateTime, nullable=True)
    # hint_used stays a plain "has this booth ever used a hint" flag for any code that only
    # needs that (e.g. the no-hint bonus check) — hints_taken is the real per-booth counter
    # (0..MAX_HINTS_PER_BOOTH) driving sequential hint reveal and per-hint scoring.
    hint_used = db.Column(db.Boolean, default=False)
    hints_taken = db.Column(db.Integer, default=0, nullable=False)

    # --- Frozen at the moment a deciding submission is received (before grading/review runs),
    # never touched by how long grading or Booth Agent review subsequently takes. Reset back to
    # NULL whenever a team is sent back for another attempt (booth retry, game-master reset) so
    # the live countdown resumes. See MissionService.freeze_submission. ---
    submitted_at = db.Column(db.DateTime, nullable=True)
    elapsed_seconds = db.Column(db.Integer, nullable=True)
    time_remaining = db.Column(db.Integer, nullable=True)  # negative == submitted overtime
    submission_status = db.Column(db.String(20), nullable=True)  # "on_time" | "overtime"
    grading_status = db.Column(db.String(20), nullable=True)  # "pending_review" | "graded"

    # JSON-encoded list of KnowledgeQuestion ids, chosen once (randomly, from that booth's full
    # question bank) the first time this team reaches this mission, in the fixed order they're
    # presented/revealed. Nullable -- assigned lazily by MissionService.assign_knowledge_subset,
    # never recomputed afterward, so reloading the page never reshuffles mid-booth.
    knowledge_question_pool = db.Column(db.Text, nullable=True)

    def assigned_question_ids(self):
        if not self.knowledge_question_pool:
            return []
        return json.loads(self.knowledge_question_pool)

    knowledge_answers = db.relationship(
        "TeamKnowledgeAnswer", backref="team_mission", cascade="all, delete-orphan"
    )

    __table_args__ = (db.UniqueConstraint("team_id", "mission_id"),)


class TeamKnowledgeAnswer(db.Model):
    __tablename__ = "team_knowledge_answers"

    id = db.Column(db.Integer, primary_key=True)
    team_mission_id = db.Column(db.Integer, db.ForeignKey("team_missions.id"), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey("knowledge_questions.id"), nullable=False)
    selected_option_id = db.Column(db.Integer, db.ForeignKey("knowledge_options.id"), nullable=False)
    is_correct = db.Column(db.Boolean, default=False)
    answered_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Explicit cascades on both FKs -- without them, deleting a KnowledgeQuestion (or its
    # options, which already cascade from the question) hits the same class of NOT NULL FK
    # violation fixed for CodeSubmission/TeamMission above, the moment any team has answered
    # it. Needed for scripts/sync_knowledge_bank.py, which replaces a booth's question set.
    question = db.relationship("KnowledgeQuestion", backref=db.backref("team_answers", cascade="all, delete-orphan"))
    selected_option = db.relationship("KnowledgeOption", backref=db.backref("team_answers", cascade="all, delete-orphan"))


class Fragment(db.Model):
    __tablename__ = "fragments"

    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=False)
    mission_id = db.Column(db.Integer, db.ForeignKey("missions.id"), nullable=False)
    cipher_value = db.Column(db.String(40), nullable=False)
    revealed_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint("team_id", "mission_id"),)


class FinalFlagConfirmation(db.Model):
    """One row per team, created the moment their fragments first validate correctly, at the
    Command Centre. The flag is never reconstructed/returned to the team until a Game Master
    sets confirmed_by/confirmed_at here — see /missions/final-flag (app/blueprints/missions.py)
    and the Game Master confirm route (app/blueprints/mod.py). No reject state: an unconfirmed
    row just stays pending indefinitely, re-checkable anytime. Modeled on ClearanceStamp's
    "one-time staff-confirmed gate" shape."""

    __tablename__ = "final_flag_confirmations"

    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=False, unique=True)
    requested_at = db.Column(db.DateTime, default=datetime.utcnow)
    confirmed_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    confirmed_at = db.Column(db.DateTime, nullable=True)

    team = db.relationship("Team")
    confirmer = db.relationship("User")


class ClearanceStamp(db.Model):
    __tablename__ = "clearance_stamps"

    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=False)
    officer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    checkpoint_id = db.Column(db.Integer, nullable=False)
    notes = db.Column(db.Text, nullable=True)
    issued_at = db.Column(db.DateTime, default=datetime.utcnow)

    officer = db.relationship("User", backref="clearance_stamps_issued")


class LeaderboardSnapshot(db.Model):
    __tablename__ = "leaderboard_snapshots"

    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=False)
    rank = db.Column(db.Integer, nullable=False)
    score = db.Column(db.Integer, nullable=False)
    integrity = db.Column(db.Integer, nullable=False)
    mission_current = db.Column(db.String(120), nullable=True)
    fragments_count = db.Column(db.Integer, default=0)
    snapshotted_at = db.Column(db.DateTime, default=datetime.utcnow)


class EventLog(db.Model):
    __tablename__ = "event_logs"

    id = db.Column(db.Integer, primary_key=True)
    actor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    actor_role = db.Column(db.String(20), nullable=False)
    action = db.Column(db.String(80), nullable=False)
    target_type = db.Column(db.String(40), nullable=True)
    target_id = db.Column(db.Integer, nullable=True)
    # Column is named "metadata" per the PRD schema; the attribute is renamed
    # because SQLAlchemy's declarative base reserves `.metadata` on Model.
    event_metadata = db.Column("metadata", db.Text, nullable=True)
    logged_at = db.Column(db.DateTime, default=datetime.utcnow)
    # Structured fields added for dispute-resolution reporting -- all nullable/additive so
    # existing rows and existing .log() call sites that don't pass them keep working unchanged.
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)  # long enough for IPv6
    user_agent = db.Column(db.String(255), nullable=True)
    result = db.Column(db.String(20), nullable=True)  # e.g. "passed" | "failed" | "soft_locked"
    score_delta = db.Column(db.Integer, nullable=True)

    actor = db.relationship("User", backref="event_logs")
    team = db.relationship("Team")

    __table_args__ = (db.Index("ix_event_logs_team_id_logged_at", "team_id", "logged_at"),)


class EventState(db.Model):
    __tablename__ = "event_state"

    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.String(20), default="not_started")
    started_at = db.Column(db.DateTime, nullable=True)
    # Set on pause(), cleared on the resuming start() -- lets start() compute exactly how long
    # the event was paused and shift every in-progress TeamMission.started_at forward by that
    # same duration, so a pause never eats into a team's remaining time.
    paused_at = db.Column(db.DateTime, nullable=True)
    broadcast_message = db.Column(db.String(255), nullable=True)
    broadcast_at = db.Column(db.DateTime, nullable=True)
    name = db.Column(db.String(120), nullable=True)
    description = db.Column(db.Text, nullable=True)
    hint_limit = db.Column(db.Integer, default=3, nullable=False)
    leaderboard_public = db.Column(db.Boolean, default=True, nullable=False)
    # Inert legacy column — manual review no longer exists (agents are grading-free monitors),
    # so this no longer has any effect anywhere. Left in place rather than migrated away.
    auto_grading_disabled = db.Column(db.Boolean, default=False, nullable=False)
    # A team can't Soft Lock a booth until they've failed it at least this many times — keeps
    # it a genuine "we're stuck" escape hatch rather than a free first-attempt point farm.
    soft_lock_min_attempts = db.Column(db.Integer, default=1, nullable=False)
