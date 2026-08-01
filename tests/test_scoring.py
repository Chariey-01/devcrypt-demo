from app.services.scoring_service import ScoringService


class DummyKnowledgeAnswer:
    def __init__(self, is_correct=True):
        self.is_correct = is_correct


class DummyTeam:
    def __init__(self, score=0, integrity=100, hints_used=0):
        self.score = score
        self.integrity = integrity
        self.hints_used = hints_used
        self.mcq_points = 0
        self.coding_points = 0
        self.cipher_points = 0
        self.hint_points = 0
        self.time_bonus_points = 0


class DummyTeamMission:
    def __init__(
        self,
        score=0,
        integrity_delta=0,
        attempts=0,
        hint_used=False,
        best_percent_score=0,
        elapsed_seconds=None,
        knowledge_answers=None,
        hints_taken=0,
    ):
        self.score = score
        self.integrity_delta = integrity_delta
        self.attempts = attempts
        self.hint_used = hint_used
        self.best_percent_score = best_percent_score
        self.elapsed_seconds = elapsed_seconds
        self.knowledge_answers = knowledge_answers or []
        self.hints_taken = hints_taken


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


def test_award_points_routes_to_the_matching_category_bucket():
    service = ScoringService()
    team = DummyTeam()

    service.award_points(team, 10, category="mcq")
    service.award_points(team, 100, category="coding")
    service.award_points(team, 50, category="cipher")
    service.award_points(team, -15, category="hint")
    service.award_points(team, 20, category="time")

    assert team.mcq_points == 10
    assert team.coding_points == 100
    assert team.cipher_points == 50
    assert team.hint_points == -15
    assert team.time_bonus_points == 20
    assert team.score == 10 + 100 + 50 - 15 + 20


def test_time_bonus_for_elapsed_tiers():
    service = ScoringService()

    assert service.time_bonus_for_elapsed(None) == 0
    assert service.time_bonus_for_elapsed(0) == 20
    assert service.time_bonus_for_elapsed(300) == 20
    assert service.time_bonus_for_elapsed(301) == 10
    assert service.time_bonus_for_elapsed(480) == 10
    assert service.time_bonus_for_elapsed(481) == 5
    assert service.time_bonus_for_elapsed(600) == 5
    assert service.time_bonus_for_elapsed(601) == 0


def test_score_knowledge_correct_awards_mcq_points():
    service = ScoringService()
    team = DummyTeam()
    team_mission = DummyTeamMission()

    service.score_knowledge_correct(team, team_mission)

    assert team.score == service.KNOWLEDGE_CORRECT
    assert team.mcq_points == service.KNOWLEDGE_CORRECT
    assert team_mission.score == service.KNOWLEDGE_CORRECT


def test_award_all_mcq_correct_bonus():
    service = ScoringService()
    team = DummyTeam()
    team_mission = DummyTeamMission()

    service.award_all_mcq_correct_bonus(team, team_mission)

    assert team.score == service.ALL_MCQ_CORRECT_BONUS
    assert team.mcq_points == service.ALL_MCQ_CORRECT_BONUS


def test_score_mission_pass_awards_all_bonuses_when_perfect():
    service = ScoringService()
    team = DummyTeam()
    team_mission = DummyTeamMission(hint_used=False, knowledge_answers=[DummyKnowledgeAnswer(True)])

    points = service.score_mission_pass(team, team_mission, mission=None, on_time=True)

    expected = (
        service.CHALLENGE_COMPLETE
        + service.NO_HINT_BONUS
        + service.FIRST_ATTEMPT_BONUS
        + service.FINISH_BOOTH_BONUS
        + service.PERFECT_BOOTH_BONUS
        + service.FRAGMENT_BONUS
    )
    assert points == expected
    assert team.score == points
    assert team_mission.score == points
    # Fragment bonus is tracked as its own "cipher" line item, distinct from the coding score.
    assert team.cipher_points == service.FRAGMENT_BONUS
    assert team.coding_points == points - service.FRAGMENT_BONUS


def test_score_mission_pass_no_perfect_bonus_if_hint_used():
    service = ScoringService()
    team = DummyTeam()
    team_mission = DummyTeamMission(hint_used=True, knowledge_answers=[DummyKnowledgeAnswer(True)])

    points = service.score_mission_pass(team, team_mission, mission=None, on_time=True)

    expected = (
        service.CHALLENGE_COMPLETE
        + service.FIRST_ATTEMPT_BONUS
        + service.FINISH_BOOTH_BONUS
        + service.FRAGMENT_BONUS
    )
    assert points == expected


