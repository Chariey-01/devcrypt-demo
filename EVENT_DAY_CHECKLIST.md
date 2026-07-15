# DevCrypt — Event-Day Operations Checklist

A concise, checkbox-driven companion to `DEPLOYMENT.md` (which explains *why*; this is just
*what, in order*). Print it or keep it open on the Game Master's laptop. Times are suggestions —
adjust to your actual event schedule, but keep the relative ordering.

---

## T-minus 1 week (or as soon as the venue/team list is known)

- [ ] Confirm the production host (Railway preferred) is on a **paid, always-on plan** — not a
      free tier that sleeps. See `DEPLOYMENT.md` → "Surviving a live event."
- [ ] Confirm final team count and real team names — you'll need the full list for credential
      generation, and changing it later means re-running that step.
- [ ] Confirm Booth Agent assignments (who owns which mission/booth) and Security Officer /
      Game Master accounts needed.

## T-minus 1-2 days

- [ ] **Generate fresh secrets** — never reuse a previous event's values, since reusing
      `EVENT_SALT` lets someone who ran a past event predict this event's cipher fragments:
      ```bash
      python3 -c "import secrets; print(secrets.token_hex(32))"   # run twice
      ```
      Set the two outputs as `SECRET_KEY` and `EVENT_SALT` in the host's environment variables
      (Railway/Render dashboard — see `DEPLOYMENT.md`).
- [ ] Set `ALLOWED_ORIGIN` to the real deployed URL (e.g. `https://your-app.up.railway.app`),
      not the `*` default.
