import resource
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

# NOTE on gevent + subprocess: earlier this routed subprocess.run() through
# gevent.get_hub().threadpool to avoid a suspected fork/greenlet interaction. That was wrong and
# broke every auto-graded submission under the real server (confirmed live): gevent.monkey.patch_
# all() replaces subprocess.run/Popen in place with its own cooperative version, whose child-
# watcher setup only works on the hub's own thread — dispatching it into a *worker* thread crashed
# with "child watchers are only available on the default loop", and even fetching the pre-patch
# original via monkey.get_original() didn't help, since that original run() still does a runtime
# global lookup of Popen and finds gevent's patched class either way. gevent's patched subprocess
# module is specifically designed to be called cooperatively from the hub thread — Popen.wait()
# yields to other greenlets (other requests, open WebSockets) while the child process runs, so a
# plain, direct subprocess.run() call below is correct and sufficient. No thread pool needed.


# Hard ceiling on total suite wall-clock, independent of any single test's timeout, so one
# submission can't starve a gunicorn worker for longer than this regardless of how many test
# cases an Agent configures.
MAX_SUITE_SECONDS = 30

# Sandbox resource limits applied to the child process via preexec_fn. This is OS-level
# isolation (timeout + rlimits), not container/namespace isolation — see SYSTEM_DESIGN.md
# section 13 for the explicit tradeoff this represents.
CPU_SECONDS_LIMIT = 5
ADDRESS_SPACE_BYTES_LIMIT = 256 * 1024 * 1024  # 256 MB
MAX_PROCESSES_LIMIT = 16


@dataclass
class TestCaseResult:
    name: str
    visibility: str
    passed: bool
    weight: int
    failure_message: str = None
    input_data: str = None
    expected_output: str = None
    actual_output: str = None
    error: str = None


@dataclass
class GradingResult:
    results: list = field(default_factory=list)
    total_tests: int = 0
    passed_tests: int = 0
    weighted_score: int = 0
    total_weight: int = 0
    percent_score: int = 0
    passed_threshold: bool = False


def _set_limits():
    # Runs in the child process after fork, before exec — this is what actually confines it.
    resource.setrlimit(resource.RLIMIT_CPU, (CPU_SECONDS_LIMIT, CPU_SECONDS_LIMIT))
    resource.setrlimit(resource.RLIMIT_AS, (ADDRESS_SPACE_BYTES_LIMIT, ADDRESS_SPACE_BYTES_LIMIT))
    resource.setrlimit(resource.RLIMIT_NPROC, (MAX_PROCESSES_LIMIT, MAX_PROCESSES_LIMIT))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


class GradingEngine:
    """Runs Python-only, sandboxed code submissions against a challenge's test cases.

    Isolation is OS-level subprocess confinement (timeout + rlimits, no network namespace,
    no container) — a deliberate tradeoff for a supervised booth setting, not adversarial-grade
    isolation. See SYSTEM_DESIGN.md for the full rationale. This class never imports or
    executes submitted code in-process.
    """

    def _run_once(self, code, input_data, timeout_seconds):
        with tempfile.TemporaryDirectory() as tmp_dir:
            script_path = Path(tmp_dir) / "submission.py"
            script_path.write_text(code)
            try:
                proc = subprocess.run(
                    [sys.executable, str(script_path)],
                    input=input_data or "",
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
                    cwd=tmp_dir,
                    env={"PATH": "/usr/bin:/bin"},
                    preexec_fn=_set_limits,
                )
            except subprocess.TimeoutExpired:
                return None, "Timed out."
            if proc.returncode != 0:
                return None, (proc.stderr or "Runtime error.").strip()[-500:]
            return proc.stdout.strip(), None

    def _run_test_cases(self, challenge, code, test_cases):
        results = []
        timeout_seconds = min(challenge.time_limit_seconds or 5, MAX_SUITE_SECONDS)
        remaining_budget = MAX_SUITE_SECONDS
        for tc in test_cases:
            per_test_timeout = min(timeout_seconds, max(remaining_budget, 0))
            if per_test_timeout <= 0:
                results.append(
                    TestCaseResult(
                        name=tc.name,
                        visibility=tc.visibility,
                        passed=False,
                        weight=tc.weight,
                        failure_message=tc.failure_message or "Suite time budget exceeded.",
                        error="suite_timeout",
                    )
                )
                continue
            output, error = self._run_once(code, tc.input_data, per_test_timeout)
            remaining_budget -= per_test_timeout
            passed = error is None and output == (tc.expected_output or "").strip()
            result = TestCaseResult(
                name=tc.name,
                visibility=tc.visibility,
                passed=passed,
                weight=tc.weight,
                error=error,
            )
            if tc.visibility == "visible":
                result.input_data = tc.input_data
                result.expected_output = tc.expected_output
                result.actual_output = output
            if not passed:
                result.failure_message = tc.failure_message or "Output did not match expected result."
            results.append(result)
        return results

    def _score(self, challenge, results):
        total_weight = sum(r.weight for r in results) or 1
        weighted_score = sum(r.weight for r in results if r.passed)
        percent = round((weighted_score / total_weight) * 100)
        return GradingResult(
            results=results,
            total_tests=len(results),
            passed_tests=sum(1 for r in results if r.passed),
            weighted_score=weighted_score,
            total_weight=total_weight,
            percent_score=percent,
            passed_threshold=percent >= (challenge.pass_threshold or 100),
        )

    def run_visible_tests(self, challenge, code):
        visible = [tc for tc in challenge.test_cases if tc.visibility == "visible"]
        return self._score(challenge, self._run_test_cases(challenge, code, visible))

    def run_all_tests(self, challenge, code):
        return self._score(challenge, self._run_test_cases(challenge, code, challenge.test_cases))
