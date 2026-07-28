"""Import prepared problem statements (Markdown) and test suites (CSV or pytest) into each
booth's Challenge, instead of re-entering them by hand in the Agent Dashboard.

Directory layout expected (default: content/challenges/ under the repo root). Two mutually
exclusive file sets per booth number, depending on which grading style that booth's content
uses:

CSV / stdin-stdout suite (the app's original "auto" grading_mode):
    booth1_elewa.md         <- entire file content becomes Challenge.prompt, verbatim
    booth1_elewa.csv        <- that booth's full test-case suite (replaces the old one)

Pytest / function suite (the newer "pytest" grading_mode -- a typed function tested with real
pytest assertions, e.g. `def find_profile_issues(profile: dict) -> list[str]`):
    booth3_unispot_prompt.md      <- Challenge.prompt
    booth3_unispot_starter.py     <- Challenge.starter_code (shown in Monaco, e.g. the function
                                      stub the player fills in)
    booth3_unispot_test.py        <- Challenge.test_code (hidden pytest test file), and sets
                                      grading_mode = "pytest"

Matching rule: the leading "boothN" in each filename (case-insensitive, N = the booth number)
is matched against Mission.booth_id. Everything after that in the filename is free text for
your own organization -- only the leading boothN token, and (for the pytest set) the
"_starter.py" / "_test.py" suffix, are read.

CSV columns (header row required): name, input_data, expected_output, weight, visibility
    - name, expected_output are required per row; a row missing either is rejected and the
      whole booth's import is skipped (see per-booth error reporting below) rather than
      silently importing a partial suite.
    - weight defaults to 1 if blank; must be an integer.
    - visibility must be "visible" or "hidden" (case-insensitive); blank defaults to "visible".
    - input_data and failure_message are optional; there is no failure_message column in the
      confirmed schema, so it is always left NULL -- edit it later in the Agent Dashboard if
      you want custom per-test failure text.

Pytest test file convention: GradingEngine._run_pytest_suite always writes the player's
submitted code to a sandbox file literally named `submission.py`, so your test file must import
the function under test as `from submission import <name>`. If your test file instead imports
from some other module name (e.g. `from t1_challenge import detect_brute_force`, matching
whatever you happened to name your own local starter file), this script detects that and
rewrites just the import line to `from submission import ...` -- never touching any assertion,
fixture, or test logic -- and prints exactly what it rewrote so it's never a silent change. If
more than one distinct non-stdlib module is imported this way, that's ambiguous and the booth
is reported as an error instead of guessed at.

What this does and does not touch:
    - Only Challenge.prompt, starter_code (pytest sets only), test_code (pytest sets only),
      grading_mode (pytest sets only), and that Challenge's TestCase rows (CSV sets only) are
      replaced.
    - Mission fields (title, narrative, tagline, cipher_word, order_index, time_limit, status)
      are never touched.
    - Other Challenge fields (language, pass_threshold, max_attempts, bonus_points,
      time_limit_seconds, hints, etc.) are never touched -- whatever is already configured on
      that booth stays.
    - Never touches Team/TeamMission/CodeSubmission/Fragment or any other player-progress table.
    - A booth_id with no existing Mission row is reported and skipped, not created -- this
      script only replaces content on booths that already exist (see scripts/seed.py for
      creating new booths).

**Mid-event warning**: replacing a booth's test suite while a team is actively looking at that
booth's prompt/starter code changes what they're solving out from under them, and any
already-passed team keeps its prior score untouched (this never re-grades past submissions)
but a team mid-attempt will now be graded against the new suite on their next submit. Safe
to run freely before an event starts or between booths teams haven't reached yet. Cross-check
scripts/verify_missions.py first if unsure whether a booth is already in use.

Usage:
    python3 scripts/import_challenge_content.py                    # preview only
    python3 scripts/import_challenge_content.py --yes               # apply
    python3 scripts/import_challenge_content.py --dir some/other/path --yes
"""
import argparse
import csv
import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models import Challenge, Mission, TestCase

DEFAULT_CONTENT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "content", "challenges")

BOOTH_FILENAME_RE = re.compile(r"^booth(\d+)", re.IGNORECASE)

REQUIRED_CSV_COLUMNS = {"name", "expected_output"}
KNOWN_CSV_COLUMNS = {"name", "input_data", "expected_output", "weight", "visibility"}

