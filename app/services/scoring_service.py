class ScoringService:
    # ---------------------------------------------------------------------
    # Knowledge Check
    # ---------------------------------------------------------------------
    KNOWLEDGE_CORRECT = 10
    # Awarded once, the moment the last assigned question in a booth's Knowledge Check is
    # answered, if every one of them was correct (see missions.answer_knowledge_question).
    ALL_MCQ_CORRECT_BONUS = 20

    # ---------------------------------------------------------------------
    # Coding challenge
    # ---------------------------------------------------------------------
    # Flat reward for actually clearing pass_threshold (>=80% hidden tests) — replaces the old
    # weighted-percent-of-20 "CHALLENGE_COMPLETE" base for the *passing* submission specifically.
    # Legacy per-mission bonus_points (Agent-configured) still applies on top, unchanged.
    CODING_CHALLENGE_PASS = 100
    # A below-threshold submission still earns proportional partial credit on this same 0-20
    # scale it always has (see score_auto_graded_partial) — CODING_CHALLENGE_PASS above pays out
    # the *remainder* up to 100 once the team finally clears the threshold, so partial credit
    # already paid on this scale is never double-counted (see score_auto_graded_pass).
    CHALLENGE_COMPLETE = 20
    # Zero failed attempts recorded against this booth before the pass (team_mission.attempts is
    # only incremented by apply_retry_penalty, which only ever runs on a *failed* submission —
    # so `attempts == 0` at pass time means this submission was the first one).
    FIRST_ATTEMPT_BONUS = 20
    # Paired 1:1 with the Fragment row complete_mission always inserts on a real pass — these are
    # separate named line items for the dashboard breakdown, not two different trigger points.
    FRAGMENT_BONUS = 50
    FINISH_BOOTH_BONUS = 30
    # All four "did great" conditions in one booth: zero hints, on time, every MCQ correct, and
    # passed on the first submission. Additive on top of whichever of those already paid their
    # own individual bonus — a deliberate "extra" for the live event, not a replacement for them.
    PERFECT_BOOTH_BONUS = 50

    # ---------------------------------------------------------------------
    # Time — absolute elapsed-time tiers from booth start to the deciding submission,
    # independent of whatever per-mission time_limit an Agent configured. Evaluated in order;
    # first tier whose ceiling the elapsed time falls within wins. Replaces the old flat
    # ON_TIME_BONUS entirely — same "reward speed" intent, finer-grained.
    # ---------------------------------------------------------------------
    TIME_BONUS_TIERS = (
        (300, 20),   # <= 5 min
        (480, 10),   # <= 8 min
        (600, 5),    # <= 10 min
    )                # > 10 min -> 0, handled by falling through

    # ---------------------------------------------------------------------
    # Hints — sequential, per booth, capped at MAX_HINTS_PER_BOOTH. Both slots cost the same
    # flat amount (a first hint costing as much as a whole extra hint later was judged too
    # punishing — see the product discussion this was built against).
    # ---------------------------------------------------------------------
    MAX_HINTS_PER_BOOTH = 2
    HINT_PENALTY = 15
    HINT_INTEGRITY_PENALTY = 10

    # ---------------------------------------------------------------------
    # Legacy / unchanged
    # ---------------------------------------------------------------------
    NO_HINT_BONUS = 5
    OVERRIDE_PENALTY = 30
    CHECKPOINT_BONUS = 25
    # Deliberately small and flat — participation credit for walking away from a booth, never
    # worth more than even a weak partial-credit attempt would have earned. See
    # score_soft_lock for why this can never be paid twice for the same booth.
    SOFT_LOCK_PARTICIPATION = 5

    RETRY_INTEGRITY_PENALTY = 5
    OVERRIDE_INTEGRITY_PENALTY = 20

    def award_points(self, team, points, reason=None, category=None):
        team.score = max(0, team.score + points)
        if category == "mcq":
            team.mcq_points += points
        elif category == "coding":
            team.coding_points += points
        elif category == "cipher":
            team.cipher_points += points
        elif category == "hint":
            team.hint_points += points
        elif category == "time":
            team.time_bonus_points += points
        return team.score

    def apply_integrity_penalty(self, team, percent):
        team.integrity = max(0, team.integrity - percent)
        return team.integrity

    def time_bonus_for_elapsed(self, elapsed_seconds):
        if elapsed_seconds is None:
            return 0
        for max_seconds, bonus in self.TIME_BONUS_TIERS:
            if elapsed_seconds <= max_seconds:
                return bonus
        return 0

    def score_knowledge_correct(self, team, team_mission):
        self.award_points(team, self.KNOWLEDGE_CORRECT, "knowledge_correct", category="mcq")
        team_mission.score += self.KNOWLEDGE_CORRECT

    def award_all_mcq_correct_bonus(self, team, team_mission):
        self.award_points(team, self.ALL_MCQ_CORRECT_BONUS, "all_mcq_correct", category="mcq")
        team_mission.score += self.ALL_MCQ_CORRECT_BONUS

    def _all_mcq_correct(self, team_mission):
        answers = team_mission.knowledge_answers
        return bool(answers) and all(a.is_correct for a in answers)

    def score_mission_pass(self, team, team_mission, mission, on_time):
        # Legacy manual-review / cipher-answer path (grading_mode != "auto") — still uses the
        # flat CHALLENGE_COMPLETE base, since it never had a percent_score to scale against in
        # the first place. Gets the same new bonus set as the auto-graded path below.
        first_attempt = team_mission.attempts == 0
        all_correct = self._all_mcq_correct(team_mission)

        points = self.CHALLENGE_COMPLETE
        if not team_mission.hint_used:
            points += self.NO_HINT_BONUS
        if first_attempt:
            points += self.FIRST_ATTEMPT_BONUS
        points += self.FINISH_BOOTH_BONUS
        if not team_mission.hint_used and on_time and all_correct and first_attempt:
            points += self.PERFECT_BOOTH_BONUS
        self.award_points(team, points, "mission_pass", category="coding")
        team_mission.score += points

        self.award_points(team, self.FRAGMENT_BONUS, "fragment_collected", category="cipher")
        team_mission.score += self.FRAGMENT_BONUS
        points += self.FRAGMENT_BONUS

        time_bonus = self.time_bonus_for_elapsed(team_mission.elapsed_seconds)
        if time_bonus:
            self.award_points(team, time_bonus, "time_bonus", category="time")
            team_mission.score += time_bonus
        return points + time_bonus

    def score_auto_graded_pass(self, team, team_mission, challenge, grading_result, on_time):
        # Flat CODING_CHALLENGE_PASS reward, minus whatever partial credit this booth already
        # earned on the old 0-20 scale via score_auto_graded_partial on earlier below-threshold
        # attempts — so a team that improved from 60% to finally passing collects 100 total,
        # never 100 plus the partial credit it was already paid along the way.
        already_paid = round(self.CHALLENGE_COMPLETE * team_mission.best_percent_score / 100)
        team_mission.best_percent_score = max(team_mission.best_percent_score, grading_result.percent_score)
        base = max(0, self.CODING_CHALLENGE_PASS - already_paid)

        first_attempt = team_mission.attempts == 0
        all_correct = self._all_mcq_correct(team_mission)

        points = base
        if not team_mission.hint_used:
            points += self.NO_HINT_BONUS
        if first_attempt:
            points += self.FIRST_ATTEMPT_BONUS
        points += self.FINISH_BOOTH_BONUS
        if not team_mission.hint_used and on_time and all_correct and first_attempt:
            points += self.PERFECT_BOOTH_BONUS
        points += challenge.bonus_points or 0

        self.award_points(team, points, "auto_graded_pass", category="coding")
        team_mission.score += points

        self.award_points(team, self.FRAGMENT_BONUS, "fragment_collected", category="cipher")
        team_mission.score += self.FRAGMENT_BONUS
        points += self.FRAGMENT_BONUS

        time_bonus = self.time_bonus_for_elapsed(team_mission.elapsed_seconds)
        if time_bonus:
            self.award_points(team, time_bonus, "time_bonus", category="time")
            team_mission.score += time_bonus

        return points + time_bonus

    def score_auto_graded_partial(self, team, team_mission, grading_result):
        # A below-threshold submission still earns points proportional to tests passed — but
        # only the *delta* against this booth's best percent_score so far, never the full
        # amount again, so grinding the same (or a worse) solution through the retry cooldown
        # can't double-count score. No Fragment, no hint/time/perfect bonuses, no status
        # change — those are exclusively score_auto_graded_pass's job once the team actually
        # clears pass_threshold.
        if grading_result.percent_score <= team_mission.best_percent_score:
            return 0
        old_points = round(self.CHALLENGE_COMPLETE * team_mission.best_percent_score / 100)
        new_points = round(self.CHALLENGE_COMPLETE * grading_result.percent_score / 100)
        delta = new_points - old_points
        team_mission.best_percent_score = grading_result.percent_score
        if delta:
            self.award_points(team, delta, "auto_graded_partial", category="coding")
            team_mission.score += delta
        return delta

    def score_soft_lock(self, team, team_mission):
        self.award_points(team, self.SOFT_LOCK_PARTICIPATION, "soft_lock", category="coding")
        team_mission.score += self.SOFT_LOCK_PARTICIPATION

    def apply_retry_penalty(self, team, team_mission):
        team_mission.attempts += 1
        if team_mission.attempts > 1:
            self.apply_integrity_penalty(team, self.RETRY_INTEGRITY_PENALTY)
            team_mission.integrity_delta -= self.RETRY_INTEGRITY_PENALTY

    def apply_hint_penalty(self, team, team_mission):
        # Sequential, per booth: hints_taken counts 0..MAX_HINTS_PER_BOOTH for *this* booth.
        # Caller (missions.request_hint) is responsible for refusing once the cap is hit and
        # for handing back the correct hint text for the slot just paid for.
        self.award_points(team, -self.HINT_PENALTY, "hint_used", category="hint")
        team_mission.score -= self.HINT_PENALTY
        self.apply_integrity_penalty(team, self.HINT_INTEGRITY_PENALTY)
        team_mission.integrity_delta -= self.HINT_INTEGRITY_PENALTY
        team_mission.hint_used = True
        team_mission.hints_taken += 1
        team.hints_used += 1

    def apply_override_penalty(self, team, team_mission):
        self.award_points(team, -self.OVERRIDE_PENALTY, "mission_override", category="coding")
        team_mission.score -= self.OVERRIDE_PENALTY
        self.apply_integrity_penalty(team, self.OVERRIDE_INTEGRITY_PENALTY)
        team_mission.integrity_delta -= self.OVERRIDE_INTEGRITY_PENALTY

    def score_checkpoint(self, team):
        self.award_points(team, self.CHECKPOINT_BONUS, "checkpoint_stamp", category="coding")
