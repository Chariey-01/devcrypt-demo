from scripts.import_challenge_content import (
    BoothFileSetError,
    apply_plan,
    build_plan,
    normalize_test_module_import,
)


# ---------------------------------------------------------------------------
# normalize_test_module_import
# ---------------------------------------------------------------------------

def test_normalize_test_module_import_rewrites_a_single_foreign_module():
    test_code = "from t1_challenge import detect_brute_force\n\n\ndef test_x():\n    assert detect_brute_force([]) is False\n"
    rewritten, note = normalize_test_module_import(test_code, "booth6")
    assert "from submission import detect_brute_force" in rewritten
    assert "from t1_challenge import" not in rewritten
    assert note == "booth6: rewrote test imports from 't1_challenge' to 'submission'"


def test_normalize_test_module_import_leaves_submission_import_untouched():
    test_code = "from submission import find_profile_issues\n\n\ndef test_x():\n    pass\n"
    rewritten, note = normalize_test_module_import(test_code, "booth3")
    assert rewritten == test_code
    assert note is None


def test_normalize_test_module_import_ignores_stdlib_and_pytest_imports():
    test_code = (
        "import pytest\nfrom collections import Counter\nfrom submission import solve\n\n\n"
        "def test_x():\n    pass\n"
    )
    rewritten, note = normalize_test_module_import(test_code, "booth1")
    assert rewritten == test_code
    assert note is None


def test_normalize_test_module_import_raises_on_ambiguous_multiple_foreign_modules():
    test_code = "from module_a import x\nfrom module_b import y\n"
    try:
        normalize_test_module_import(test_code, "booth5")
        assert False, "expected BoothFileSetError"
    except BoothFileSetError as e:
        assert "more than one non-standard module" in str(e)


# ---------------------------------------------------------------------------
# build_plan / apply_plan -- csv mode
# ---------------------------------------------------------------------------

def _make_mission(booth_id, title="Test Booth"):
    from app.models import Mission

    mission = Mission(
        title=title, type="code", narrative="n", cipher_word="X", booth_id=booth_id, order_index=booth_id,
    )
    return mission


def test_build_plan_csv_mode_happy_path(app, tmp_path):
    from app.extensions import db

    (tmp_path / "booth1_demo.md").write_text("Do the thing.")
    (tmp_path / "booth1_demo.csv").write_text(
        "name,input_data,expected_output,weight,visibility\n"
        "case1,3,6,1,visible\n"
        "case2,5,10,2,hidden\n"
    )

    with app.app_context():
        db.session.add(_make_mission(1))
        db.session.commit()

        plan, errors, notes = build_plan(str(tmp_path))
        assert errors == []
        assert notes == []
        assert len(plan) == 1
        assert plan[0]["mode"] == "csv"
        assert len(plan[0]["test_cases"]) == 2

        booths_updated, total_test_cases = apply_plan(plan)
        assert booths_updated == 1
        assert total_test_cases == 2

        from app.models import Mission
        mission = Mission.query.filter_by(booth_id=1).first()
        assert mission.challenge.prompt == "Do the thing."
        assert len(mission.challenge.test_cases) == 2
        assert mission.challenge.grading_mode == "auto"  # freshly created, never touched to pytest


# ---------------------------------------------------------------------------
# build_plan / apply_plan -- pytest mode
# ---------------------------------------------------------------------------

def test_build_plan_pytest_mode_happy_path_and_rewrites_import(app, tmp_path):
    from app.extensions import db

    (tmp_path / "booth6_tbm_prompt.md").write_text("Detect the brute force attack.")
    (tmp_path / "booth6_tbm_starter.py").write_text("def detect_brute_force(logs):\n    pass\n")
    (tmp_path / "booth6_tbm_test.py").write_text(
        "from t1_challenge import detect_brute_force\n\n\n"
        "def test_empty():\n    assert detect_brute_force([]) is False\n"
    )

    with app.app_context():
        db.session.add(_make_mission(6))
        db.session.commit()

        plan, errors, notes = build_plan(str(tmp_path))
        assert errors == []
        assert len(notes) == 1 and "rewrote test imports" in notes[0]
        assert len(plan) == 1
        item = plan[0]
        assert item["mode"] == "pytest"
        assert "from submission import detect_brute_force" in item["test_code"]

        apply_plan(plan)

        from app.models import Mission
        mission = Mission.query.filter_by(booth_id=6).first()
        assert mission.challenge.grading_mode == "pytest"
        assert mission.challenge.prompt == "Detect the brute force attack."
        assert "def detect_brute_force" in mission.challenge.starter_code
        assert "from submission import" in mission.challenge.test_code
        assert mission.challenge.test_cases == []


def test_build_plan_reports_error_for_missing_mission(app, tmp_path):
    (tmp_path / "booth9_missing.md").write_text("prompt")
    (tmp_path / "booth9_missing.csv").write_text("name,expected_output\nc,1\n")

    with app.app_context():
        plan, errors, notes = build_plan(str(tmp_path))
        assert plan == []
        assert len(errors) == 1
        assert "no existing Mission" in errors[0]


def test_build_plan_reports_error_when_both_csv_and_pytest_files_present(app, tmp_path):
    from app.extensions import db

    (tmp_path / "booth2_both.md").write_text("prompt")
    (tmp_path / "booth2_both.csv").write_text("name,expected_output\nc,1\n")
    (tmp_path / "booth2_both_starter.py").write_text("def f(): pass\n")
    (tmp_path / "booth2_both_test.py").write_text("from submission import f\n")

    with app.app_context():
        db.session.add(_make_mission(2))
        db.session.commit()

        plan, errors, notes = build_plan(str(tmp_path))
        assert plan == []
        assert len(errors) == 1
        assert "found both a .csv file and _starter.py/_test.py files" in errors[0]


def test_build_plan_reports_error_for_incomplete_pytest_pair(app, tmp_path):
    from app.extensions import db

    (tmp_path / "booth4_partial.md").write_text("prompt")
    (tmp_path / "booth4_partial_starter.py").write_text("def f(): pass\n")
    # no _test.py

    with app.app_context():
        db.session.add(_make_mission(4))
        db.session.commit()

        plan, errors, notes = build_plan(str(tmp_path))
        assert plan == []
        assert len(errors) == 1
        assert "missing _test.py" in errors[0]
