import os
import sys

# Running as `python3 scripts/seed.py` puts only scripts/ on sys.path (Python adds the script's
# own directory, not the cwd) — add the repo root so `app` resolves regardless of invocation.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models import Challenge, EvidenceFile, MCQ, MCQOption, Mission, Team, TestCase, User

MISSIONS = [
    {
        "title": "Discovery Node — DEPLOY",
        "cipher_word": "DEPLOY",
        "type": "code",
        "booth_id": 1,
        "order_index": 1,
        "time_limit": 600,
        "narrative": (
            "GhostRoute-7 has compromised the discovery node. A faulty deployment "
            "left an authentication bypass live in production."
        ),
        "evidence": (
            "deploy.log",
            "log",
            "10:02:11 INFO  deploy started rev=8f3a1c\n"
            "10:02:14 WARN  skipping auth_middleware.py (feature flag disabled)\n"
            "10:02:15 INFO  deploy complete\n",
        ),
        "mcqs": [
            (
                "What caused the authentication bypass?",
                [
                    ("A feature flag disabled the auth middleware during deploy", True),
                    ("The database password expired", False),
                    ("The load balancer misrouted traffic", False),
                    ("A developer force-pushed to main", False),
                ],
            ),
            (
                "Which log line is the root cause?",
                [
                    ("deploy started rev=8f3a1c", False),
                    ("skipping auth_middleware.py (feature flag disabled)", True),
                    ("deploy complete", False),
                    ("None of the above", False),
                ],
            ),
            (
                "What is the correct immediate mitigation?",
                [
                    ("Roll back the deploy and re-enable the flag", True),
                    ("Restart the database", False),
                    ("Ignore it — deploy succeeded", False),
                    ("Rotate all team keys", False),
                ],
            ),
        ],
        "challenge": {
            "type": "code",
            "prompt": "Write the config change that re-enables auth_middleware.py.",
            "steps": "Review deploy.log, identify the disabled middleware, describe the fix.",
            "answer_key": "auth_middleware_enabled",
            "hint_text": "Look for what the deploy skipped, not what it completed.",
        },
    },
    {
        "title": "Identity Node — TOKENS",
        "cipher_word": "TOKENS",
        "type": "code",
        "booth_id": 2,
        "order_index": 2,
        "time_limit": 600,
        "narrative": (
            "GhostRoute-7 exfiltrated a long-lived API token from the auth service. "
            "The token grants full admin scope and never expires."
        ),
        "evidence": (
            "token_audit.log",
            "log",
            "09:14:02 INFO  token issued sub=svc-admin scope=* exp=none\n"
            "09:14:05 WARN  token used from unrecognized IP 203.0.113.44\n"
            "09:14:07 INFO  token used to call /admin/users/delete\n",
        ),
        "mcqs": [
            (
                "Why is this token dangerous?",
                [
                    ("It has unlimited scope and never expires", True),
                    ("It's too short", False),
                    ("It was issued twice", False),
                    ("It uses the wrong protocol", False),
                ],
            ),
            (
                "Which log line shows the compromise being actively used?",
                [
                    ("token issued sub=svc-admin scope=* exp=none", False),
                    ("token used from unrecognized IP 203.0.113.44", False),
                    ("token used to call /admin/users/delete", True),
                    ("None of the above", False),
                ],
            ),
            (
                "What's the correct remediation?",
                [
                    ("Revoke the token and reissue scoped, short-lived tokens", True),
                    ("Restart the server", False),
                    ("Ignore it, nothing was deleted yet", False),
                    ("Rotate the database password", False),
                ],
            ),
        ],
        "challenge": {
            "type": "code",
            "prompt": "Describe the token policy fix: scope and expiry that should have been enforced.",
            "steps": "Reference the audit log; identify the two missing constraints.",
            "answer_key": "scoped_short_lived_token",
            "hint_text": "The dangerous token was missing two constraints — scope and expiry.",
        },
    },
    {
        "title": "Network Node — PACKET",
        "cipher_word": "PACKET",
        "type": "mcq",
        "booth_id": 3,
        "order_index": 3,
        "time_limit": 600,
        "narrative": (
            "A malformed packet flood is saturating the node's network stack. The traffic "
            "pattern matches a known amplification vector."
        ),
        "evidence": (
            "packet_trace.txt",
            "network",
            "14:02:01 UDP 198.51.100.7:53 -> 10.0.0.5:53 len=4096\n"
            "14:02:01 UDP 198.51.100.7:53 -> 10.0.0.5:53 len=4096\n"
            "14:02:02 UDP 198.51.100.7:53 -> 10.0.0.5:53 len=4096\n",
        ),
        "mcqs": [
            (
                "What type of attack does this traffic represent?",
                [
                    ("DNS amplification / reflection", True),
                    ("SQL injection", False),
                    ("Phishing", False),
                    ("Directory traversal", False),
                ],
            ),
            (
                "What is suspicious about the packet length?",
                [
                    ("4096 bytes is abnormally large for a DNS response", True),
                    ("It's too small to be real traffic", False),
                    ("The length field is missing", False),
                    ("Nothing — this is normal", False),
                ],
            ),
            (
                "What's the correct first response?",
                [
                    ("Rate-limit and filter traffic from the source at the firewall", True),
                    ("Disable the firewall entirely", False),
                    ("Restart the DNS server with no filtering", False),
                    ("Do nothing — it will pass", False),
                ],
            ),
        ],
        "challenge": {
            "type": "mcq",
            "prompt": "Select the correct mitigation for this DNS amplification pattern.",
            "steps": (
                "Rate-limit and filter UDP/53 traffic from the offending source\n"
                "Disable the firewall to let traffic pass through\n"
                "Restart the DNS server without any filtering\n"
                "Ignore it — the node will recover on its own"
            ),
            "answer_key": "Rate-limit and filter UDP/53 traffic from the offending source",
            "hint_text": "Look at where the packets are coming from, not just how many there are.",
        },
    },
    {
        "title": "Data Node — SCHEMA",
        "cipher_word": "SCHEMA",
        "type": "code",
        "booth_id": 4,
        "order_index": 4,
        "time_limit": 600,
        "narrative": (
            "The users table has been silently altered — a migration ran without a rollback "
            "plan, and duplicate primary keys are now corrupting lookups."
        ),
        "evidence": (
            "schema_diff.log",
            "sql",
            "ALTER TABLE users DROP CONSTRAINT users_pkey;\n"
            "-- migration_004 applied without a unique constraint restored\n"
            "SELECT COUNT(*) FROM users; -- returns duplicate id values\n",
        ),
        "mcqs": [
            (
                "What did the migration remove?",
                [
                    ("The primary key constraint on users.id", True),
                    ("The users table entirely", False),
                    ("A foreign key on orders", False),
                    ("Nothing — this is a normal migration", False),
                ],
            ),
            (
                "What symptom does this cause?",
                [
                    ("Duplicate id values corrupting lookups", True),
                    ("Slower query performance only", False),
                    ("The table becomes read-only", False),
                    ("No visible symptom", False),
                ],
            ),
            (
                "What's the correct fix?",
                [
                    ("Restore the primary key constraint after de-duplicating rows", True),
                    ("Drop the users table and start over", False),
                    ("Add an index without removing duplicates", False),
                    ("Ignore it — duplicates are harmless", False),
                ],
            ),
        ],
        "challenge": {
            "type": "code",
            "prompt": "Write the fix that restores integrity to the users table.",
            "steps": "De-duplicate rows first, then re-add the primary key constraint.",
            "answer_key": "restore_primary_key",
            "hint_text": "Two steps are required, and the order matters: de-duplicate, then re-add the constraint.",
        },
    },
    {
        "title": "Application Node — INJECT",
        "cipher_word": "INJECT",
        "type": "mcq",
        "booth_id": 5,
        "order_index": 5,
        "time_limit": 600,
        "narrative": (
            "A login form is passing raw user input directly into a SQL query. Someone just "
            "walked in through the front door."
        ),
        "evidence": (
            "app_query.log",
            "log",
            "SELECT * FROM users WHERE username = '' OR '1'='1' -- ' AND password = '';\n",
        ),
        "mcqs": [
            (
                "What vulnerability is this?",
                [
                    ("SQL injection", True),
                    ("Cross-site scripting", False),
                    ("Buffer overflow", False),
                    ("Cross-site request forgery", False),
                ],
            ),
            (
                "What does '1'='1' accomplish here?",
                [
                    ("Makes the WHERE clause always true, bypassing authentication", True),
                    ("Encrypts the password field", False),
                    ("Deletes the users table", False),
                    ("Nothing — it's a typo", False),
                ],
            ),
            (
                "What's the correct fix?",
                [
                    ("Use parameterized queries / prepared statements", True),
                    ("Concatenate strings more carefully", False),
                    ("Hide the login form", False),
                    ("Block the user's IP address permanently", False),
                ],
            ),
        ],
        "challenge": {
            "type": "mcq",
            "prompt": "Select the correct remediation for this SQL injection.",
            "steps": (
                "Use parameterized queries / prepared statements\n"
                "Concatenate strings more carefully\n"
                "Hide the login form\n"
                "Block the user's IP address permanently"
            ),
            "answer_key": "Use parameterized queries / prepared statements",
            "hint_text": "The fix is about how the query is built, not about blocking the attacker afterward.",
        },
    },
    {
        "title": "Grid Core — RESTORE",
        "cipher_word": "RESTORE",
        "type": "code",
        "booth_id": 6,
        "order_index": 6,
        "time_limit": 900,
        "narrative": (
            "All five nodes are secured. GhostRoute-7's final foothold is the Grid Core "
            "itself. Two security clearance stamps are required to attempt restoration."
        ),
        "evidence": (
            "core_status.log",
            "log",
            "CORE STATUS: LOCKED\nFRAGMENTS RECEIVED: 5/5\nAWAITING: SECURITY CLEARANCE x2\nAWAITING: MASTER FLAG\n",
        ),
        "mcqs": [
            (
                "How many clearance stamps are required to attempt restoration?",
                [
                    ("Two", True),
                    ("None", False),
                    ("One", False),
                    ("Four", False),
                ],
            ),
            (
                "How many fragments have been recovered at this point?",
                [
                    ("Five", True),
                    ("Zero", False),
                    ("Three", False),
                    ("Six", False),
                ],
            ),
            (
                "What is required alongside clearance to restore the core?",
                [
                    ("The master flag", True),
                    ("A new deploy", False),
                    ("A password reset", False),
                    ("Nothing else", False),
                ],
            ),
        ],
        "challenge": {
            "type": "code",
            "prompt": (
                "Read a line of space-separated fragment integrity values (integers) and print "
                "their sum — the core only restores once every fragment's value is accounted for."
            ),
            "steps": None,
            "answer_key": None,
            "hint_text": "Split the line on whitespace, cast each piece to an integer, sum them.",
            "grading_mode": "auto",
            "starter_code": "values = list(map(int, input().split()))\n",
            "pass_threshold": 100,
            "test_cases": [
                # (name, input_data, expected_output, visibility)
                ("visible case", "1 2 3 4 5", "15", "visible"),
                ("hidden case — larger set", "10 20 30 40", "100", "hidden"),
                ("hidden case — single value", "7", "7", "hidden"),
            ],
        },
    },
]


