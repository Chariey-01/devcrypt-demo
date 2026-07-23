class ScoringService:
    CHALLENGE_COMPLETE = 20
    NO_HINT_BONUS = 5
    ON_TIME_BONUS = 5
    PERFECT_BONUS = 10
    HINT_PENALTY = 15
    OVERRIDE_PENALTY = 30
    CHECKPOINT_BONUS = 25
    # Deliberately small and flat — participation credit for walking away from a booth, never
    # worth more than even a weak partial-credit attempt would have earned. See
    # score_soft_lock for why this can never be paid twice for the same booth.
    SOFT_LOCK_PARTICIPATION = 5
    # Trivia reward, not mission progress — deliberately smaller than any coding-challenge
    # scoring path, so Knowledge Check can never be a meaningful substitute for solving the
    # actual booth.
    KNOWLEDGE_CORRECT = 3

    RETRY_INTEGRITY_PENALTY = 5
    HINT_INTEGRITY_PENALTY = 10
    OVERRIDE_INTEGRITY_PENALTY = 20

    def award_points(self, team, points, reason=None):
        team.score = max(0, team.score + points)
        return team.score

    def apply_integrity_penalty(self, team, percent):
        team.integrity = max(0, team.integrity - percent)
        return team.integrity

    def score_knowledge_correct(self, team, team_mission):
        self.award_points(team, self.KNOWLEDGE_CORRECT, "knowledge_correct")
        team_mission.score += self.KNOWLEDGE_CORRECT

    def score_mission_pass(self, team, team_mission, mission, on_time):
        points = self.CHALLENGE_COMPLETE
        if not team_mission.hint_used:
            points += self.NO_HINT_BONUS
        if on_time:
            points += self.ON_TIME_BONUS
        if not team_mission.hint_used and on_time:
            points += self.PERFECT_BONUS
        self.award_points(team, points, "mission_pass")
        team_mission.score += points
        return points

    def score_auto_graded_pass(self, team, team_mission, challenge, grading_result, on_time):
        # Weighted-percent base, same bonus structure as score_mission_pass, plus a
        # challenge-configured bonus on top. The base only ever pays the *incremental* amount
        # beyond whatever score_auto_graded_partial already awarded on earlier below-threshold
        # attempts (best_percent_score) — otherwise a team that failed at 60% then passed at
        # 100% would double-collect the first 60%'s worth of base credit.
        old_base = round(self.CHALLENGE_COMPLETE * team_mission.best_percent_score / 100)
        new_base = round(self.CHALLENGE_COMPLETE * grading_result.percent_score / 100)
        team_mission.best_percent_score = max(team_mission.best_percent_score, grading_result.percent_score)
        points = max(0, new_base - old_base)
        if not team_mission.hint_used:
            points += self.NO_HINT_BONUS
        if on_time:
            points += self.ON_TIME_BONUS
        if grading_result.percent_score == 100:
            points += self.PERFECT_BONUS
        points += challenge.bonus_points or 0
        self.award_points(team, points, "auto_graded_pass")
        team_mission.score += points
        return points

    def score_auto_graded_partial(self, team, team_mission, grading_result):
        # A below-threshold submission still earns points proportional to tests passed — but
        # only the *delta* against this booth's best percent_score so far, never the full
        # amount again, so grinding the same (or a worse) solution through the retry cooldown
        # can't double-count score. No Fragment, no hint/on-time/perfect bonuses, no status
        # change — those are exclusively score_auto_graded_pass's job once the team actually
        # clears pass_threshold.
        if grading_result.percent_score <= team_mission.best_percent_score:
            return 0
        old_points = round(self.CHALLENGE_COMPLETE * team_mission.best_percent_score / 100)
        new_points = round(self.CHALLENGE_COMPLETE * grading_result.percent_score / 100)
        delta = new_points - old_points
        team_mission.best_percent_score = grading_result.percent_score
        if delta:
            self.award_points(team, delta, "auto_graded_partial")
            team_mission.score += delta
        return delta

    def score_soft_lock(self, team, team_mission):
        self.award_points(team, self.SOFT_LOCK_PARTICIPATION, "soft_lock")
        team_mission.score += self.SOFT_LOCK_PARTICIPATION

    def apply_retry_penalty(self, team, team_mission):
        team_mission.attempts += 1
        if team_mission.attempts > 1:
            self.apply_integrity_penalty(team, self.RETRY_INTEGRITY_PENALTY)
            team_mission.integrity_delta -= self.RETRY_INTEGRITY_PENALTY

    def apply_hint_penalty(self, team, team_mission):
        self.award_points(team, -self.HINT_PENALTY, "hint_used")
        team_mission.score -= self.HINT_PENALTY
        self.apply_integrity_penalty(team, self.HINT_INTEGRITY_PENALTY)
        team_mission.integrity_delta -= self.HINT_INTEGRITY_PENALTY
        team_mission.hint_used = True
        team.hints_used += 1

    def apply_override_penalty(self, team, team_mission):
        self.award_points(team, -self.OVERRIDE_PENALTY, "mission_override")
        team_mission.score -= self.OVERRIDE_PENALTY
        self.apply_integrity_penalty(team, self.OVERRIDE_INTEGRITY_PENALTY)
        team_mission.integrity_delta -= self.OVERRIDE_INTEGRITY_PENALTY

    def score_checkpoint(self, team):
        self.award_points(team, self.CHECKPOINT_BONUS, "checkpoint_stamp")
