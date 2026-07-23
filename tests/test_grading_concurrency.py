"""Regression coverage for unbounded grading subprocess creation: a burst of simultaneous
submissions must not spawn more child processes at once than the configured cap. subprocess.run
itself is faked (tracking overlapping calls via a lock-protected counter) so the test is fast
and deterministic instead of depending on real process scheduling."""
import threading
import time

import app.services.grading_service as grading_service
from app.services.grading_service import GradingEngine


class _FakeCompleted:
    returncode = 0
    stdout = "ok\n"
    stderr = ""


def test_grading_bounds_concurrent_subprocess_creation(monkeypatch):
    monkeypatch.setattr(grading_service, "_grading_slots", threading.Semaphore(2))

    active = 0
    max_active = 0
    lock = threading.Lock()

    def fake_run(*args, **kwargs):
        nonlocal active, max_active
        with lock:
            active += 1
            max_active = max(max_active, active)
        time.sleep(0.15)
        with lock:
            active -= 1
        return _FakeCompleted()

    monkeypatch.setattr(grading_service.subprocess, "run", fake_run)

    engine = GradingEngine()
    threads = [
        threading.Thread(target=engine._run_once, args=("print(1)", "", 5)) for _ in range(6)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Before the fix, all 6 fake subprocess calls overlap freely (max_active == 6). With the
    # semaphore gate in place, no more than 2 (the configured cap in this test) ever run at once.
    assert max_active <= 2
