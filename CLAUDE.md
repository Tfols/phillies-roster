# CLAUDE.md — Phillies Roster App

Philadelphia Phillies All-Time Autograph Tracker. Flask + PostgreSQL app, deployed to Railway.

## Vault

Vault location: C:\Users\tomfo\vault

At the start of this session:
- Read `projects/phillies/status.md`
- Read `projects/phillies/decisions.md`
- Read `architecture/patterns.md`

At the end of this session, if anything changed:
- Update `projects/phillies/status.md`
- Log new decisions to `projects/phillies/decisions.md`
- Add one line to `log/2026/sessions.md`:
  `[Date] | Phillies Roster Tracker | [What changed]`

---
## Context Management

Context is a limited resource. Use subagents (Task tool) to keep
exploration and research out of the main conversation.

**Spawn a subagent for:**
- Reading 3+ files to answer a question about existing code
- Investigating how a current feature is implemented before
  building on it
- Any task where only the summary matters, not the raw file contents

**Stay in main context for:**
- Direct file edits
- Reading 1-2 specific files I've pointed you to
- Tasks where I need to see intermediate steps

**Rule of thumb:** If a task will read more than 3 files or produce
output I don't need to see verbatim, delegate it to a subagent
and return a summary.
```

---
## Live App
- **URL**: https://phillies.tashefamily.com
- **Password**: `TashePhillies` (set via Railway env var `APP_PASSWORD`)
- **GitHub**: https://github.com/Tfols/phillies-roster (branch: `master`)
- **Hosting**: Railway (free tier)
- **DNS**: Cloudflare CNAME → Railway (domain: tashefamily.com)

---

## Tech Stack
- **Backend**: Flask + SQLAlchemy + Gunicorn
- **Database**: PostgreSQL (Railway-managed)
- **Frontend**: Vanilla JS, no build step — all in `static/js/app.js`
- **Installability**: Web app manifest at `static/manifest.json` (no coded service worker)
- **Deployment**: `git push origin master` → Railway auto-deploys via Nixpacks

---

## CRITICAL: Two Database URLs
Railway exposes **two URLs** for the same Postgres service — they are NOT the same database instance:

| Use | URL |
|-----|-----|
| Web app (automatic) | `postgres.railway.internal:5432` — set as `DATABASE_URL` by Railway |
| Local scripts | `postgresql://postgres:tjlGaMTHVDeJJjkyIZPJjfLPneaynSHQ@centerbeam.proxy.rlwy.net:18837/railway` |

**Always use the public URL for any local Python scripts:**
```powershell
$env:DATABASE_URL="postgresql://postgres:tjlGaMTHVDeJJjkyIZPJjfLPneaynSHQ@centerbeam.proxy.rlwy.net:18837/railway"
```

Do NOT use `maglev.proxy.rlwy.net:44703` — that is a stale/old instance.

---

## Environment Variables (Railway)
| Variable | Value |
|---|---|
| `APP_PASSWORD` | TashePhillies |
| `SECRET_KEY` | (random 32-char hex, set in Railway dashboard) |
| `DATABASE_URL` | Auto-set by Railway to internal postgres URL |

---

## Project Structure
```
├── app.py                   # Flask app: auth, API routes
├── models.py                # Player, Affiliate, MinorPlayer models + VALID_STATUSES
├── import_data.py           # One-time MLB player import (MLB Stats API, 1883–2025)
├── import_minors.py         # Minor league import orchestrator (--reset, --dedup-only)
├── import_affiliates.py     # Wikipedia scraper for affiliate history
├── backfill_dob.py          # Backfills birth_date for MLB players (run once, done)
├── fix_schema.py            # Schema migration helper
├── generate_icons.py        # Generates PWA icons (Pillow)
├── Procfile                 # web: gunicorn (no release phase)
├── railway.toml             # Nixpacks builder config
├── EXPORT-PATTERN-WRITEUP.md # jsPDF + LZ-string export pattern from minis app
├── importers/
│   ├── mlbstats_minor.py    # MLB Stats API minor league importer
│   └── baseball_cube_stub.py
├── static/
│   ├── manifest.json
│   ├── icons/
│   ├── css/style.css
│   └── js/app.js            # All frontend logic
└── templates/
    ├── base.html
    ├── login.html
    └── roster.html          # Tab nav (MLB | Minor League) + both panels
```

---

## Database Schema

### `players` (2,209 rows — MLB)
`id`, `player_id` (Lahman), `full_name`, `position`, `year_start`, `year_end`, `years_active`, `mlb_id`, `birth_date`, `photo_url`, `collection_status`, `created_at`, `updated_at`

