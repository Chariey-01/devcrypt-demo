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
    cipher_word = db.Column(db.String(20), nullable=False)
    order_index = db.Column(db.Integer, default=0)
    time_limit = db.Column(db.Integer, nullable=True)
    # NULL = unowned, staffed the legacy way via /booth/select. Set = this mission is a
    # stakeholder booth managed exclusively by that Agent (see app/blueprints/agent.py).
    owner_agent_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    evidence_files = db.relationship("EvidenceFile", backref="mission", cascade="all, delete-orphan")
    mcqs = db.relationship("MCQ", backref="mission", cascade="all, delete-orphan", order_by="MCQ.order_index")
    challenges = db.relationship("Challenge", backref="mission", cascade="all, delete-orphan")
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


class MCQ(db.Model):
    __tablename__ = "mcqs"

    id = db.Column(db.Integer, primary_key=True)
    mission_id = db.Column(db.Integer, db.ForeignKey("missions.id"), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    order_index = db.Column(db.Integer, default=0)
    # Provenance only — lets a future AI-assisted generator tag what it created and from
    # which uploaded file, without a schema change when that feature is built.
    source = db.Column(db.String(20), default="manual")
    source_asset_id = db.Column(db.Integer, db.ForeignKey("evidence_files.id"), nullable=True)

    options = db.relationship("MCQOption", backref="mcq", cascade="all, delete-orphan")


class MCQOption(db.Model):
    __tablename__ = "mcq_options"

    id = db.Column(db.Integer, primary_key=True)
    mcq_id = db.Column(db.Integer, db.ForeignKey("mcqs.id"), nullable=False)
    option_text = db.Column(db.String(255), nullable=False)
    is_correct = db.Column(db.Boolean, default=False)
    cipher_letter_index = db.Column(db.Integer, nullable=True)


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
    # "manual_review" (default, legacy booth-agent queue) or "auto" (sandboxed TestCase grading).
    grading_mode = db.Column(db.String(20), default="manual_review")
    pass_threshold = db.Column(db.Integer, default=100)
    max_attempts = db.Column(db.Integer, nullable=True)
    bonus_points = db.Column(db.Integer, default=0)
    time_limit_seconds = db.Column(db.Integer, default=5)

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

    team_mission = db.relationship("TeamMission", backref="code_submissions")


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
    integrity_delta = db.Column(db.Integer, default=0)
    submission_text = db.Column(db.Text, nullable=True)
    penalty_until = db.Column(db.DateTime, nullable=True)
    hint_used = db.Column(db.Boolean, default=False)

    mcq_answers = db.relationship("TeamMCQAnswer", backref="team_mission", cascade="all, delete-orphan")

    __table_args__ = (db.UniqueConstraint("team_id", "mission_id"),)


class TeamMCQAnswer(db.Model):
    __tablename__ = "team_mcq_answers"

    id = db.Column(db.Integer, primary_key=True)
    team_mission_id = db.Column(db.Integer, db.ForeignKey("team_missions.id"), nullable=False)
    mcq_id = db.Column(db.Integer, db.ForeignKey("mcqs.id"), nullable=False)
    selected_option_id = db.Column(db.Integer, db.ForeignKey("mcq_options.id"), nullable=False)
    is_correct = db.Column(db.Boolean, default=False)
    answered_at = db.Column(db.DateTime, default=datetime.utcnow)

    mcq = db.relationship("MCQ")
    selected_option = db.relationship("MCQOption")


class Fragment(db.Model):
    __tablename__ = "fragments"

    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=False)
    mission_id = db.Column(db.Integer, db.ForeignKey("missions.id"), nullable=False)
    cipher_value = db.Column(db.String(40), nullable=False)
    revealed_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint("team_id", "mission_id"),)


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

    actor = db.relationship("User", backref="event_logs")


class EventState(db.Model):
    __tablename__ = "event_state"

    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.String(20), default="not_started")
    started_at = db.Column(db.DateTime, nullable=True)
    broadcast_message = db.Column(db.String(255), nullable=True)
    broadcast_at = db.Column(db.DateTime, nullable=True)
