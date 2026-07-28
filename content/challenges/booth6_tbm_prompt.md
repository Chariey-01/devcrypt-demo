# TBM Limited Challenge: Brute Force Detection

## Problem statement

You work for T1, a cybersecurity company protecting enterprise systems.

Your challenge is to write a function that analyzes authentication logs to detect a brute-force attack.

A brute-force attack occurs when the SAME IP address fails to log in 5 or more times in a row (consecutive failures).

Edit `submission.py` and complete:

```python
def detect_brute_force(logs):
    ...
```

Input:

A list of log entries (strings) formatted as:
`"IP_ADDRESS login success"` or `"IP_ADDRESS login failed"`

Output:

Return `True` if a brute-force attack is detected, `False` otherwise.

## Example

```python
logs = [
    "192.168.1.10 login failed",
    "192.168.1.10 login failed",
    "192.168.1.10 login failed",
    "192.168.1.10 login failed",
    "192.168.1.10 login failed"
]
detect_brute_force(logs)  # True
```

## Example 2

```python
logs = [
    "192.168.1.10 login failed",
    "192.168.1.20 login success",
    "192.168.1.10 login failed"
]
detect_brute_force(logs)  # False
```
