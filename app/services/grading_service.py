import logging
import os
import pwd
import resource
import subprocess
import sys
import tempfile
import threading
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("devcrypt.grading")

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

# Bounds how many grading subprocesses may be running at once across ALL concurrent requests,
# so a burst of simultaneous submissions (e.g. 20 teams at once) can't spawn 20 concurrent
# 256MB child processes and exhaust the host. This gates subprocess *creation* only — the
# acquire/release still happens on the gevent hub greenlet like everything else here, it does
# NOT move subprocess.run() onto a worker thread (see the NOTE above: that's what broke grading
# under gunicorn -k gevent before). threading.Semaphore is used rather than gevent.lock.Semaphore
# so this module still works unpatched (e.g. under plain pytest) — gevent.monkey.patch_all()
# (app/__init__.py, run.py) makes it cooperative for free when it matters, same as every other
# stdlib lock in this codebase under the real server.
MAX_CONCURRENT_GRADING_PROCESSES = 8
_grading_slots = threading.Semaphore(MAX_CONCURRENT_GRADING_PROCESSES)


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


# Ships a sitecustomize.py the interpreter auto-imports at startup (see
# app/sandbox/sitecustomize.py for what it does and why) by putting its directory on the
# child's PYTHONPATH -- this is how the network block below is actually installed.
_SANDBOX_DIR = str(Path(__file__).resolve().parent.parent / "sandbox")

# Whether a privilege drop to a distinct, unprivileged user is even possible depends on whether
# this process itself is root — only root has CAP_SETUID to become a different user. Logged
# once at import time (not asserted, checked) so this is visible in the real deployment's boot
# log without having to shell into the box. Spike-and-confirm, per the security hardening plan:
# don't assume either answer.
_RUNNING_AS_ROOT = os.getuid() == 0
if _RUNNING_AS_ROOT:
    logger.warning(
        "grading subprocess parent runs as root (uid 0) -- dropping each submission to 'nobody' "
        "before exec (see _set_limits)."
    )
else:
    logger.info(
        "grading subprocess parent does not run as root (uid=%s) -- this process cannot switch "
        "a child to a different UID, so submission sandboxing here relies on rlimits + timeout "
        "+ the application-layer network block only, not a genuine privilege drop.",
        os.getuid(),
    )


