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

    players = db.relationship("User", secondary=team_players, back_populates="teams")
    current_mission = db.relationship("Mission", foreign_keys=[booth_current])
    team_missions = db.relationship("TeamMission", backref="team", cascade="all, delete-orphan")
    fragments = db.relationship("Fragment", backref="team", cascade="all, delete-orphan")
    clearance_stamps = db.relationship("ClearanceStamp", backref="team", cascade="all, delete-orphan")
    leaderboard_snapshots = db.relationship("LeaderboardSnapshot", backref="team", cascade="all, delete-orphan")

    def set_key(self, raw_key):
        self.key_hash = bcrypt.generate_password_hash(raw_key).decode("utf-8")

    def check_key(self, raw_key):
        return bcrypt.check_password_hash(self.key_hash, raw_key)


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

    evidence_files = db.relationship("EvidenceFile", backref="mission", cascade="all, delete-orphan")
    mcqs = db.relationship("MCQ", backref="mission", cascade="all, delete-orphan", order_by="MCQ.order_index")
    challenges = db.relationship("Challenge", backref="mission", cascade="all, delete-orphan")
    team_missions = db.relationship("TeamMission", backref="mission", cascade="all, delete-orphan")
    fragments = db.relationship("Fragment", backref="mission", cascade="all, delete-orphan")

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
