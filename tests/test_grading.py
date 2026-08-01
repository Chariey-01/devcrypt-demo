from app.services.grading_service import GradingEngine


class DummyTestCase:
    def __init__(
        self,
        name,
        input_data,
        expected_output,
        weight=1,
        visibility="visible",
        failure_message=None,
    ):
        self.name = name
        self.input_data = input_data
        self.expected_output = expected_output
        self.weight = weight
        self.visibility = visibility
        self.failure_message = failure_message


class DummyChallenge:
    def __init__(self, test_cases, pass_threshold=100, time_limit_seconds=5, bonus_points=0):
        self.test_cases = test_cases
        self.pass_threshold = pass_threshold
        self.time_limit_seconds = time_limit_seconds
        self.bonus_points = bonus_points


DOUBLE_CODE = "print(int(input()) * 2)"


def test_run_all_tests_all_pass_scores_100_percent():
    engine = GradingEngine()
    challenge = DummyChallenge(
        [
            DummyTestCase("doubles 3", "3", "6"),
            DummyTestCase("doubles 5", "5", "10"),
        ]
    )
    result = engine.run_all_tests(challenge, DOUBLE_CODE)

    assert result.total_tests == 2
    assert result.passed_tests == 2
    assert result.percent_score == 100
    assert result.passed_threshold is True


def test_run_all_tests_computes_weighted_percentage_on_partial_failure():
    engine = GradingEngine()
    challenge = DummyChallenge(
        [
            DummyTestCase("doubles 3", "3", "6", weight=3),
            DummyTestCase("doubles wrong", "5", "999", weight=1),
        ],
        pass_threshold=80,
    )
    result = engine.run_all_tests(challenge, DOUBLE_CODE)

    assert result.passed_tests == 1
    assert result.total_weight == 4
    assert result.weighted_score == 3
    assert result.percent_score == 75
    assert result.passed_threshold is False  # 75% < 80% threshold


def test_run_visible_tests_excludes_hidden_cases():
    engine = GradingEngine()
    challenge = DummyChallenge(
        [
            DummyTestCase("visible", "3", "6", visibility="visible"),
            DummyTestCase("hidden", "5", "10", visibility="hidden"),
        ]
    )
    result = engine.run_visible_tests(challenge, DOUBLE_CODE)

    assert result.total_tests == 1
    assert result.results[0].name == "visible"


def test_hidden_test_results_omit_input_and_expected_output():
    engine = GradingEngine()
    challenge = DummyChallenge([DummyTestCase("hidden", "5", "10", visibility="hidden")])
    result = engine.run_all_tests(challenge, DOUBLE_CODE)

    hidden_result = result.results[0]
    assert hidden_result.input_data is None
    assert hidden_result.expected_output is None
    assert hidden_result.actual_output is None


def test_failing_test_uses_configured_failure_message():
    engine = GradingEngine()
    challenge = DummyChallenge(
        [DummyTestCase("wrong", "5", "999", failure_message="Check your doubling logic.")]
    )
    result = engine.run_all_tests(challenge, DOUBLE_CODE)

    assert result.results[0].passed is False
    assert result.results[0].failure_message == "Check your doubling logic."


def test_infinite_loop_times_out_and_fails():
    engine = GradingEngine()
    challenge = DummyChallenge([DummyTestCase("hang", "", "anything")], time_limit_seconds=1)
    result = engine.run_all_tests(challenge, "while True:\n    pass\n")

    assert result.passed_tests == 0
    assert result.results[0].error == "Timed out."


def test_runtime_error_fails_gracefully():
    engine = GradingEngine()
    challenge = DummyChallenge([DummyTestCase("boom", "", "anything")])
    result = engine.run_all_tests(challenge, "raise ValueError('boom')")

    assert result.passed_tests == 0
    assert result.results[0].error is not None
