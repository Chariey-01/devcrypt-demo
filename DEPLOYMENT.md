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
python3 run.py
```

Use `python3 run.py`, not `flask run`/`flask --app run.py run` — the app uses real Socket.IO push
(see §2's "Surviving a live event" section), which needs `socketio.run()` to hold WebSocket
connections open. `flask run` never executes `run.py`'s `if __name__ == "__main__":` block, so it
would silently fall back to long-polling instead of true push. `run.py` binds to
`0.0.0.0:5000` itself, matching the same LAN-visible address the old `flask run` flags gave.

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

### Real event credentials

The table above is demo-only — every team key is `TEAMNAME01` and every staff password is
`changeme`, hardcoded in `seed.py`. For an actual event,we will generate real random credentials
instead:

```bash
python3 seed.py                       # sets up missions/evidence — wipes everything first
python3 generate_credentials.py \
  --teams "Alpha Squad" "Bravo Squad" "Charlie Squad" \
  --game-masters gm@devcrypt.local \
  --booth-agents agent1@devcrypt.local agent2@devcrypt.local \
  --security-officers officer@devcrypt.local \
  --out credentials.csv
```

This writes cryptographically random team keys (`secrets`-module generated, ambiguous
characters like `0`/`O` and `1`/`I`/`L` excluded so they're safe to read off a printed key
card) and staff passwords to `credentials.csv` — print/distribute it, then delete the file.
Only bcrypt hashes are stored in the database; a lost credential can't be recovered, only
replaced by re-running the script for that team/account. It only touches `Team`/`User` rows —
safe to re-run any time without disturbing missions (unlike `seed.py`, it never wipes data).
`credentials*.csv` is gitignored — never commit it.

## 2. Production (Railway preferred, Render supported — both persistent servers)

This app is a **persistent Flask process** (a gunicorn worker holding open WebSocket
connections for real Socket.IO push, a subprocess-based grading engine that runs for up to
30s per request) — not a request/response function. It needs a
host that keeps a process running continuously, not a serverless/functions platform. Railway
and Render both fit that model directly; **Vercel does not and is not a target for this
backend** (see the note at the end of this section for why, in case that changes later for
just the frontend).

Config already in the repo for both: `Procfile` (the gunicorn entrypoint), `railway.json`
(explicit build/start/health-check config so Railway doesn't have to guess), `render.yaml`
(a Render Blueprint — provisions the web service *and* Postgres together, with `SECRET_KEY`/
`EVENT_SALT` auto-generated, in one deploy), `requirements.txt` (includes `psycopg2-binary` for
Postgres), `.env.example` (documents every required env var).

### Railway (preferred)

1. Push this repo to GitHub.
2. **New Project → Deploy from GitHub repo.**
3. **New → Database → Add PostgreSQL** in the same project — Railway injects `DATABASE_URL`
   into the web service automatically, no copy-pasting a connection string.
4. On the web service, set **Variables**: `SECRET_KEY` and `EVENT_SALT` (generate both with
   `python3 -c "import secrets; print(secrets.token_hex(32))"`). Leave `ALLOWED_ORIGIN` unset
   for now — you don't know the URL yet — and come back and set it to the real
   `https://your-app.up.railway.app` URL once step 6 assigns one (tightens Socket.IO's CORS
   check; see `.env.example` for why it matters).
