# DevCrypt — Breach the Grid

A hybrid digital-physical Capture-the-Flag platform for career fairs and hackathons. Teams
play Cyber Response Units investigating a live "attack" on the Grid — six real employer
booths (Elewa, Workforce Africa, Unispot, Close the Gap, Zuberi, TBM Limited), each posing a
themed coding challenge with a Monaco-editor-based auto-grading pipeline. Each booth opens
with a general technology Knowledge Check (unrelated to the coding problem — Software
Engineering, Cybersecurity, AI/ML, Data Science, DevOps), then a real coding challenge:
Run Visible Tests as many times as you like, then Submit for automatic grading against a
hidden suite. Passing a booth reveals a fragment of a live-decoding cryptogram; assembling
all six and getting Game Master confirmation reconstructs the final flag.

Four roles, one app: **Player** (team), **Booth Agent** (employer rep — authors and publishes
their own booth's content, nothing is hardcoded), **Security Officer** (checkpoint clearance,
audit-only), **Game Master** (event operator).

## Quickstart

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 scripts/seed.py         # 2 teams, 6 sponsor-themed missions, 4 staff accounts (dev/demo only —
                                 # NEVER run this against a database with real event data, it drops every table)
python3 run.py                  # not `flask run` — skips the Socket.IO entrypoint
```

Then open `http://localhost:5000` and either:
- log in as a **team** (`Alpha Squad` / key `ALPHA01`, or `Bravo Squad` / key `BRAVO01`), or
- log in as **staff** (`gm@devcrypt.local`, `agent1@devcrypt.local`, `officer@devcrypt.local`
  — all password `changeme`; change these before any real event).

The Game Master must click **Start event** before player portals accept submissions.

## Docs

- **[docs/SYSTEM.md](docs/SYSTEM.md)** — start here. Current, verified architecture: how the
  four roles connect, the mission loop end to end (Knowledge Check → Monaco editor → Run
  Visible Tests → Submit → automatic grading → fragment → Game-Master-confirmed final flag),
  the Agent Dashboard content-management platform, scoring/integrity rules, real-time sync,
  known limitations.
- **[docs/API.md](docs/API.md)** — full, current route-by-route reference.
- **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)** — local demo setup (offline-capable, single
  laptop) and a step-by-step production deployment guide (Railway + managed Postgres).
- **[docs/EVENT_DAY_CHECKLIST.md](docs/EVENT_DAY_CHECKLIST.md)** — checkbox-driven event-day
  operations.
- `docs/SYSTEM_DESIGN.md` and `docs/PROJECT_EXPLANATION_PART*.md` are **historical** — they
  describe an earlier version of this app (MCQs instead of a Knowledge Check, manual-review-
  only code challenges, a `/booth/*` portal that no longer exists). Kept for design-reasoning
  history, not for current facts — see `docs/SYSTEM.md` instead.

## Stack

Flask (Blueprints) · SQLAlchemy · Flask-SocketIO (gevent) · Flask-Login + Flask-Bcrypt ·
SQLite (demo) / Postgres (production) · vanilla JS + CSS (no build step, no CDN dependency).

## Tests

```bash
pytest
```
