from submission import find_profile_issues


def test_valid_profile_has_no_issues():
    profile = {
        "application_name": "Amina Noor",
        "passport_name": "  amina   noor ",
        "subject_scores": [80, 70, 90],
        "claimed_average": 80,
        "graduation_year": 2025,
        "application_year": 2026,
    }
    assert find_profile_issues(profile) == []


def test_detects_name_and_average_mismatch_in_required_order():
    profile = {
        "application_name": "Brian Otieno",
        "passport_name": "Bryan Otieno",
        "subject_scores": [70, 80, 90],
        "claimed_average": 86,
        "graduation_year": 2024,
        "application_year": 2026,
    }
    assert find_profile_issues(profile) == ["NAME_MISMATCH", "AVERAGE_MISMATCH"]


def test_invalid_scores_and_future_graduation():
    profile = {
        "application_name": "Nia Kamau",
        "passport_name": "Nia Kamau",
        "subject_scores": [82, 105, 75],
        "claimed_average": 87,
        "graduation_year": 2027,
        "application_year": 2026,
    }
    assert find_profile_issues(profile) == ["INVALID_SCORE", "FUTURE_GRADUATION"]