### `affiliates` (139 rows)
`id`, `mlb_team_id`, `team_name`, `level`, `league`, `location`, `year_start`, `year_end`

### `minor_players` (2,362 rows; 2,012 shown — 350 hidden as MLB duplicates)
`id`, `mlb_id`, `full_name`, `position`, `birth_date`, `year_start`, `year_end`, `affiliate_id` (FK), `affiliate_name`, `level`, `photo_url`, `collection_status`, `data_source`, `is_mlb_duplicate`, `created_at`, `updated_at`

---

## API Routes
| Method | Route | Description |
|--------|-------|-------------|
| GET | `/api/players` | All MLB players |
| PATCH | `/api/players/<id>/status` | Update MLB player status |
| GET | `/api/minors` | Minor players where `is_mlb_duplicate=False` |
| PATCH | `/api/minors/<id>/status` | Update minor player status |

---

## Collection Statuses
Defined in `models.py` as `VALID_STATUSES`:
`Have` | `Have Signed` | `Don't Have` | `No Auto Available` | `In Person`

---

## Frontend Architecture (`app.js`)
- All data loaded once at startup into `allPlayers` / `allMinors` arrays
- Client-side filtering and sorting — no re-fetch on filter change
- Minor League tab lazy-loads on first click
- `getFiltered()` / `getMinorFiltered()` apply all active filters
- `onStatusChange()` uses optimistic UI: updates in-memory + DB, and restores the select value, local model, stats, and rendered row state on failure
- Status change handling uses event delegation on the table bodies instead of rebinding listeners on every render
- Player names are links to `https://www.mlb.com/player/{slug}-{mlb_id}` (opens in new tab)
  - Players without `mlb_id` render as plain text
- `null` `year_end` means the player is still active — year filter uses `?? 9999` to handle this
- Static asset URLs are versioned from file mtimes via `asset_url()` in `app.py`
- JS/CSS/manifest responses are sent with `no-cache, no-store, must-revalidate`

---

## Self-Healing Schema Migration
`_init_db()` in `app.py` runs before the first request and:
1. Calls `db.create_all()` to create any missing tables
2. Checks for the `birth_date` column on `players` and adds it if absent

This exists because Railway's internal DB and the public proxy URL were found to be different instances — the internal DB was missing columns added to the public DB.

---

## Data Import Notes
- **MLB players**: MLB Stats API, year-by-year 1883–2025, 2,209 players
- **Birth dates**: backfilled via MLB Stats API (2,203/2,209 have DOB)
- **Minor players**: MLB Stats API 2005–2025, filtered in Python by `parentOrgId == 143` (Phillies)
  - The `parentOrgIds` query param is silently ignored by the API — the filter must be client-side in the importer
- **Dedup logic**: match by `mlb_id` first, then `(full_name, birth_date)` — 350 players appear in both tables, hidden in minor tab via `is_mlb_duplicate=True`

### Re-running Minor League Import
```powershell
$env:DATABASE_URL="postgresql://postgres:tjlGaMTHVDeJJjkyIZPJjfLPneaynSHQ@centerbeam.proxy.rlwy.net:18837/railway"
python import_minors.py --reset   # wipes minor_players and re-imports cleanly
```

---

## Deployment
```bash
git push origin master   # Railway auto-deploys on push to master
```
No build step. Railway detects Python via Nixpacks, installs `requirements.txt`, runs `gunicorn app:app`.

Static assets are cache-busted dynamically with a `?v=` query derived from each file's mtime, so no manual cache bump is needed after CSS/JS/manifest changes.

---

## Export Pattern Reference
`EXPORT-PATTERN-WRITEUP.md` documents the jsPDF + LZ-string export/share pattern from the sister app `minis.tashefamily.com`. Use this as the reference implementation when adding PDF export or shareable links to this app.

Key points for adapting to this app:
- Use **jsPDF** (CDN) for client-side PDF generation — no server needed
- The checklist export should respect whatever filters are currently active (pass `getFiltered()` / `getMinorFiltered()` output, not `allPlayers`)
- Export button should appear in the filter bar when any filter is active (or always — TBD)
- PDF layout: title block (tab name + active filters), then a two-column checklist grid (name + checkbox), multi-page overflow guard at `y > 270`

---

## Known Gotchas
1. `postgres://` URLs must be rewritten to `postgresql://` — handled in `app.py` and `import_data.py`
2. Railway internal vs. public DB URLs are different instances — always use public URL for local scripts
3. Minor league API `parentOrgIds` param is silently ignored — filter in Python, not the API query
4. iOS Safari zooms on inputs with `font-size < 16px` — keep all inputs at `1rem` minimum
5. Active players have `year_end = null` — JS filters use `?? 9999` to avoid excluding them