# Modules a test file might legitimately import besides the player's own code -- never
# candidates for the "from X import ..." rewrite below, regardless of how many appear.
STDLIB_TEST_IMPORT_ALLOWLIST = {
    "pytest", "unittest", "collections", "itertools", "functools", "typing", "math", "re",
    "os", "sys", "json", "datetime", "random", "string", "copy", "io", "statistics",
    "dataclasses", "decimal", "enum", "abc",
}
FROM_IMPORT_RE = re.compile(r"^from\s+(\w+)\s+import\b", re.MULTILINE)


class BoothFileSetError(Exception):
    """Raised for a problem specific to one booth's file pair -- caught per-booth so one bad
    file doesn't abort every other booth's import."""


def normalize_test_module_import(test_code, booth_label):
    """Rewrites `from <module> import ...` to `from submission import ...` wherever <module>
    isn't stdlib/pytest, so the test file matches what _run_pytest_suite actually writes the
    player's code to. Returns (possibly-rewritten test_code, rewrite_note_or_None). Raises
    BoothFileSetError if more than one distinct non-stdlib module is imported (ambiguous)."""
    candidates = {
        m for m in FROM_IMPORT_RE.findall(test_code)
        if m not in STDLIB_TEST_IMPORT_ALLOWLIST and m != "submission"
    }
    if not candidates:
        return test_code, None
    if len(candidates) > 1:
        raise BoothFileSetError(
            f"{booth_label}: test file imports from more than one non-standard module "
            f"{sorted(candidates)} -- can't tell which one is the player's code. Edit the test "
            f"file so it imports the function under test from a single module."
        )
    old_module = candidates.pop()
    rewritten = re.sub(rf"^from\s+{re.escape(old_module)}\s+import\b", "from submission import", test_code, flags=re.MULTILINE)
    return rewritten, f"{booth_label}: rewrote test imports from '{old_module}' to 'submission'"


def discover_booth_files(content_dir):
    """Returns {booth_number: {"md": path_or_None, "csv": path_or_None, "starter": path_or_None,
    "test": path_or_None}}."""
    booths = {}
    for path in glob.glob(os.path.join(content_dir, "*")):
        filename = os.path.basename(path)
        stem, ext = os.path.splitext(filename)
        ext = ext.lower()
        if ext not in (".md", ".csv", ".py"):
            continue
        match = BOOTH_FILENAME_RE.match(stem)
        if not match:
            continue
        booth_num = int(match.group(1))
        entry = booths.setdefault(booth_num, {"md": None, "csv": None, "starter": None, "test": None})

        if ext == ".md":
            key = "md"
        elif ext == ".csv":
            key = "csv"
        elif stem.endswith("_starter"):
            key = "starter"
        elif stem.endswith("_test"):
            key = "test"
        else:
            raise BoothFileSetError(
                f"booth{booth_num}: {filename} is a .py file but doesn't end in '_starter.py' "
                f"or '_test.py' -- rename it so its role is unambiguous."
            )

        if entry[key] is not None:
            raise BoothFileSetError(
                f"booth{booth_num}: found more than one {key} file "
                f"({os.path.basename(entry[key])} and {filename}) -- rename so only one matches."
            )
        entry[key] = path
    return booths