def _set_limits():
    # Runs in the child process after fork, before exec — this is what actually confines it.
    if _RUNNING_AS_ROOT:
        # Only reached when the parent has root's CAP_SETUID (see _RUNNING_AS_ROOT above) --
        # drop to 'nobody' (present on virtually every Linux base image) so the child is a
        # genuinely different, unprivileged user, not just the same account with rlimits
        # attached. Best-effort: if 'nobody' doesn't exist on this image, fall through to the
        # same-UID rlimit-only confinement rather than crashing every submission.
        try:
            nobody = pwd.getpwnam("nobody")
            os.setgroups([])
            os.setgid(nobody.pw_gid)
            os.setuid(nobody.pw_uid)
        except (KeyError, PermissionError):
            pass
    resource.setrlimit(resource.RLIMIT_CPU, (CPU_SECONDS_LIMIT, CPU_SECONDS_LIMIT))
    resource.setrlimit(resource.RLIMIT_AS, (ADDRESS_SPACE_BYTES_LIMIT, ADDRESS_SPACE_BYTES_LIMIT))
    resource.setrlimit(resource.RLIMIT_NPROC, (MAX_PROCESSES_LIMIT, MAX_PROCESSES_LIMIT))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def _sandbox_env():
    return {"PATH": "/usr/bin:/bin", "PYTHONPATH": _SANDBOX_DIR, "PYTHONNOUSERSITE": "1"}


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
            with _grading_slots:
                try:
                    proc = subprocess.run(
                        [sys.executable, str(script_path)],
                        input=input_data or "",
                        capture_output=True,
                        text=True,
                        timeout=timeout_seconds,
                        cwd=tmp_dir,
                        env=_sandbox_env(),
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
            passed_threshold=percent >= (challenge.pass_threshold or 80),
        )

    def run_visible_tests(self, challenge, code):
        # getattr(..., None), not challenge.grading_mode: test doubles in tests/test_grading.py
        # and tests/test_grading_concurrency.py don't define grading_mode at all, and must keep
        # falling through to the TestCase path below unchanged.
        if getattr(challenge, "grading_mode", None) == "pytest":
            # No visible/hidden split exists in a raw pytest file -- "Run Tests" runs the same
            # full hidden suite as an actual submit (see _run_pytest_suite's visibility="hidden"
            # on every result: individual assertions/expected values are still never revealed,
            # only names and a pass/fail count, via the existing hidden-TestCase suppression in
            # missions._serialize_grading_results).
            return self._run_pytest_suite(challenge, code)
        visible = [tc for tc in challenge.test_cases if tc.visibility == "visible"]
        return self._score(challenge, self._run_test_cases(challenge, code, visible))

    def run_all_tests(self, challenge, code):
        if getattr(challenge, "grading_mode", None) == "pytest":
            return self._run_pytest_suite(challenge, code)
        return self._score(challenge, self._run_test_cases(challenge, code, challenge.test_cases))

    def _parse_junit_report(self, report_path):
        """Returns a list of TestCaseResult from a pytest --junitxml report. Empty list means
        no <testcase> elements were found at all -- typically a collection failure (e.g. a
        syntax error in the submission breaks `import submission` before any test can run)."""
        if not report_path.exists():
            return []
        root = ET.parse(report_path).getroot()
        results = []
        for tc in root.findall(".//testcase"):
            passed = tc.find("failure") is None and tc.find("error") is None
            results.append(
                TestCaseResult(
                    name=tc.get("name") or "test",
                    visibility="hidden",
                    passed=passed,
                    weight=1,
                    failure_message=None if passed else "Test did not pass.",
                )
            )
        return results

    def _run_pytest_suite(self, challenge, code):
        # Whole-suite timeout (pytest runs every test within one process invocation, unlike the
        # per-TestCase loop in _run_test_cases) -- same MAX_SUITE_SECONDS ceiling either way.
        timeout_seconds = min(challenge.time_limit_seconds or 5, MAX_SUITE_SECONDS)
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            (tmp_path / "submission.py").write_text(code)
            (tmp_path / "test_submission.py").write_text(challenge.test_code or "")
            report_path = tmp_path / "report.xml"
            with _grading_slots:
                try:
                    proc = subprocess.run(
                        [
                            sys.executable, "-m", "pytest", "test_submission.py",
                            "--tb=no", "-q", f"--junitxml={report_path}", "-p", "no:cacheprovider",
                        ],
                        capture_output=True,
                        text=True,
                        timeout=timeout_seconds,
                        cwd=tmp_dir,
                        env=_sandbox_env(),
                        preexec_fn=_set_limits,
                    )
                except subprocess.TimeoutExpired:
                    return self._score(
                        challenge,
                        [
                            TestCaseResult(
                                name="suite", visibility="hidden", passed=False, weight=1,
                                failure_message="Suite timed out.", error="timeout",
                            )
                        ],
                    )
                results = self._parse_junit_report(report_path)
                if not results:
                    # Collection failed before any test could run (syntax error, crash, etc.) --
                    # one failed pseudo-result, not a silently-empty/vacuously-100%-passing suite.
                    # Diagnostic tail goes in .error, which is never player-facing.
                    results = [
                        TestCaseResult(
                            name="collection", visibility="hidden", passed=False, weight=1,
                            failure_message="Code failed to run (syntax error or crash).",
                            error=(proc.stdout + proc.stderr).strip()[-500:],
                        )
                    ]
                return self._score(challenge, results)
