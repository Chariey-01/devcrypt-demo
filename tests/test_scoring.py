from app.services.scoring_service import ScoringService


class DummyTeam:
    def __init__(self, score=0, integrity=100, hints_used=0):
        self.score = score
        self.integrity = integrity
        self.hints_used = hints_used


class DummyTeamMission:
    def __init__(self, score=0, integrity_delta=0, attempts=0, hint_used=False, best_percent_score=0):
        self.score = score
        self.integrity_delta = integrity_delta
        self.attempts = attempts
        self.hint_used = hint_used
        self.best_percent_score = best_percent_score


class DummyGradingResult:
    def __init__(self, percent_score):
        self.percent_score = percent_score


class DummyChallenge:
    def __init__(self, bonus_points=0):
        self.bonus_points = bonus_points


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

    points = service.score_mission_pass(team, team_mission, mission=None, on_time=True)

    assert points == service.CHALLENGE_COMPLETE + service.NO_HINT_BONUS + service.ON_TIME_BONUS + service.PERFECT_BONUS
    assert team.score == points
    assert team_mission.score == points


def test_score_mission_pass_no_perfect_bonus_if_hint_used():
    service = ScoringService()
    team = DummyTeam()
    team_mission = DummyTeamMission(hint_used=True)

    points = service.score_mission_pass(team, team_mission, mission=None, on_time=True)

    assert points == service.CHALLENGE_COMPLETE + service.ON_TIME_BONUS


def test_score_auto_graded_partial_awards_proportional_credit():
    service = ScoringService()
    team = DummyTeam()
    team_mission = DummyTeamMission()

    delta = service.score_auto_graded_partial(team, team_mission, DummyGradingResult(60))

    assert delta == round(service.CHALLENGE_COMPLETE * 0.6)
    assert team.score == delta
    assert team_mission.score == delta
    assert team_mission.best_percent_score == 60


def test_score_auto_graded_partial_only_awards_the_delta_above_best_so_far():
    service = ScoringService()
    team = DummyTeam()
    team_mission = DummyTeamMission()

    first = service.score_auto_graded_partial(team, team_mission, DummyGradingResult(40))
    second = service.score_auto_graded_partial(team, team_mission, DummyGradingResult(70))

    assert second == round(service.CHALLENGE_COMPLETE * 0.7) - round(service.CHALLENGE_COMPLETE * 0.4)
    assert team.score == first + second
    assert team_mission.best_percent_score == 70


def test_score_auto_graded_partial_never_pays_again_for_a_worse_or_equal_resubmit():
    service = ScoringService()
    team = DummyTeam()
    team_mission = DummyTeamMission()

    service.score_auto_graded_partial(team, team_mission, DummyGradingResult(60))
    score_after_first = team.score

    delta = service.score_auto_graded_partial(team, team_mission, DummyGradingResult(30))

    assert delta == 0
    assert team.score == score_after_first  # never goes down, and never re-pays a worse attempt
    assert team_mission.best_percent_score == 60


def test_score_auto_graded_pass_after_partial_credit_only_pays_the_remaining_base_plus_bonuses():
    # A team that failed at 60% (partial credit already paid), then passed at 100%, must end
    # up with exactly what a clean 100% pass would have earned — not the partial credit PLUS
    # a full second base amount.
    service = ScoringService()
    team = DummyTeam()
    team_mission = DummyTeamMission()
    challenge = DummyChallenge(bonus_points=0)

    service.score_auto_graded_partial(team, team_mission, DummyGradingResult(60))
    partial_total = team.score

    pass_points = service.score_auto_graded_pass(
        team, team_mission, challenge, DummyGradingResult(100), on_time=True
    )

    clean_pass_points = (
        service.CHALLENGE_COMPLETE + service.NO_HINT_BONUS + service.ON_TIME_BONUS + service.PERFECT_BONUS
    )
    assert partial_total + pass_points == clean_pass_points
    assert team.score == clean_pass_points
    assert team_mission.best_percent_score == 100


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