def parse_test_cases_csv(path):
    """Returns a list of dicts ready for TestCase(**row), in file order. Raises
    BoothFileSetError with a clear, row-numbered message on any problem."""
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise BoothFileSetError(f"{os.path.basename(path)}: file is empty.")
        header = {h.strip() for h in reader.fieldnames if h}
        missing = REQUIRED_CSV_COLUMNS - header
        if missing:
            raise BoothFileSetError(
                f"{os.path.basename(path)}: missing required column(s) {sorted(missing)}. "
                f"Found columns: {sorted(header)}."
            )
        unknown = header - KNOWN_CSV_COLUMNS
        if unknown:
            raise BoothFileSetError(
                f"{os.path.basename(path)}: unrecognized column(s) {sorted(unknown)} -- "
                f"expected only {sorted(KNOWN_CSV_COLUMNS)}."
            )

        rows = []
        for i, raw in enumerate(reader, start=2):  # header is line 1
            name = (raw.get("name") or "").strip()
            expected_output = raw.get("expected_output")
            if not name or expected_output is None or expected_output == "":
                raise BoothFileSetError(
                    f"{os.path.basename(path)} line {i}: name and expected_output are both required."
                )
            weight_raw = (raw.get("weight") or "").strip()
            try:
                weight = int(weight_raw) if weight_raw else 1
            except ValueError:
                raise BoothFileSetError(
                    f"{os.path.basename(path)} line {i}: weight {weight_raw!r} is not an integer."
                )
            visibility_raw = (raw.get("visibility") or "").strip().lower()
            if visibility_raw not in ("", "visible", "hidden"):
                raise BoothFileSetError(
                    f"{os.path.basename(path)} line {i}: visibility must be 'visible' or "
                    f"'hidden', got {visibility_raw!r}."
                )
            rows.append(
                {
                    "name": name,
                    "input_data": raw.get("input_data") or None,
                    "expected_output": expected_output,
                    "weight": weight,
                    "visibility": "hidden" if visibility_raw == "hidden" else "visible",
                }
            )
        if not rows:
            raise BoothFileSetError(f"{os.path.basename(path)}: no test case rows found.")
        return rows


def build_plan(content_dir):
    """Returns (plan, errors, notes). plan is a list of dicts describing each importable booth;
    errors is a list of human-readable strings for booths that can't be imported; notes is a
    list of non-fatal heads-up messages (e.g. an import-line rewrite) to print either way."""
    booths = discover_booth_files(content_dir)
    plan = []
    errors = []
    notes = []

    for booth_num in sorted(booths):
        entry = booths[booth_num]
        booth_label = f"booth{booth_num}"
        try:
            if entry["md"] is None:
                raise BoothFileSetError(f"{booth_label}: no .md file found.")

            has_csv = entry["csv"] is not None
            has_pytest_pair = entry["starter"] is not None or entry["test"] is not None
            if has_csv and has_pytest_pair:
                raise BoothFileSetError(
                    f"{booth_label}: found both a .csv file and _starter.py/_test.py files -- "
                    f"pick one file set per booth (CSV/stdin-stdout, or pytest/function)."
                )
            if not has_csv and not has_pytest_pair:
                raise BoothFileSetError(
                    f"{booth_label}: no .csv file and no _starter.py/_test.py files found -- "
                    f"nothing to import besides the prompt."
                )
            if has_pytest_pair and (entry["starter"] is None or entry["test"] is None):
                missing = "starter" if entry["starter"] is None else "test"
                raise BoothFileSetError(
                    f"{booth_label}: found only one half of the pytest pair (missing "
                    f"_{missing}.py) -- both _starter.py and _test.py are required together."
                )

            mission = Mission.query.filter_by(booth_id=booth_num).first()
            if mission is None:
                raise BoothFileSetError(
                    f"{booth_label}: no existing Mission with booth_id={booth_num} -- "
                    f"this script only replaces content on booths that already exist."
                )

            with open(entry["md"], encoding="utf-8") as f:
                prompt = f.read().strip()
            if not prompt:
                raise BoothFileSetError(f"{os.path.basename(entry['md'])}: file is empty.")

            if has_csv:
                test_cases = parse_test_cases_csv(entry["csv"])
                plan.append(
                    {
                        "mode": "csv",
                        "booth_num": booth_num,
                        "mission": mission,
                        "md_path": entry["md"],
                        "csv_path": entry["csv"],
                        "prompt": prompt,
                        "test_cases": test_cases,
                    }
                )
            else:
                with open(entry["starter"], encoding="utf-8") as f:
                    starter_code = f.read()
                with open(entry["test"], encoding="utf-8") as f:
                    test_code = f.read()
                if not test_code.strip():
                    raise BoothFileSetError(f"{os.path.basename(entry['test'])}: file is empty.")
                test_code, rewrite_note = normalize_test_module_import(test_code, booth_label)
                if rewrite_note:
                    notes.append(rewrite_note)
                plan.append(
                    {
                        "mode": "pytest",
                        "booth_num": booth_num,
                        "mission": mission,
                        "md_path": entry["md"],
                        "starter_path": entry["starter"],
                        "test_path": entry["test"],
                        "prompt": prompt,
                        "starter_code": starter_code,
                        "test_code": test_code,
                    }
                )
        except BoothFileSetError as e:
            errors.append(str(e))

    return plan, errors, notes


