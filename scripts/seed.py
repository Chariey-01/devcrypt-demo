import os
import sys

# Running as `python3 scripts/seed.py` puts only scripts/ on sys.path (Python adds the script's
# own directory, not the cwd) — add the repo root so `app` resolves regardless of invocation.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models import (
    Challenge,
    EvidenceFile,
    KnowledgeOption,
    KnowledgeQuestion,
    Mission,
    Team,
    TestCase,
    User,
)

# Dev/demo seed data only — this is NOT the source of truth for a real event. Every field here
# (problem statement, starter code, test cases, knowledge check questions, hints, evidence) is
# meant to be authored and edited through the Agent Dashboard instead; this script exists so a
# fresh local database isn't empty, and so the shape of "a fully configured booth" is documented
# somewhere runnable. All six booths are auto-graded (grading_mode="auto") with an 80% pass
# threshold, matching the event's actual grading design — nothing here uses the old manual-review
# queue.
#
# Booths are themed around this event's real employer partners, researched directly (not
# invented) so each scenario reflects what that company actually does:
#   - Elewa           — Kenya-based IT/product agency (elewa.ke), the "Elewa Way" 3-stage
#                        product methodology for startups and SMEs.
#   - Workforce Africa — Pan-African HR/EOR & PEO platform managing employee access and staffing
#                        across 40+ markets.
#   - Unispot          — Kenya-based study-abroad consultancy routing student applications to
#                        partner universities internationally (unispotconsultants.co.ke).
#   - Close the Gap    — Mombasa-based IT Asset Disposition / e-waste circular-economy
#                        organisation; refurbishes devices and securely wipes data before reuse.
#   - Zuberi           — Nairobi-based African game studio (BodaLands, Ganga) building mobile
#                        games rooted in East African culture.
#   - TBM Limited      — Nairobi-based IT/cybersecurity/cloud services firm, a 30+ year IBM
#                        business partner (Trans Business Machines).
MISSIONS = [
    {
        "title": "Elewa — MVP Launch Pipeline",
        "tagline": "Building digital products and engineering talent.",
        "cipher_word": "LAUNCH",
        "booth_id": 1,
        "order_index": 1,
        "time_limit": 600,
        "narrative": (
            "Elewa is walking a startup client through the final stage of the Elewa Way — "
            "shipping their MVP. GhostRoute-7 tampered with the launch checklist service: it "
            "needs to report exactly how many feature flags are actually ready to ship."
        ),
        "evidence": (
            "launch_checklist.log",
            "log",
            "10:02:11 INFO  checklist requested for release rev=8f3a1c\n"
            "10:02:12 WARN  flag aggregator returning stale counts since the GhostRoute-7 patch\n"
            "10:02:14 INFO  awaiting corrected on/off tally before go-live\n",
        ),
        "challenge": {
            "prompt": (
                "You'll receive one line of space-separated feature flag states, each exactly "
                "\"on\" or \"off\". Print how many flags are \"on\" — that's how many features "
                "are actually ready for this MVP launch."
            ),
            "hint_text": "Split the line on whitespace, then count how many entries equal \"on\".",
            "starter_code": "flags = input().split()\n",
            "test_cases": [
                ("visible case", "on off on on", "3", "visible"),
                ("hidden — all off", "off off off", "0", "hidden"),
                ("hidden — single flag", "on", "1", "hidden"),
                ("hidden — all on", "on on on on on", "5", "hidden"),
                ("hidden — alternating", "off on off on off", "2", "hidden"),
            ],
        },
        "knowledge_questions": [
            {
                "question_text": "What does \"MVP\" stand for in product development?",
                "options": [
                    ("Minimum Viable Product", True),
                    ("Most Valuable Programmer", False),
                    ("Maximum Version Push", False),
                    ("Managed Virtual Platform", False),
                ],
            },
            {
                "question_text": "Which of these is a core principle of Agile software development?",
                "options": [
                    ("Delivering working software frequently", True),
                    ("Writing all documentation before any code is written", False),
                    ("Avoiding customer feedback until final launch", False),
                    ("Freezing every requirement at project start", False),
                ],
            },
            {
                "question_text": "In version control, what does a \"merge conflict\" mean?",
                "options": [
                    ("Two branches changed the same code in different ways", True),
                    ("The repository has been permanently corrupted", False),
                    ("A test suite has failed to run", False),
                    ("The build server has gone offline", False),
                ],
            },
        ],
    },
    {
        "title": "Workforce Africa — Access Roster Audit",
        "tagline": "Pan-African HR, EOR and workforce management platform.",
        "cipher_word": "ACCESS",
        "booth_id": 2,
        "order_index": 2,
        "time_limit": 600,
        "narrative": (
            "Workforce Africa manages employee access for client companies across 40+ African "
            "markets. GhostRoute-7 duplicated entries in an access roster — every duplicated "
            "employee ID is a account that could grant someone access twice over."
        ),
        "evidence": (
            "roster_audit.log",
            "log",
            "09:14:02 INFO  roster sync started, source=EOR-platform\n"
            "09:14:05 WARN  duplicate employee ids detected in access grants\n"
            "09:14:07 INFO  awaiting duplicate count before roster can be locked\n",
        ),
        "challenge": {
            "prompt": (
                "You'll receive one line of space-separated employee IDs. Print how many "
                "distinct IDs appear more than once in the roster (count each duplicated ID "
                "once, not the number of extra copies)."
            ),
            "hint_text": "Count occurrences of each ID, then count how many of those counts are greater than 1.",
            "starter_code": "ids = input().split()\n",
            "test_cases": [
                ("visible case", "1 2 2 3 3 3", "2", "visible"),
                ("hidden — one id repeated", "5 5 5 5", "1", "hidden"),
                ("hidden — no duplicates", "1 2 3", "0", "hidden"),
                ("hidden — pair", "9 9", "1", "hidden"),
                ("hidden — three duplicated ids", "4 4 5 5 6 6", "3", "hidden"),
            ],
        },
        "knowledge_questions": [
            {
                "question_text": "What is the primary purpose of Role-Based Access Control (RBAC)?",
                "options": [
                    ("Granting permissions based on a user's assigned role", True),
                    ("Encrypting all outbound network traffic", False),
                    ("Compressing database backups", False),
                    ("Load balancing incoming web requests", False),
                ],
            },
            {
                "question_text": "In cloud computing, what does \"SaaS\" stand for?",
                "options": [
                    ("Software as a Service", True),
                    ("Server as Storage", False),
                    ("Security as a Standard", False),
                    ("System as a Subscription", False),
                ],
            },
            {
                "question_text": "Why is multi-factor authentication (MFA) more secure than a password alone?",
                "options": [
                    ("It requires a second, independent proof of identity", True),
                    ("It automatically makes passwords longer", False),
                    ("It stores passwords in plaintext for faster checks", False),
                    ("It disables login entirely after one attempt", False),
                ],
            },
        ],
    },
    {
        "title": "Unispot — Application Routing Desk",
        "tagline": "Routing student applications to universities abroad.",
        "cipher_word": "ROUTE",
        "booth_id": 3,
        "order_index": 3,
        "time_limit": 600,
        "narrative": (
            "Unispot routes student applications to partner universities abroad. GhostRoute-7 "
            "disrupted the processing-time tracker the advising team uses to set expectations "
            "with applicants — it needs to report the average turnaround, in whole days."
        ),
        "evidence": (
            "routing_desk.log",
            "log",
            "14:02:01 INFO  application batch received, destinations=multiple\n"
            "14:02:02 WARN  processing-time aggregator offline since GhostRoute-7 intrusion\n"
            "14:02:04 INFO  awaiting average turnaround (days) before advisors can respond\n",
        ),
        "challenge": {
            "prompt": (
                "You'll receive one line of space-separated integers — the processing time in "
                "days for each application in a batch. Print the average processing time, "
                "rounded down to the nearest whole day."
            ),
            "hint_text": "Sum the values, then use integer (floor) division by how many values there are.",
            "starter_code": "times = list(map(int, input().split()))\n",
            "test_cases": [
                ("visible case", "10 20 30", "20", "visible"),
                ("hidden — two values", "5 15", "10", "hidden"),
                ("hidden — single value", "7", "7", "hidden"),
                ("hidden — floors down", "1 2 4", "2", "hidden"),
                ("hidden — larger batch", "100 200 300 400", "250", "hidden"),
            ],
        },
        "knowledge_questions": [
            {
                "question_text": "What does DNS primarily do?",
                "options": [
                    ("Translates domain names into IP addresses", True),
                    ("Encrypts email traffic end-to-end", False),
                    ("Compresses image files for the web", False),
                    ("Manages database transactions", False),
                ],
            },
            {
                "question_text": "What is the main difference between HTTP and HTTPS?",
                "options": [
                    ("HTTPS encrypts the connection using TLS/SSL", True),
                    ("HTTP is only used for loading images", False),
                    ("HTTPS is obsolete and no longer used", False),
                    ("HTTP requires a VPN to function", False),
                ],
            },
            {
                "question_text": "What does an API allow two systems to do?",
                "options": [
                    ("Communicate and exchange data via a defined set of rules", True),
                    ("Share the same physical hard drive", False),
                    ("Run on the exact same IP address", False),
                    ("Automatically bypass any firewall", False),
                ],
            },
        ],
    },
    {
        "title": "Close the Gap — Secure Wipe Audit",
        "tagline": "Circular-economy IT refurbishment and secure e-waste disposal.",
        "cipher_word": "WIPED",
        "booth_id": 4,
        "order_index": 4,
        "time_limit": 600,
        "narrative": (
            "Close the Gap refurbishes donated IT equipment at its Circular Economy Hub in "
            "Mombasa — every device must be securely wiped before it's redeployed. GhostRoute-7 "
            "corrupted the wipe-status tracker for an incoming batch of devices."
        ),
        "evidence": (
            "wipe_audit.log",
            "log",
            "11:41:00 INFO  batch received for refurbishment, hub=Mombasa\n"
            "11:41:03 WARN  wipe-status flags unreadable since GhostRoute-7 intrusion\n"
            "11:41:05 INFO  awaiting count of devices still requiring a secure wipe\n",
        ),
        "challenge": {
            "prompt": (
                "You'll receive one line of space-separated flags, one per device: \"1\" means "
                "the device still has data and needs a secure wipe, \"0\" means it's already "
                "wiped. Print how many devices in the batch still need wiping."
            ),
            "hint_text": "Count how many entries in the line equal \"1\".",
            "starter_code": "devices = input().split()\n",
            "test_cases": [
                ("visible case", "0 1 0 1 1", "3", "visible"),
                ("hidden — none remaining", "0 0 0", "0", "hidden"),
                ("hidden — single device", "1", "1", "hidden"),
                ("hidden — all remaining", "1 1 1 1", "4", "hidden"),
                ("hidden — mixed batch", "0 1 1 0 1 0 1", "4", "hidden"),
            ],
        },
        "knowledge_questions": [
            {
                "question_text": "Why is \"data wiping\" different from simply deleting a file?",
                "options": [
                    ("Wiping overwrites the data so it can't be recovered", True),
                    ("Deleting a file physically destroys the hard drive", False),
                    ("Wiping only works on printers", False),
                    ("Deleting a file is always more secure than wiping", False),
                ],
            },
            {
                "question_text": "What term describes reusing and refurbishing electronics to reduce waste?",
                "options": [
                    ("Circular economy", True),
                    ("Linear scaling", False),
                    ("Vertical integration", False),
                    ("Cold storage", False),
                ],
            },
            {
                "question_text": "Which of these is generally considered \"e-waste\"?",
                "options": [
                    ("A decommissioned company laptop", True),
                    ("A software license key", False),
                    ("A cloud storage bucket", False),
                    ("An email account", False),
                ],
            },
        ],
    },
    {
        "title": "Zuberi — BodaLands Leaderboard",
        "tagline": "African game studio building mobile games rooted in local culture.",
        "cipher_word": "RIDERS",
        "booth_id": 5,
        "order_index": 5,
        "time_limit": 600,
        "narrative": (
            "Zuberi builds BodaLands, a mobile game rooted in Nairobi's motorcycle "
            "taxi culture. GhostRoute-7 knocked out the leaderboard service — it needs to "
            "recover the top score from a batch of submitted match results."
        ),
        "evidence": (
            "bodalands_matches.log",
            "log",
            "16:20:11 INFO  match batch submitted, mode=Founding Riders Program\n"
            "16:20:12 WARN  leaderboard aggregator down since GhostRoute-7 intrusion\n"
            "16:20:14 INFO  awaiting top score before rankings can be restored\n",
        ),
        "challenge": {
            "prompt": (
                "You'll receive one line of space-separated integers — scores from a batch of "
                "BodaLands matches. Print the single highest score in the batch."
            ),
            "hint_text": "Read the scores as integers and print the maximum.",
            "starter_code": "scores = list(map(int, input().split()))\n",
            "test_cases": [
                ("visible case", "120 340 210", "340", "visible"),
                ("hidden — tied scores", "5 5 5", "5", "hidden"),
                ("hidden — outlier last", "1 2 3 100", "100", "hidden"),
                ("hidden — single match", "0", "0", "hidden"),
                ("hidden — outlier first", "999 1 2", "999", "hidden"),
            ],
        },
        "knowledge_questions": [
            {
                "question_text": "What is a common risk of not validating user input in a mobile app?",
                "options": [
                    ("Injection or crash vulnerabilities", True),
                    ("The app automatically becomes faster", False),
                    ("The UI redesigns itself", False),
                    ("Battery life improves", False),
                ],
            },
            {
                "question_text": "In game development, what does \"FPS\" commonly refer to?",
                "options": [
                    ("Frames Per Second", True),
                    ("File Processing Server", False),
                    ("Final Product Stage", False),
                    ("Fast Packet Switching", False),
                ],
            },
            {
                "question_text": "Why do mobile games typically use a server to validate leaderboard scores?",
                "options": [
                    ("To prevent players from tampering with scores locally", True),
                    ("To make the app icon smaller", False),
                    ("To disable multiplayer entirely", False),
                    ("To remove the need for an internet connection", False),
                ],
            },
        ],
    },
    {
        "title": "TBM Limited — Grid Core Restoration",
        "tagline": "Cybersecurity, cloud and enterprise IT services, IBM business partner.",
        "cipher_word": "RESTORE",
        "booth_id": 6,
        "order_index": 6,
        "time_limit": 900,
        "narrative": (
            "All five partner nodes are secured. TBM Limited — the event's cybersecurity and "
            "enterprise infrastructure partner — has been brought in for the final restoration. "
            "GhostRoute-7's last foothold is the Grid Core itself: every recovered fragment's "
            "integrity value must be summed before the core will restore."
        ),
        "evidence": (
            "core_status.log",
            "log",
            "CORE STATUS: LOCKED\nFRAGMENTS RECEIVED: 5/5\nPARTNER ON SITE: TBM Limited\nAWAITING: FRAGMENT INTEGRITY SUM\n",
        ),
        "challenge": {
            "prompt": (
                "Read a line of space-separated fragment integrity values (integers) and print "
                "their sum — the core only restores once every fragment's value is accounted for."
            ),
            "hint_text": "Split the line on whitespace, cast each piece to an integer, sum them.",
            "starter_code": "values = list(map(int, input().split()))\n",
            "test_cases": [
                ("visible case", "1 2 3 4 5", "15", "visible"),
                ("hidden case — larger set", "10 20 30 40", "100", "hidden"),
                ("hidden case — single value", "7", "7", "hidden"),
                ("hidden — five fragments", "100 200 300 400 500", "1500", "hidden"),
                ("hidden — mostly zero", "0 0 0 1", "1", "hidden"),
            ],
        },
        "knowledge_questions": [
            {
                "question_text": "What does \"Zero Trust\" security architecture assume?",
                "options": [
                    ("No user or device should be trusted by default, even inside the network", True),
                    ("All internal network traffic is automatically safe", False),
                    ("Passwords are no longer necessary", False),
                    ("Only external users need to be verified", False),
                ],
            },
            {
                "question_text": "What is the main purpose of a SOC (Security Operations Center)?",
                "options": [
                    ("Monitor and respond to security incidents in real time", True),
                    ("Design marketing campaigns", False),
                    ("Manage payroll systems", False),
                    ("Host static websites", False),
                ],
            },
            {
                "question_text": "In AI/ML, what is \"training data\" used for?",
                "options": [
                    ("Teaching a model to recognize patterns", True),
                    ("Storing user passwords securely", False),
                    ("Rendering 3D graphics", False),
                    ("Compiling source code", False),
                ],
            },
        ],
    },
]