5. Railway picks up the `Procfile` automatically (`gunicorn -k gevent -w 1 -b 0.0.0.0:$PORT
   --timeout 60 --graceful-timeout 60 "app:create_app()"` — see "Surviving a live event" below
   for why it's a single gevent worker, not multiple sync workers). Confirm the service's
   **Settings → Deploy** shows a persistent (not serverless/cron) service type — this is
   Railway's default for a web service, but worth a glance.
6. Deploy. Railway assigns an HTTPS URL and terminates TLS for you.
7. Once live, set up the database from Railway's **Shell** tab (or locally with `DATABASE_URL`
   pointed at Railway's Postgres via its public connection string) — **two commands, in this
   order, and do this before the event, not during**:
   ```bash
   python3 seed.py                       # missions/evidence content — wipes everything first
   python3 generate_credentials.py \
     --teams "Team One" "Team Two" ... \   # all 30-50 real team names
     --game-masters gm@yourevent.local \
     --booth-agents agent1@yourevent.local agent2@yourevent.local \
     --security-officers officer@yourevent.local \
     --out credentials.csv
   ```
   `seed.py` alone only creates the 2-team demo (`Alpha Squad`/`Bravo Squad`, `changeme`
   passwords) — real credentials for real teams always come from `generate_credentials.py`
   (see "Real event credentials" above for the full explanation). **After this initial setup,
   never run `seed.py` against production again** — it drops and recreates every table,
   destroying live team scores/progress. Any later code push that includes a database
   migration should instead run `python3 deploy_db_setup.py`, which is non-destructive and
   safe to run any number of times (see "Notes" below for why this distinction matters and
   exactly what each script does).
8. **Scaling stays to one instance for this event.** Railway can run multiple replicas of a
   service, but Socket.IO's `emit()` only reaches clients connected to the *same* process
   unless a shared Redis message queue fans it out across replicas — this app has neither
   Redis nor any other cross-process shared state, by design (see "Surviving a live event").
   Don't turn on Railway's horizontal replica scaling for this deployment without adding a
   message queue first, or some connected clients will silently stop receiving live updates
   (they'd still work correctly via the polling fallback, just not instantly).

### Render

Same shape, slightly more manual since Railway auto-wires the database connection:

1. Push this repo to GitHub.
2. In the Render dashboard: **New → PostgreSQL** — create a database, copy its **Internal
   Connection String**.
3. **New → Web Service** → connect the GitHub repo.
   - Build command: `pip install -r requirements.txt`
   - Start command: leave blank to use the `Procfile`, or paste it explicitly:
     `gunicorn -k gevent -w 1 -b 0.0.0.0:$PORT --timeout 60 --graceful-timeout 60 "app:create_app()"`
   - Environment variables: `SECRET_KEY`, `EVENT_SALT` (same generation command as above),
     `DATABASE_URL` (the Postgres connection string from step 2).
   - **Pick a paid, always-on instance type for event day** — Render's free web service tier
     spins down after ~15 minutes idle and cold-starts on the next request (see the
     `/healthz` note under "Surviving a live event"); that cold start is exactly what "sleeps" during a live event.
4. Deploy. Render assigns an HTTPS URL automatically — no separate Nginx/SSL setup needed.
5. Once live, set up the database from Render's **Shell** tab — same two commands, same
   order, same "never run `seed.py` again after this" warning, as Railway step 7 above.
6. Set `ALLOWED_ORIGIN` to the real assigned `https://your-app.onrender.com` URL now that you
   have one.

Alternatively, `render.yaml` in the repo root is a Render **Blueprint** — in the Render
dashboard, **New → Blueprint**, point it at this repo, and it provisions the web service *and*
Postgres together in one pass, with `SECRET_KEY`/`EVENT_SALT` auto-generated for you (skips
steps 1-4 above). You'll still need to run step 5's database setup commands and set
`ALLOWED_ORIGIN` manually afterward — a Blueprint can't know either of those ahead of time.

### Supabase (Postgres only, optional)

Railway and Render both provide their own managed Postgres, so this is only relevant if you
specifically want Postgres decoupled from whichever host runs the app. Create a Supabase
project, grab its connection string (Project Settings → Database), and use that as
`DATABASE_URL` on either host above.

### Why not Vercel for this backend

Vercel runs Python as short-lived serverless functions, which conflicts with this app on two
separate axes, not one:

- **No persistent filesystem or long-lived process.** The old `sqlite:///devcrypt.db` default
  would see different (or empty) databases across invocations — this is why Postgres is
  mandatory everywhere, not Vercel-specific, but it's a harder requirement there since there's
  no way to fall back to a local file even for quick testing.
- **No WebSocket support.** The app uses real Socket.IO push (`app/sockets.py`) over a
  `gevent`-based gunicorn worker, which needs a process that stays alive to hold WebSocket
  connections open. Serverless functions are invoked per-request and torn down; they cannot
  host a WebSocket server — this makes Vercel not just suboptimal but structurally
  incompatible for this backend, not a "someday" concern.

If the frontend is split out later, Vercel is a perfectly reasonable place to host *that*
piece (static/SPA hosting is its actual strength) — it's specifically the Flask backend that
doesn't belong there. `pyproject.toml`'s Vercel entrypoint config has been removed so a
default "deploy this repo" flow on Vercel doesn't silently target the backend.

### Surviving a live event (concurrent booths, all day, no crashes)

- **Gunicorn's request timeout now matches the grading engine's ceiling.** The grading
  service's own hard cap is `MAX_SUITE_SECONDS = 30` (`app/services/grading_service.py`).
  Gunicorn's *default* worker timeout is also 30s — a submission that legitimately takes close
  to the full 30s could get SIGKILLed by gunicorn's watchdog a moment before the grading
  service would have returned its own graceful `suite_timeout` response, turning a clean
  failure into a raw connection reset for the player. The `Procfile` now passes
  `--timeout 60 --graceful-timeout 60` so gunicorn always outlives the app's own timeout.
  If `time_limit_seconds` is ever raised per-challenge above 30s, bump both together.
- **`pool_pre_ping` is on** (`app/config.py`). Managed Postgres free/low tiers (Supabase,
  Render, Railway) silently drop idle connections after a few minutes. Without this, the
  *next* query on a dead connection throws `OperationalError` instead of transparently
  reconnecting — the failure mode that shows up as "worked fine during setup, then randomly
  500s mid-event after a quiet stretch between booth visits."
- **`/healthz` round-trips the database** (not just "is the process alive") and returns
  503 if the DB is unreachable. Point an uptime monitor (UptimeRobot, Better Uptime, cron +
  curl, anything that pings on an interval) at `<your-url>/healthz` every 5–10 minutes on
  event day. This does double duty: it catches a dead DB connection *before* a team hits it,
  and on free/low hosting tiers that spin down after ~15 minutes idle (Render's free web
  service, in particular), the pings keep the app warm so nobody's first request of the day —
  or first request after a lull — eats a 30–50s cold-start. **This is a mitigation, not a
  fix: for a real event, pay for an always-on tier rather than relying on pinging a free one
  not to sleep.**
- **Real-time push runs on a single `gevent` worker, not multiple sync workers.** This is a
  deliberate architecture change, not a downgrade: Socket.IO needs an async-capable worker to
  hold WebSocket connections open at all (sync workers only support Socket.IO's HTTP
  long-polling fallback), and `emit()` only reaches clients on the *same* process unless a
  shared Redis queue fans it out — with a single instance already decided for this event,
  `-k gevent -w 1` sidesteps needing Redis entirely rather than adding new infra to
  provision and misconfigure before the event. One gevent process handles this event's
  concurrency fine because it's never doing CPU work in Python itself — it's either waiting
  on a DB query or waiting on the grading subprocess, both handled correctly (see below).

  Two correctness fixes this requires, both already in place, both worth knowing about if
  something seems to hang:
  1. `gevent.monkey.patch_all()` does not patch `psycopg2`. A blocking libpq call from inside
     the single gevent process would otherwise stall *every* open WebSocket/request for the
     query's duration. Fixed via `psycogreen.gevent.patch_psycopg()`, applied at boot in
     `app/__init__.py`.
  2. The grading engine's `subprocess.run(..., preexec_fn=...)` call forks and calls
     `resource.setrlimit()` in the child. An earlier version of this code routed that call
     through `gevent.get_hub().threadpool.apply(...)` (a real OS thread) out of caution about
     forking inside a monkey-patched greenlet — **this was wrong and broke every auto-graded
     submission** (confirmed live against the real `gunicorn -k gevent` server): gevent's
     monkey-patching replaces `subprocess.run`/`Popen` in place, and the patched version's
     child-watcher setup only works on the hub's own thread, so dispatching it into a worker
     thread crashed with `TypeError: child watchers are only available on the default loop`.
     `app/services/grading_service.py` now calls `subprocess.run()` directly with no thread
     pool — gevent's patched subprocess module is specifically designed to be called
     cooperatively from the hub thread, and `Popen.wait()` already yields to other greenlets
     (other requests, open WebSockets) while the child process runs. Verified live with 10
     concurrent submissions from one team: all completed correctly with the process staying
     responsive throughout.
  3. A pre-existing race in `MissionService.complete_mission()`: its "already resolved" guard
     (`if team_mission.status in ("passed", "overridden"): return None`) is a fast-path check,
     not a lock — under gevent's tighter interleaving, concurrent requests for the same team
     (a double-click, or several near-simultaneous submissions) can all pass that check before
     any of them commits, then collide on `Fragment`'s unique `(team_id, mission_id)`
     constraint and crash with a raw 500. Confirmed live: 10 simultaneous identical passing
     submissions for one team crashed on request #2 onward before this fix. Fixed by wrapping
     the commit (and everything after the `Fragment` insert, since SQLAlchemy's autoflush can
     surface the constraint violation on an earlier query in the same block, not just the
     final `commit()`) in a `try/except IntegrityError` that rolls back and returns `None` —
     the same graceful outcome as the fast-path check, instead of a crash. Re-verified live
     afterward: 10 concurrent identical submissions all return `200 {"correct": true}`, exactly
     one `Fragment` row is created, and the team's score reflects exactly one scoring pass, not
     ten.

  **Trade-off to accept explicitly:** `-w 1` means no failover — a crashed worker is a total
  outage until gunicorn's arbiter (a separate, always-alive process) respawns it, versus a
  multi-worker setup where one stuck worker only costs a fraction of capacity. This is
  mitigated, not eliminated, by the push design itself: every socket event is a bare
  "something changed, go refetch" ping (`app/sockets.py`), never state-carrying, so a brief
  worker restart just means clients fall back to their still-running 2-3s poll loop until
  reconnect — the same guarantee `SYSTEM.md` §6 already promised before sockets existed.

  Worked example for a **30-50 team career fair event** (30-50 team laptops, multiple Booth
  Agents, Security Officers, a Game Master, a projected public leaderboard — connection count
  scales with team count, plus bursts of up to 50 simultaneous submissions in the worst case
  where every team submits at once): `SQLALCHEMY_ENGINE_OPTIONS` in `app/config.py` sizes the
  single process's connection pool to `pool_size=10, max_overflow=10` (20 total) — connections
  are only held briefly, for the `CodeSubmission` insert and the completion commit, not for the
  duration of a grading run. Check 20 against your Postgres provider's connection cap before
  the event; bump `max_overflow` if you provision a plan with more headroom.

  Grading itself calls `subprocess.run()` **directly**, not via a thread pool — gevent's own
  monkey-patched `subprocess` module is already cooperative (it yields to other greenlets, i.e.
  other requests and open WebSockets, while the child process runs), so a real thread was
  unnecessary complexity that in an earlier version of this design actually broke every
  auto-graded submission outright (gevent's child-process watcher only works correctly from the
  hub's own thread — see the comment at the top of `app/services/grading_service.py`). This
  matters for capacity planning: grading concurrency is bounded by real CPU cores available for
  spawning subprocesses, not by a configurable thread-pool size.

  **Empirically load-tested** (`loadtest.py`, committed to the repo — re-run it against
  whatever host you actually provision before the event): 50 teams, each opening a session,
  connecting a WebSocket, polling status, and firing 3 code submissions — all **at the exact
  same instant**, the worst case realistically possible — against the real
  `gunicorn -k gevent -w 1` process on a 4 vCPU box. Result: 50/50 succeeded, zero duplicate
  scoring (the `IntegrityError`-backed race guard in `MissionService.complete_mission()` held
  under real concurrency), zero dropped socket pushes, zero server errors — worst-case latency
  ~14s, comfortably under gunicorn's 60s timeout. In practice, teams arrive at booths staggered
  over the course of the event rather than all submitting in the same second, so this is a
  ceiling test, not the expected common case.

  **Host sizing:** budget for at least **4 vCPUs and ~4-8 GB RAM** at this team count (revised
  up from the 2 vCPU figure this doc previously gave for a 12-team event — grading is CPU-bound
  subprocess work, so more simultaneous teams genuinely needs more cores, not just more RAM).
  Each grading subprocess is capped at 256 MB (`ADDRESS_SPACE_BYTES_LIMIT` in
  `grading_service.py`) but that's a ceiling, not typical usage. **Run `loadtest.py` against
  your actual provisioned host before the event** — the 4 vCPU number above is what was tested,
  not a theoretical guess; if your host has fewer cores, re-test and expect worse worst-case
  latency, not failures (the design degrades to "slower," not "broken," as long as gunicorn's
  own `--timeout` isn't exceeded).
- **Test on the actual devices before the day**, not just a laptop browser: the UI is plain
  HTML/CSS/vanilla JS with no CDN dependency and no bundler (`app/static/*.js`, plain
  `<textarea>` for the code editor, not Monaco/CodeMirror) — this is deliberately the safest
  choice for unknown hardware, since there's nothing to fail to load and nothing that needs a
  specific browser version. Still worth a real pass on an iPad (Safari) and a couple of Android
  tablets/laptops on the actual venue Wi-Fi before the event, since that's the one class of bug
  (touch input quirks, a viewport edge case, a slow/flaky venue network) this repo can't verify
  for you.

### Notes

- `Flask-Migrate`/Alembic is wired up (`app/extensions.py`, `render_as_batch=True` so the
  same scripts apply cleanly to both SQLite and Postgres) and a `migrations/` folder exists
  with the first real migration (the Agent-managed challenge platform schema — see
  `SYSTEM_DESIGN.md` section 13). **`create_app()` no longer calls `db.create_all()`
  automatically** — it used to, on every boot, but that silently raced Flask-Migrate: the
  `flask` CLI has to import `run.py` (which calls `create_app()` at module level) just to
  discover the `app` object before dispatching to `flask db upgrade`, so `create_all()` would
  already have created every table from current `models.py` *before* Alembic's own
  `CREATE TABLE`/`ALTER TABLE` statements ran — confirmed live, this crashed with
  `table hints already exists` (and, once that was patched around, `ALTER TABLE challenges
  ADD COLUMN title` failing with `no such table: challenges`, since the one migration file
  only captures the *incremental* diff from when Flask-Migrate was adopted — it assumes the
  base schema already exists, because it was autogenerated against a database that already
  had it).
  **The fix:** `python3 deploy_db_setup.py`, a new script that's safe to run after *any*
  deploy, first time or the hundredth time — it inspects the target database and does the
  right thing automatically: a genuinely empty database gets `db.create_all()` (the full
  current schema in one shot) followed by `flask_migrate.stamp()` (marks Alembic's history as
  already being at head, so it doesn't try to replay diffs `create_all()` already satisfied);
  a database with tables but no `alembic_version` (an old local DB from before migration
  tracking existed) just gets stamped, no replay; a properly-tracked database gets a normal
  `flask_migrate.upgrade()`, which is what actually applies a *future* migration correctly.
  All three paths were run and verified locally against fresh/legacy/tracked SQLite databases
  — see the script's own docstring for the full reasoning. It isn't part of the *very first*
  deploy's runbook steps above, since `python3 seed.py` already calls `db.create_all()` itself
  (after its own `db.drop_all()`, independent of `create_app()`) and is what actually seeds
  the initial mission/team content — `deploy_db_setup.py` is what you run instead of `seed.py`
  for every deploy *after* that first one, so a mid-event hotfix with a new migration doesn't
  wipe live team scores.
- Real-time surfaces (mission panel, GM dashboard, public leaderboard) use Socket.IO push
  (`app/sockets.py`) as a low-latency trigger layered on top of the original 2-3s poll loops
  (`app/static/app.js`, `mod_admin.js`), which still run unchanged as the fallback — see
  `SYSTEM.md` §6 for the original polling rationale, and "Surviving a live event" above for
  the push architecture. No Redis message queue is required at the single-instance,
  single-worker scale this deploys at; see that section before enabling horizontal scaling.
- Rotate `SECRET_KEY` and `EVENT_SALT` per event; reusing them across events lets an
  organizer from a past event predict current fragment values.
- The sandboxed code-grading engine (`app/services/grading_service.py`) runs submitted
  Python as a subprocess with CPU/memory/process rlimits and a hard timeout — OS-level
  isolation, not container isolation. This is an intentional tradeoff for a supervised
  booth setting (see `SYSTEM_DESIGN.md` section 13); it is not hardened for hosting fully
  adversarial untrusted code at internet scale.
