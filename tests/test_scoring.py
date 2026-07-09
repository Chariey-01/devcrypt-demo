from app.services.scoring_service import ScoringService


class DummyTeam:
    def __init__(self, score=0, integrity=100, hints_used=0):
        self.score = score
        self.integrity = integrity
        self.hints_used = hints_used


class DummyTeamMission:
    def __init__(self, score=0, integrity_delta=0, attempts=0, hint_used=False):
        self.score = score
        self.integrity_delta = integrity_delta
        self.attempts = attempts
        self.hint_used = hint_used


def test_award_points_updates_team_score():
    service = ScoringService()
    team = DummyTeam(score=10)

    new_score = service.award_points(team, 25, "solved mission")

    assert new_score == 35
    assert team.score == 35


def test_award_points_never_drops_below_zero():
    service = ScoringService()
    team = DummyTeam(score=10)

    service.award_points(team, -50)

    assert team.score == 0


def test_score_mission_pass_awards_all_bonuses_when_perfect():
    service = ScoringService()
    team = DummyTeam()
    team_mission = DummyTeamMission(hint_used=False)

    points = service.score_mission_pass(team, team_mission, mission=None, all_mcqs_correct=True, on_time=True)

    assert points == service.CHALLENGE_COMPLETE + service.NO_HINT_BONUS + service.ON_TIME_BONUS + service.PERFECT_BONUS
    assert team.score == points
    assert team_mission.score == points


def test_score_mission_pass_no_perfect_bonus_if_hint_used():
    service = ScoringService()
    team = DummyTeam()
    team_mission = DummyTeamMission(hint_used=True)

    points = service.score_mission_pass(team, team_mission, mission=None, all_mcqs_correct=True, on_time=True)

    assert points == service.CHALLENGE_COMPLETE + service.ON_TIME_BONUS


def test_apply_hint_penalty_deducts_score_integrity_and_increments_budget():
    service = ScoringService()
    team = DummyTeam(score=100, integrity=100, hints_used=0)
    team_mission = DummyTeamMission()

    service.apply_hint_penalty(team, team_mission)

    assert team.score == 100 - service.HINT_PENALTY
    assert team.integrity == 100 - service.HINT_INTEGRITY_PENALTY
    assert team.hints_used == 1
    assert team_mission.hint_used is True


def test_apply_retry_penalty_only_hurts_integrity_after_first_attempt():
    service = ScoringService()
    team = DummyTeam(integrity=100)
    team_mission = DummyTeamMission(attempts=0)

    service.apply_retry_penalty(team, team_mission)
    assert team_mission.attempts == 1
    assert team.integrity == 100

    service.apply_retry_penalty(team, team_mission)
    assert team_mission.attempts == 2
    assert team.integrity == 100 - service.RETRY_INTEGRITY_PENALTY


def test_apply_override_penalty():
    service = ScoringService()
    team = DummyTeam(score=100, integrity=100)
    team_mission = DummyTeamMission()

    service.apply_override_penalty(team, team_mission)

    assert team.score == 100 - service.OVERRIDE_PENALTY
    assert team.integrity == 100 - service.OVERRIDE_INTEGRITY_PENALTY


def test_score_checkpoint_awards_flat_bonus():
    service = ScoringService()
    team = DummyTeam(score=0)

    service.score_checkpoint(team)

    assert team.score == service.CHECKPOINT_BONUS
