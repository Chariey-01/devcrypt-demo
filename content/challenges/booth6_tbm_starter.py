def detect_brute_force(logs):
    """
    Detect if any IP address has 5+ consecutive login failures.

    Args:
        logs: List of strings like "192.168.1.10 login failed"

    Returns:
        True if brute-force detected, False otherwise
    """
    # Add your code here
    pass


# Test your code (optional, for practice)
if __name__ == "__main__":
    test_logs = [
        "192.168.1.100 login failed",
        "192.168.1.100 login failed",
        "192.168.1.100 login failed",
        "192.168.1.100 login failed",
        "192.168.1.100 login failed"
    ]
    print(detect_brute_force(test_logs))  # Should print True