def test_score_mission_pass_no_perfect_bonus_if_not_all_mcq_correct():
    service = ScoringService()
    team = DummyTeam()
    team_mission = DummyTeamMission(
        hint_used=False,
        knowledge_answers=[DummyKnowledgeAnswer(True), DummyKnowledgeAnswer(False)],
    )

    points = service.score_mission_pass(team, team_mission, mission=None, on_time=True)

    expected = (
        service.CHALLENGE_COMPLETE
        + service.NO_HINT_BONUS
        + service.FIRST_ATTEMPT_BONUS
        + service.FINISH_BOOTH_BONUS
        + service.FRAGMENT_BONUS
    )
    assert points == expected


def test_score_mission_pass_no_first_attempt_bonus_after_a_failed_retry():
    service = ScoringService()
    team = DummyTeam()
    team_mission = DummyTeamMission(hint_used=False, attempts=1)

    points = service.score_mission_pass(team, team_mission, mission=None, on_time=True)

    expected = (
        service.CHALLENGE_COMPLETE
        + service.NO_HINT_BONUS
        + service.FINISH_BOOTH_BONUS
        + service.FRAGMENT_BONUS
    )
    assert points == expected


def test_score_mission_pass_includes_time_bonus_for_a_fast_finish():
    service = ScoringService()
    team = DummyTeam()
    team_mission = DummyTeamMission(hint_used=False, elapsed_seconds=120)

    points = service.score_mission_pass(team, team_mission, mission=None, on_time=True)

    base = (
        service.CHALLENGE_COMPLETE
        + service.NO_HINT_BONUS
        + service.FIRST_ATTEMPT_BONUS
        + service.FINISH_BOOTH_BONUS
        + service.FRAGMENT_BONUS
    )
    assert points == base + 20  # <= 300s tier
    assert team.time_bonus_points == 20


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

    assert second == round(service.CHALLENGE_COMPLETE * 0.7) - round(
        service.CHALLENGE_COMPLETE * 0.4
    )
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
    # up with exactly what a clean 100% first-try pass would have earned in total -- not the
    # partial credit PLUS a full second base amount. This invariant holds regardless of the
    # exact bonus values, since score_auto_graded_partial never awards any of the pass-only
    # bonuses (no_hint/first_attempt/finish_booth/fragment) itself.
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
        service.CODING_CHALLENGE_PASS
        + service.NO_HINT_BONUS
        + service.FIRST_ATTEMPT_BONUS
        + service.FINISH_BOOTH_BONUS
        + service.FRAGMENT_BONUS
    )
    assert partial_total + pass_points == clean_pass_points
    assert team.score == clean_pass_points
    assert team_mission.best_percent_score == 100


def test_score_auto_graded_pass_adds_the_challenges_configured_bonus_points():
    service = ScoringService()
    team = DummyTeam()
    team_mission = DummyTeamMission()
    challenge = DummyChallenge(bonus_points=7)

    points = service.score_auto_graded_pass(
        team, team_mission, challenge, DummyGradingResult(100), on_time=True
    )

    expected = (
        service.CODING_CHALLENGE_PASS
        + service.NO_HINT_BONUS
        + service.FIRST_ATTEMPT_BONUS
        + service.FINISH_BOOTH_BONUS
        + service.FRAGMENT_BONUS
        + 7
    )
    assert points == expected


def test_apply_hint_penalty_deducts_score_integrity_and_increments_budget():
    service = ScoringService()
    team = DummyTeam(score=100, integrity=100, hints_used=0)
    team_mission = DummyTeamMission()

    service.apply_hint_penalty(team, team_mission)

    assert team.score == 100 - service.HINT_PENALTY
    assert team.integrity == 100 - service.HINT_INTEGRITY_PENALTY
    assert team.hints_used == 1
    assert team.hint_points == -service.HINT_PENALTY
    assert team_mission.hint_used is True
    assert team_mission.hints_taken == 1


def test_apply_hint_penalty_is_flat_per_hint_and_stacks_up_to_the_per_booth_cap():
    service = ScoringService()
    team = DummyTeam(score=100, integrity=100)
    team_mission = DummyTeamMission()

    service.apply_hint_penalty(team, team_mission)
    service.apply_hint_penalty(team, team_mission)
    service.apply_hint_penalty(team, team_mission)

    assert team_mission.hints_taken == service.MAX_HINTS_PER_BOOTH == 3
    assert team.score == 100 - (service.HINT_PENALTY * 3)
    assert team.integrity == 100 - (service.HINT_INTEGRITY_PENALTY * 3)


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
