# DevCrypt — Breach the Metaverse

A hybrid digital-physical Capture-the-Flag platform for career fairs and hackathons. Teams
play Cyber Response Units investigating a live "attack" on the Moringa Metaverse — six
compromised nodes, each an employer booth, each hiding a different real vulnerability
(faulty deploy, leaked token, DNS amplification, broken schema, SQL injection, and a final
locked core). Solving each node reveals a fragment of a live-decoding cryptogram; assembling
all six lets a team capture the final flag and restore the Metaverse Core.

Four roles, one app: **Player** (team), **Booth Agent** (employer rep), **Security Officer**
(checkpoint clearance), **Game Master** (event operator).

## Quickstart

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 seed.py                 # 2 teams, 6 missions, 4 staff accounts
flask --app run.py run --host=0.0.0.0 --port=5000
```

Then open `http://localhost:5000` and either:
- log in as a **team** (`Alpha Squad` / key `ALPHA01`, or `Bravo Squad` / key `BRAVO01`), or
- log in as **staff** (`gm@devcrypt.local`, `agent1@devcrypt.local`, `officer@devcrypt.local`
  — all password `changeme`; change these before any real event).

The Game Master must click **Start event** before player portals accept submissions.

## Docs

- **[SYSTEM.md](SYSTEM.md)** — full architecture: how the four roles connect, the mission
  loop end to end, every schema addition beyond the original design and why, scoring/integrity
  rules, the cipher/fragment engine, and why this build polls instead of using WebSockets.
- **[DEPLOYMENT.md](DEPLOYMENT.md)** — local demo setup (offline-capable, single laptop) and
  a step-by-step production deployment guide (Render/Railway + managed Postgres).

## Stack

Flask (Blueprints) · SQLAlchemy · Flask-Login + Flask-Bcrypt · SQLite (demo) / Postgres
(production) · vanilla JS + CSS (no build step, no CDN dependency — see SYSTEM.md §6 for why).

## Tests

```bash
pytest
```
