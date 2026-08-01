from app.services.grading_service import GradingEngine


class DummyChallenge:
    def __init__(self, test_code, pass_threshold=100, time_limit_seconds=5, bonus_points=0):
        self.test_cases = []
        self.test_code = test_code
        self.grading_mode = "pytest"
        self.pass_threshold = pass_threshold
        self.time_limit_seconds = time_limit_seconds
        self.bonus_points = bonus_points


ADD_MULTIPLY_TEST = """
from submission import add, multiply


def test_add():
    assert add(2, 3) == 5


def test_multiply():
    assert multiply(2, 3) == 6
"""

CORRECT_CODE = "def add(a, b):\n    return a + b\n\n\ndef multiply(a, b):\n    return a * b\n"
MULTIPLY_BROKEN_CODE = (
    "def add(a, b):\n    return a + b\n\n\ndef multiply(a, b):\n    return a + b\n"
)
SYNTAX_ERROR_CODE = "def add(a, b) return a + b\n"


def test_run_all_tests_pytest_mode_all_pass():
    engine = GradingEngine()
    challenge = DummyChallenge(ADD_MULTIPLY_TEST)

    result = engine.run_all_tests(challenge, CORRECT_CODE)

    assert result.total_tests == 2
    assert result.passed_tests == 2
    assert result.percent_score == 100
    assert result.passed_threshold is True
    assert {r.name for r in result.results} == {"test_add", "test_multiply"}
    assert all(r.visibility == "hidden" for r in result.results)


def test_run_all_tests_pytest_mode_partial_fail():
    engine = GradingEngine()
    challenge = DummyChallenge(ADD_MULTIPLY_TEST, pass_threshold=80)

    result = engine.run_all_tests(challenge, MULTIPLY_BROKEN_CODE)

    assert result.total_tests == 2
    assert result.passed_tests == 1
    assert result.percent_score == 50
    assert result.passed_threshold is False
    failed = [r for r in result.results if not r.passed]
    assert len(failed) == 1
    assert failed[0].name == "test_multiply"
    assert failed[0].failure_message == "Test did not pass."
    # Hidden results never leak assertion internals to the player-facing serializer.
    assert failed[0].input_data is None
    assert failed[0].expected_output is None
    assert failed[0].actual_output is None


def test_run_visible_tests_pytest_mode_runs_the_full_suite():
    # No visible/hidden split exists in a raw pytest file -- "Run Tests" is the same full suite
    # as an actual submit, just without persisting a CodeSubmission (that's missions.py's job).
    engine = GradingEngine()
    challenge = DummyChallenge(ADD_MULTIPLY_TEST)

    result = engine.run_visible_tests(challenge, CORRECT_CODE)

    assert result.total_tests == 2
    assert result.passed_tests == 2


def test_pytest_mode_collection_failure_is_reported_as_a_failed_result_not_a_crash():
    # Confirmed against real pytest --junitxml output: a syntax error in the player's submitted
    # module (which the test file imports) produces exactly one synthetic <testcase> named after
    # the test module itself, with an <error> child -- not zero <testcase> elements. The
    # "collection" pseudo-result in _run_pytest_suite is a defensive fallback for the rarer case
    # of literally no <testcase> in the report at all (e.g. a pytest-internal crash), not this one.
    engine = GradingEngine()
    challenge = DummyChallenge(ADD_MULTIPLY_TEST)

    result = engine.run_all_tests(challenge, SYNTAX_ERROR_CODE)

    assert result.total_tests == 1
    assert result.passed_tests == 0
    assert result.percent_score == 0
    assert result.passed_threshold is False
    assert result.results[0].passed is False
    assert result.results[0].failure_message == "Test did not pass."


def test_pytest_mode_timeout_is_reported_as_a_failed_result_not_a_crash():
    engine = GradingEngine()
    challenge = DummyChallenge(ADD_MULTIPLY_TEST, time_limit_seconds=1)
    # A submission that sleeps past the per-suite timeout.
    slow_code = "import time\ntime.sleep(30)\n\n\ndef add(a, b):\n    return a + b\n\n\ndef multiply(a, b):\n    return a * b\n"

    result = engine.run_all_tests(challenge, slow_code)

    assert result.total_tests == 1
    assert result.passed_tests == 0
    assert result.results[0].name == "suite"
    assert result.results[0].failure_message == "Suite timed out."


def test_run_all_tests_non_pytest_mode_is_unaffected():
    # A challenge with no grading_mode attribute at all (matching the DummyChallenge doubles in
    # tests/test_grading.py) must keep working exactly as before -- getattr(..., None), not
    # challenge.grading_mode, is what makes this safe.
    class LegacyDummyChallenge:
        def __init__(self):
            self.test_cases = []
            self.pass_threshold = 100
            self.time_limit_seconds = 5

    engine = GradingEngine()
    result = engine.run_all_tests(LegacyDummyChallenge(), "print('unused')")
    assert result.total_tests == 0
    assert result.percent_score == 0
