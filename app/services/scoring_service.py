class ScoringService:
    MCQ_CORRECT = 10
    CHALLENGE_COMPLETE = 20
    NO_HINT_BONUS = 5
    ON_TIME_BONUS = 5
    PERFECT_BONUS = 10
    HINT_PENALTY = 15
    OVERRIDE_PENALTY = 30
    CHECKPOINT_BONUS = 25

    RETRY_INTEGRITY_PENALTY = 5
    HINT_INTEGRITY_PENALTY = 10
    OVERRIDE_INTEGRITY_PENALTY = 20

    def award_points(self, team, points, reason=None):
        team.score = max(0, team.score + points)
        return team.score

    def apply_integrity_penalty(self, team, percent):
        team.integrity = max(0, team.integrity - percent)
        return team.integrity

    def score_mcq_correct(self, team, team_mission):
        self.award_points(team, self.MCQ_CORRECT, "mcq_correct")
        team_mission.score += self.MCQ_CORRECT

    def score_mission_pass(self, team, team_mission, mission, all_mcqs_correct, on_time):
        points = self.CHALLENGE_COMPLETE
        if not team_mission.hint_used:
            points += self.NO_HINT_BONUS
        if on_time:
            points += self.ON_TIME_BONUS
        if all_mcqs_correct and not team_mission.hint_used and on_time:
            points += self.PERFECT_BONUS
        self.award_points(team, points, "mission_pass")
        team_mission.score += points
        return points

    def score_auto_graded_pass(self, team, team_mission, challenge, grading_result, on_time):
        # Weighted-percent base, same bonus structure as score_mission_pass, plus a
        # challenge-configured bonus on top. Kept separate from score_mission_pass so the
        # legacy manual-review scoring path is untouched.
        base = round(self.CHALLENGE_COMPLETE * grading_result.percent_score / 100)
        points = base
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
