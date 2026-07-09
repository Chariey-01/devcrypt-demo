# DevCrypt — Deployment

Two deployment targets: the **local demo** (single laptop, no internet, per NFR-05) and
**production** (cloud, HTTPS, Postgres). This doc covers both. It does not perform any
deployment for you — every command here is meant to be run by whoever owns the target
environment.

## 1. Local demo (career fair / hackathon laptop)

No internet connection required after the one-time `pip install`.

```bash
cd devcrypt
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python3 seed.py                    # wipes and reseeds devcrypt.db with 2 teams + 6 missions
flask --app run.py run --host=0.0.0.0 --port=5000
```

Everyone on the same Wi-Fi/hotspot connects to `http://<laptop-ip>:5000`. Find `<laptop-ip>`
with `ipconfig` (Windows) or `ifconfig`/`ip addr` (Mac/Linux). SQLite (`devcrypt.db`) needs no
separate server and survives restarts — teams can switch devices mid-event without losing
progress.

**Before the event**, log in as Game Master (`gm@devcrypt.local` / `changeme` — change this
password if the laptop will be reachable beyond the venue Wi-Fi) and click **Start event** —
until you do, every player portal shows a "standing by" screen and blocks submissions.

Seeded accounts (see `seed.py`, and change every password before a real event):

| Role | Login | Password |
|---|---|---|
| Team | Alpha Squad / key `ALPHA01` | — |
| Team | Bravo Squad / key `BRAVO01` | — |
| Game Master | `gm@devcrypt.local` | `changeme` |
| Booth Agent | `agent1@devcrypt.local`, `agent2@devcrypt.local` | `changeme` |
| Security Officer | `officer@devcrypt.local` | `changeme` |

## 2. Production (Render / Railway / Vercel + managed Postgres)

Config already in the repo: `Procfile` (gunicorn entrypoint for Render/Railway),
`pyproject.toml` (Vercel entrypoint), `requirements.txt` (includes `psycopg2-binary` for
Postgres), `.env.example` (documents every required env var).

### Render

1. Push this repo to GitHub (see the main branch/PR you're working from).
2. In the Render dashboard: **New → PostgreSQL** — create a database, copy its **Internal
   Connection String**.
3. **New → Web Service** → connect the GitHub repo.
   - Build command: `pip install -r requirements.txt`
   - Start command: `gunicorn -w 4 -b 0.0.0.0:$PORT "app:create_app()"`
   - Environment variables: `SECRET_KEY`, `EVENT_SALT` (generate both with
     `python3 -c "import secrets; print(secrets.token_hex(32))"`), `DATABASE_URL` (the
     Postgres connection string from step 2).
4. Deploy. Render assigns an HTTPS URL automatically — no separate Nginx/SSL setup needed,
   Render terminates TLS for you.
5. Once live, run the seed script once against production (Render's shell tab):
   `python3 seed.py` — **do this before the event, not during**, since it drops and
   recreates all tables.

### Railway

Same shape: **New Project → Deploy from GitHub repo**, add a **Postgres** plugin (Railway
injects `DATABASE_URL` automatically), set `SECRET_KEY` and `EVENT_SALT` as project
variables, and Railway will pick up the `Procfile` automatically.

### Vercel

Vercel runs Flask as a serverless function (`pyproject.toml`'s `[tool.vercel] entrypoint =
"run:app"` points it at the `app` object in `run.py`). **This changes one thing that
matters a lot for a live event: the filesystem is not persistent across invocations.**
The default `sqlite:///devcrypt.db` will not reliably keep team scores/progress between
requests on Vercel — different invocations can see different (or empty) databases. Do not
run a real event on Vercel with SQLite.

1. Provision Postgres somewhere external (Supabase, Neon, or Render/Railway's managed
   Postgres all work) and copy its connection string.
2. In the Vercel project's **Settings → Environment Variables**, set:
   - `DATABASE_URL` — the Postgres connection string from step 1 (not SQLite).
   - `SECRET_KEY` and `EVENT_SALT` — generate both with
     `python3 -c "import secrets; print(secrets.token_hex(32))"`. These must stay **fixed**
     across deploys — Vercel may spin up multiple function instances, and if `SECRET_KEY`
     changes between them, players' session cookies (and therefore logins) break
     unpredictably.
3. Deploy. Vercel picks up `requirements.txt` (already includes `psycopg2-binary`) and the
   `pyproject.toml` entrypoint automatically.
4. Seed once against the same `DATABASE_URL`, from your own machine before the event:
   `DATABASE_URL=<your Postgres URL> python3 seed.py`.
5. For anything beyond what's here (custom routes, build settings), follow Vercel's own
   Python runtime docs — this was written from the error message Vercel gave, not tested
   against a live Vercel deploy.

### Supabase (Postgres only)

If you want a managed Postgres without Render/Railway hosting the app itself, create a
Supabase project, grab its connection string (Project Settings → Database), and use that as
`DATABASE_URL` with any WSGI host (Render/Railway/your own VM running gunicorn).

### Notes

- `Flask-Migrate`/Alembic is already wired up (`app/extensions.py`); once this app has real
  production data, prefer `flask db migrate` / `flask db upgrade` over `db.create_all()` for
  schema changes so existing event data isn't wiped.
- `flask-socketio` is initialized but this MVP's real-time surfaces (cryptogram board,
  leaderboard, dashboards) use short-interval polling instead of WebSockets — see `SYSTEM.md`
  for why. No Redis message queue is required for this deployment.
- Rotate `SECRET_KEY` and `EVENT_SALT` per event; reusing them across events lets an
  organizer from a past event predict current fragment values.