def apply_plan(plan):
    """Actually writes the changes. Returns (booths_updated, test_cases_created)."""
    total_test_cases = 0
    for item in plan:
        mission = item["mission"]
        challenge = mission.challenge
        if challenge is None:
            # Mirrors app/blueprints/agent.py's upsert_challenge fallback: a booth that somehow
            # has no Challenge row yet gets a fresh auto-graded one instead of erroring out.
            # prompt is NOT NULL, so it must be set at construction time, not after -- otherwise
            # the flush() below fails before challenge.prompt = ... ever runs.
            challenge = Challenge(mission_id=mission.id, type="code", grading_mode="auto", prompt=item["prompt"])
            db.session.add(challenge)
            db.session.flush()

        challenge.prompt = item["prompt"]

        if item["mode"] == "csv":
            for old_tc in list(challenge.test_cases):
                db.session.delete(old_tc)
            db.session.flush()

            for order_index, row in enumerate(item["test_cases"]):
                db.session.add(
                    TestCase(
                        challenge_id=challenge.id,
                        name=row["name"],
                        input_data=row["input_data"],
                        expected_output=row["expected_output"],
                        weight=row["weight"],
                        visibility=row["visibility"],
                        order_index=order_index,
                    )
                )
            total_test_cases += len(item["test_cases"])
        else:
            challenge.starter_code = item["starter_code"]
            challenge.test_code = item["test_code"]
            challenge.grading_mode = "pytest"
            # A booth can't be in both modes at once -- clear any leftover CSV-mode TestCase
            # rows from a previous import so they don't linger unused.
            for old_tc in list(challenge.test_cases):
                db.session.delete(old_tc)

    db.session.commit()
    return len(plan), total_test_cases


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--dir", dest="content_dir", default=DEFAULT_CONTENT_DIR,
        help=f"Folder containing boothN_*.md/.csv pairs (default: {DEFAULT_CONTENT_DIR})",
    )
    parser.add_argument("--yes", action="store_true", help="Apply without an interactive confirm prompt.")
    args = parser.parse_args()

    if not os.path.isdir(args.content_dir):
        print(f"Content directory not found: {args.content_dir}")
        print("Create it and add your boothN_*.md / boothN_*.csv files, or pass --dir.")
        sys.exit(1)

    app = create_app()
    with app.app_context():
        plan, errors, notes = build_plan(args.content_dir)

        if notes:
            for n in notes:
                print(f"NOTE: {n}")
            print()

        if errors:
            print(f"{len(errors)} booth(s) could NOT be imported (will be skipped):\n")
            for e in errors:
                print(f"  - {e}")
            print()

        if not plan:
            print("No importable booths found -- nothing to do.")
            sys.exit(1 if errors else 0)

        print(f"{len(plan)} booth(s) will have their challenge content replaced:\n")
        for item in plan:
            mission = item["mission"]
            if item["mode"] == "csv":
                existing_count = len(mission.challenge.test_cases) if mission.challenge else 0
                print(
                    f"  booth_id={item['booth_num']} ({mission.title}) [csv]: "
                    f"prompt <- {os.path.basename(item['md_path'])} ({len(item['prompt'])} chars), "
                    f"test cases {existing_count} existing -> {len(item['test_cases'])} from "
                    f"{os.path.basename(item['csv_path'])}"
                )
            else:
                print(
                    f"  booth_id={item['booth_num']} ({mission.title}) [pytest]: "
                    f"prompt <- {os.path.basename(item['md_path'])} ({len(item['prompt'])} chars), "
                    f"starter_code <- {os.path.basename(item['starter_path'])} "
                    f"({len(item['starter_code'])} chars), "
                    f"test_code <- {os.path.basename(item['test_path'])} "
                    f"({len(item['test_code'])} chars), grading_mode -> pytest"
                )
        print()

        if not args.yes:
            answer = input("Apply these changes? [y/N] ").strip().lower()
            if answer != "y":
                print("Aborted -- no changes made.")
                sys.exit(0)

        booths_updated, total_test_cases = apply_plan(plan)
        print(f"Imported {total_test_cases} test case(s) across {booths_updated} booth(s).")

        if errors:
            sys.exit(1)


if __name__ == "__main__":
    main()