- [ ] Deploy the current code to production (or confirm it's already deployed).
- [ ] Run database setup (first deploy only — see `DEPLOYMENT.md` if this is a redeploy, use
      `deploy_db_setup.py` instead so you don't wipe live data):
      ```bash
      python3 seed.py
      python3 generate_credentials.py \
        --teams "Team One" "Team Two" ... \
        --game-masters gm@yourevent.local \
        --booth-agents agent1@yourevent.local agent2@yourevent.local \
        --security-officers officer@yourevent.local \
        --out credentials.csv \
        --qr --qr-dir credentials_qr --base-url https://your-app.up.railway.app
      ```
      `--qr` generates one PNG per credential (`credentials_qr/`) — each QR encodes the
      login details as **plain text plus a login link**, not an auto-login token; scanning it
      saves a team from mistyping a random key, it doesn't log them in by itself.
- [ ] Print/prepare team key cards and staff credential sheets from `credentials.csv` /
      `credentials_qr/`. **Delete both from the deploy machine once printed** — they contain
      plaintext secrets and are gitignored for a reason.
- [ ] In the Game Master dashboard, assign each Booth Agent to their mission, and set each
      team's starting booth if you want them staggered rather than all starting at the same
      node (`/mod` → team/agent management — see `DEPLOYMENT.md`'s architecture notes if this
      UI isn't self-explanatory).
- [ ] **Run the load test against the real production host**, not just locally:
      ```bash
      python3 loadtest.py --seed --teams <your real team count>
      python3 loadtest.py --url https://your-app.up.railway.app --teams <your real team count>
      ```
      Confirm it reports `PASS` with zero errors and zero duplicate-scoring before trusting
      the deployment. **Re-run `python3 seed.py` + `generate_credentials.py` afterward** to
      wipe the load-test data and restore real teams — `loadtest.py --seed` adds fake
      `LoadTest Team NNN` rows that must not be present on event day.
- [ ] Take a manual Postgres backup even if the platform has automated ones (belt-and-braces
      before a live event):
      ```bash
      pg_dump "$DATABASE_URL" > backup_pre_event_$(date +%Y%m%d).sql
      ```
      Store it somewhere other than the deploy machine.
- [ ] Confirm the host's own automated-backup setting is on if the plan offers it (Railway and
      Render both gate this behind paid Postgres tiers — check the dashboard).

## Morning of the event (before doors open)

- [ ] `curl https://your-app.up.railway.app/healthz` → expect `{"status": "ok"}`. If it's not,
      stop here and fix it before anything else.
- [ ] Log in as Game Master. Confirm the dashboard loads and shows the correct team list/count.
- [ ] Log in as one real team (pick one at random from the printed key cards) and confirm:
  - [ ] Team login succeeds with the printed key.
  - [ ] The mission/booth panel renders correctly.
  - [ ] The leaderboard page loads and shows the team.
- [ ] Log in as one Booth Agent and confirm their dashboard shows the mission(s) they're
      assigned to, not someone else's.
- [ ] Log in as the Security Officer and confirm the clearance-stamp dashboard loads.
- [ ] **Test Socket.IO end-to-end**, not just that pages load:
  - [ ] Open the team tab and the GM dashboard tab side by side.
  - [ ] From the GM dashboard, click **Start Event**.
  - [ ] Confirm the team tab's banner updates *without a manual refresh* — this is the signal
        real-time push is actually working, not silently falling back to the 2-3s poll (which
        would still work, just wouldn't prove the WebSocket path). If it takes ~2-3s instead of
        being near-instant, sockets aren't connecting — check `ALLOWED_ORIGIN` and browser
        devtools' Network tab for the WebSocket handshake status.
- [ ] Open the projected leaderboard on the actual venue display/projector, on the actual venue
      Wi-Fi, not a laptop hotspot. Confirm it's legible from booth distance.
- [ ] Confirm the event is still in **paused/not-started** state (don't start it during this
      check) — if you clicked Start Event above to test sockets, click **Pause** or **End** and
      restart cleanly right before doors open, so nobody's clock/attempts start early.
- [ ] Spot-check 2-3 more team key cards actually log in (typos happen when printing/reading
      cards) — don't wait for a team to discover a bad card mid-event.

## Just before Start Event

- [ ] All Booth Agents and the Security Officer are logged in and at their stations.
- [ ] Announce/confirm the venue Wi-Fi SSID and password to all teams if it isn't posted.
- [ ] Click **Start Event** from the Game Master dashboard.
- [ ] Immediately re-check `/healthz` and the leaderboard once teams start connecting.

## During the event

- [ ] Keep the Game Master dashboard's live submissions feed open — it's your primary signal
      for anything going wrong (a team stuck, a grading error, an unusual pattern).
- [ ] If you set up an uptime monitor pinging `/healthz` (see `DEPLOYMENT.md`), keep its alert
      channel visible.
- [ ] If something looks broken for one team but not others, check that team's own tab/browser
      first (refresh, re-login) before assuming it's server-side — the polling fallback means a
      real server outage affects *everyone* at once, not one team.
- [ ] Use **Broadcast** (Game Master dashboard) for any event-wide announcements — it pushes to
      every connected client instantly, don't rely on shouting across the venue.

## Recovery playbook (keep this section handy, don't wait until you need it)

- **App looks down / `/healthz` failing:** Check the host's dashboard for a crashed process —
  gunicorn's arbiter auto-respawns a crashed worker, and the platform auto-restarts a crashed
  container, but both take a few seconds. Give it 30s, recheck `/healthz`, then check the
  platform's logs if it's still down.
- **One team stuck / can't submit:** Have them refresh the page first — the 2-3s poll loop
  means a stale UI resolves itself on reload even if a socket dropped. If a submission
  genuinely seems to hang past ~30-60s, that's the grading timeout ceiling — it will resolve
  itself with a graceful error, not require a restart.
- **Need to fix a bug mid-event:** Deploy the fix, then run `python3 deploy_db_setup.py` if it
  includes a migration — **never `python3 seed.py`**, which wipes every team's live progress.
- **Suspected data problem (wrong score, duplicate fragment):** Use the Game Master's score
  override rather than editing the database directly — it's audit-logged.
- **Total data-loss scenario:** Restore from the pre-event `pg_dump` backup or the platform's
  automated backup. This is a last resort, not a first response — confirm the problem is
  actually unrecoverable before restoring, since a restore rolls back every team's progress to
  the backup's timestamp.

## After the event

- [ ] Click **End Event** (or Pause, if you want to review results before formally ending).
- [ ] Export final results (Game Master dashboard's CSV export, if used).
- [ ] Take a final `pg_dump` backup of the completed event's data before any cleanup.
- [ ] Delete `credentials.csv` / `credentials_qr/` from the deploy machine if not already done.
- [ ] Consider whether to scale the host back down (or pause billing) now that the event's over.