def seed_demo():
    app = create_app()
    with app.app_context():
        db.drop_all()
        db.create_all()

        game_master = User(email="gm@devcrypt.local", role="game_master", full_name="Game Master")
        game_master.set_password("changeme")
        db.session.add(game_master)

        for email, name in (
            ("agent1@devcrypt.local", "Booth Agent One"),
            ("agent2@devcrypt.local", "Booth Agent Two"),
        ):
            agent = User(email=email, role="booth_agent", full_name=name)
            agent.set_password("changeme")
            db.session.add(agent)

        officer = User(email="officer@devcrypt.local", role="security_officer", full_name="Security Officer")
        officer.set_password("changeme")
        db.session.add(officer)

        alpha = Team(name="Alpha Squad")
        alpha.set_key("ALPHA01")
        db.session.add(alpha)

        bravo = Team(name="Bravo Squad")
        bravo.set_key("BRAVO01")
        db.session.add(bravo)

        db.session.flush()
        agent_ids = [
            u.id for u in User.query.filter_by(role="booth_agent").order_by(User.email).all()
        ]

        for i, spec in enumerate(MISSIONS):
            mission = Mission(
                title=spec["title"],
                tagline=spec.get("tagline"),
                cipher_word=spec["cipher_word"],
                type="code",
                narrative=spec["narrative"],
                booth_id=spec["booth_id"],
                order_index=spec["order_index"],
                time_limit=spec["time_limit"],
                # Alternate ownership across the two seeded agents so local dev also exercises
                # the ownership-scoped Agent Dashboard with more than one agent's worth of data.
                owner_agent_id=agent_ids[i % len(agent_ids)] if agent_ids else None,
                status="published",
            )
            db.session.add(mission)
            db.session.flush()

            label, file_type, content = spec["evidence"]
            db.session.add(
                EvidenceFile(mission_id=mission.id, label=label, file_type=file_type, content=content)
            )

            challenge = spec["challenge"]
            challenge_row = Challenge(
                mission_id=mission.id,
                type="code",
                prompt=challenge["prompt"],
                hint_text=challenge["hint_text"],
                grading_mode="auto",
                language="python",
                starter_code=challenge["starter_code"],
                pass_threshold=80,
                difficulty="easy" if i < 3 else "medium",
            )
            db.session.add(challenge_row)
            db.session.flush()

            for tc_index, (tc_name, tc_input, tc_expected, tc_visibility) in enumerate(challenge["test_cases"]):
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

            for q_index, q_spec in enumerate(spec.get("knowledge_questions", [])):
                question = KnowledgeQuestion(
                    mission_id=mission.id,
                    question_text=q_spec["question_text"],
                    order_index=q_index,
                )
                db.session.add(question)
                db.session.flush()
                for option_text, is_correct in q_spec["options"]:
                    db.session.add(
                        KnowledgeOption(
                            question_id=question.id,
                            option_text=option_text,
                            is_correct=is_correct,
                        )
                    )

        db.session.commit()

        print("Seeded 2 teams, 6 employer-themed booths, and 4 staff accounts:")
        print("  Team login   — Alpha Squad / ALPHA01, Bravo Squad / BRAVO01")
        print("  Game Master  — gm@devcrypt.local / changeme")
        print("  Booth Agents — agent1@devcrypt.local, agent2@devcrypt.local / changeme")
        print("  Security     — officer@devcrypt.local / changeme")
        print("  Booths       — " + ", ".join(m["title"] for m in MISSIONS))


if __name__ == "__main__":
    seed_demo()
