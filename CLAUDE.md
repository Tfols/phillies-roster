# CLAUDE.md — Phillies Roster PWA

Philadelphia Phillies All-Time Autograph Tracker. Flask + PostgreSQL PWA, deployed to Railway.

---

## Vault

Vault location: `C:\Users\tomfo\vault\projects\phillies\`

| File | Contains |
|------|----------|
| `status.md` | Current build state, completed work, known issues |
| `decisions.md` | Architectural and product decisions with rationale |
| `plan.md` | Phase definitions, active phase, deferred features |
| `architecture.md` | Schema, API routes, file structure, frontend patterns |

**Read at session start by task type:**
- Build / feature work → `architecture.md` + `plan.md`
- Fix / debug → `status.md` + `architecture.md`
- Planning → `plan.md` + `decisions.md`
- Uncertain → read all four

**Update at session end** using `/update-docs` if anything changed.

---

## Context Management

Context is a limited resource. Use subagents (Agent tool) to keep exploration and research out of the main conversation.

**Spawn a subagent for:**
- Reading 3+ files to answer a question about existing code
- Investigating how a feature is implemented before building on it
- Any task where only the summary matters, not the raw file contents

**Stay in main context for:**
- Direct file edits
- Reading 1–2 specific files
- Tasks where intermediate steps need to be visible

---

## Live App
- **URL:** https://phillies.tashefamily.com
- **Password:** `TashePhillies` (Railway env var `APP_PASSWORD`)
- **GitHub:** https://github.com/Tfols/phillies-roster (branch: `master`)
- **Hosting:** Railway (free tier), DNS via Cloudflare

---

## Deployment
```bash
git push origin master   # Railway auto-deploys via Nixpacks
```
No build step. No service worker to version-bump — static assets use `?v=<mtime>` cache-busting automatically.

---

## CRITICAL: Two Database URLs
Railway exposes two URLs that point to **different database instances**:

| Use | URL |
|-----|-----|
| Web app | `postgres.railway.internal:5432` (auto-set as `DATABASE_URL`) |
| Local scripts | `postgresql://postgres:tjlGaMTHVDeJJjkyIZPJjfLPneaynSHQ@centerbeam.proxy.rlwy.net:18837/railway` |

**Always use the public URL for local scripts:**
```powershell
$env:DATABASE_URL="postgresql://postgres:tjlGaMTHVDeJJjkyIZPJjfLPneaynSHQ@centerbeam.proxy.rlwy.net:18837/railway"
```
Do NOT use `maglev.proxy.rlwy.net:44703` — stale/old instance.

---

## Known Gotchas
1. `postgres://` URLs must be rewritten to `postgresql://` — handled in `app.py` and `import_data.py`
2. Minor league API `parentOrgIds` param is silently ignored — filter by `parentOrgId == 143` in Python, not the API query
3. iOS Safari zooms on inputs with `font-size < 16px` — all inputs must stay at `1rem` minimum
4. Active players have `year_end = null` — JS filters use `?? 9999` to avoid excluding them

---

## Export Pattern Reference
`EXPORT-PATTERN-WRITEUP.md` in the project root documents the jsPDF + LZ-string pattern from minis.tashefamily.com. Use as the reference implementation for the PDF checklist export feature (Phase 7 — see `plan.md`).
