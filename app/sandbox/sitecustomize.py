"""Auto-imported by the Python interpreter at startup (via PYTHONPATH, see
GradingEngine._sandbox_env in app/services/grading_service.py) for every submission subprocess.
Blocks the standard-library socket path so a submission can't make outbound network calls
(exfiltrating data, hitting an external service to fake a result, etc.).

This is an application-layer block, not kernel-enforced isolation: it patches
socket.socket/socket.create_connection, which stops requests/urllib3/http.client and anything
else built on the stdlib socket module, but a submission using ctypes or raw syscalls to open a
socket directly would bypass it. Real kernel-level network isolation needs a network namespace
or container, which is a larger follow-up (see docs/SYSTEM_DESIGN.md) -- not assumed available
on the current single-process Railway/Nixpacks deployment.
"""

import socket


class _NetworkDisabledError(OSError):
    pass


def _blocked(*args, **kwargs):
    raise _NetworkDisabledError("Network access is disabled for graded submissions.")


socket.socket = _blocked  # type: ignore[misc,assignment]  # deliberate, see module docstring
socket.create_connection = _blocked
socket.create_server = _blocked