def seed_demo():
    app = create_app()
    with app.app_context():
        db.drop_all()
        db.create_all()

        game_master = User(email="gm@devcrypt.local", role="game_master")
        game_master.set_password("changeme")
        db.session.add(game_master)

        for email in ("agent1@devcrypt.local", "agent2@devcrypt.local"):
            agent = User(email=email, role="booth_agent")
            agent.set_password("changeme")
            db.session.add(agent)

        officer = User(email="officer@devcrypt.local", role="security_officer")
        officer.set_password("changeme")
        db.session.add(officer)

        alpha = Team(name="Alpha Squad")
        alpha.set_key("ALPHA01")
        db.session.add(alpha)

        bravo = Team(name="Bravo Squad")
        bravo.set_key("BRAVO01")
        db.session.add(bravo)

        for spec in MISSIONS:
            mission = Mission(
                title=spec["title"],
                cipher_word=spec["cipher_word"],
                type=spec["type"],
                narrative=spec["narrative"],
                booth_id=spec["booth_id"],
                order_index=spec["order_index"],
                time_limit=spec["time_limit"],
            )
            db.session.add(mission)
            db.session.flush()

            label, file_type, content = spec["evidence"]
            db.session.add(
                EvidenceFile(mission_id=mission.id, label=label, file_type=file_type, content=content)
            )

            for order_index, (question_text, options) in enumerate(spec["mcqs"]):
                mcq = MCQ(mission_id=mission.id, question_text=question_text, order_index=order_index)
                db.session.add(mcq)
                db.session.flush()
                for option_text, is_correct in options:
                    db.session.add(
                        MCQOption(
                            mcq_id=mcq.id,
                            option_text=option_text,
                            is_correct=is_correct,
                            cipher_letter_index=order_index if is_correct else None,
                        )
                    )

            challenge = spec["challenge"]
            challenge_row = Challenge(
                mission_id=mission.id,
                type=challenge["type"],
                prompt=challenge["prompt"],
                steps=challenge["steps"],
                answer_key=challenge["answer_key"],
                hint_text=challenge["hint_text"],
                grading_mode=challenge.get("grading_mode", "manual_review"),
                starter_code=challenge.get("starter_code"),
                function_signature=challenge.get("function_signature"),
                pass_threshold=challenge.get("pass_threshold", 100),
            )
            db.session.add(challenge_row)
            db.session.flush()

            for tc_index, (tc_name, tc_input, tc_expected, tc_visibility) in enumerate(challenge.get("test_cases", [])):
                db.session.add(
                    TestCase(
                        challenge_id=challenge_row.id,
                        name=tc_name,
                        input_data=tc_input,
                        expected_output=tc_expected,
                        weight=1,
                        visibility=tc_visibility,
                        order_index=tc_index,
                    )
                )

        db.session.commit()

        print("Seeded 2 teams, 6 missions, and 4 staff accounts:")
        print("  Team login   — Alpha Squad / ALPHA01, Bravo Squad / BRAVO01")
        print("  Game Master  — gm@devcrypt.local / changeme")
        print("  Booth Agents — agent1@devcrypt.local, agent2@devcrypt.local / changeme")
        print("  Security     — officer@devcrypt.local / changeme")


if __name__ == "__main__":
    seed_demo()
