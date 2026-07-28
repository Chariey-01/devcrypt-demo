# t1_test_suite.py
import pytest
from t1_challenge import detect_brute_force


def test_brute_force_detected():
    """Test: 5 consecutive failures = attack"""
    logs = [
        "192.168.1.100 login failed",
        "192.168.1.100 login failed",
        "192.168.1.100 login failed",
        "192.168.1.100 login failed",
        "192.168.1.100 login failed"
    ]
    assert detect_brute_force(logs) == True


def test_four_failures_not_attack():
    """Test: Only 4 failures = not an attack"""
    logs = [
        "192.168.1.50 login failed",
        "192.168.1.50 login failed",
        "192.168.1.50 login failed",
        "192.168.1.50 login failed"
    ]
    assert detect_brute_force(logs) == False


def test_success_breaks_chain():
    """Test: A success resets the counter"""
    logs = [
        "192.168.1.75 login failed",
        "192.168.1.75 login failed",
        "192.168.1.75 login failed",
        "192.168.1.75 login success",
        "192.168.1.75 login failed",
        "192.168.1.75 login failed",
        "192.168.1.75 login failed"
    ]
    assert detect_brute_force(logs) == False


def test_different_ips_not_attack():
    """Test: Failures from different IPs don't count"""
    logs = [
        "192.168.1.10 login failed",
        "192.168.1.20 login failed",
        "192.168.1.30 login failed",
        "192.168.1.40 login failed",
        "192.168.1.50 login failed"
    ]
    assert detect_brute_force(logs) == False


def test_six_failures_is_attack():
    """Test: 6+ consecutive failures = attack"""
    logs = [
        "10.0.0.1 login failed",
        "10.0.0.1 login failed",
        "10.0.0.1 login failed",
        "10.0.0.1 login failed",
        "10.0.0.1 login failed",
        "10.0.0.1 login failed"
    ]
    assert detect_brute_force(logs) == True


def test_empty_logs():
    """Test: No logs = no attack"""
    assert detect_brute_force([]) == False


def test_only_successes():
    """Test: Only successful logins = no attack"""
    logs = [
        "192.168.1.5 login success",
        "192.168.1.5 login success",
        "192.168.1.5 login success"
    ]
    assert detect_brute_force(logs) == False
