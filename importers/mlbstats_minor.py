"""
MLB Stats API — Phillies minor league player importer.

Coverage: 2005–present (pre-2005 data is very sparse in the API).

Pluggable interface — see baseball_cube_stub.py for the contract.

API endpoints used:
  GET /teams?sportIds=11,12,13,14,16,17&parentOrgIds=143&season={year}
      → returns all MiLB teams affiliated with the Phillies for that year

  GET /teams/{teamId}/roster?rosterType=fullRoster&season={year}&hydrate=person
      → returns full roster with person details (name, position, birthDate)

Sport IDs:
  11 = Triple-A   12 = Double-A   13 = High-A
  14 = Single-A   16 = Rookie     17 = Rookie (Intl / DSL)
"""

import time
from datetime import date

import requests

MLB_API        = 'https://statsapi.mlb.com/api/v1'
PHILLIES_ORG   = 143
SPORT_IDS      = '11,12,13,14,16,17'
DELAY          = 0.2   # seconds between API calls

SPORT_LEVEL = {
    11: 'Triple-A',
    12: 'Double-A',
    13: 'High-A',
    14: 'Single-A',
    16: 'Rookie',
    17: 'Rookie (Intl)',
}


def _get(url, timeout=20):
    try:
        r = requests.get(url, timeout=timeout)
        return r.json() if r.status_code == 200 else {}
    except Exception as e:
        print(f'    API error: {e}')
        return {}


def _parse_date(s):
    if not s:
        return None
    try:
        return date.fromisoformat(str(s)[:10])
    except Exception:
        return None


def _photo_url(mlb_id):
    if not mlb_id:
        return None
    return (
        f'https://img.mlbstatic.com/mlb-photos/image/upload/'
        f'w_213,q_auto:best/v1/people/{mlb_id}/headshot/67/current'
    )


def import_minors(app, db, Affiliate, MinorPlayer, Player,
                  start_year=2005, end_year=2025):
    """
    Import Phillies minor league players from the MLB Stats API.

    Args:
        app, db         — Flask app + SQLAlchemy instance
        Affiliate       — Affiliate model class
        MinorPlayer     — MinorPlayer model class
        Player          — MLB Player model class (used for dedup after import)
        start_year      — first season to import (default 2005)
        end_year        — last season to import (default 2025)

    Returns:
        (inserted, updated, skipped) tuple
    """
    inserted = updated = skipped = 0
    affiliate_cache = {}   # mlb_team_id -> Affiliate.id

    with app.app_context():
        for year in range(start_year, end_year + 1):
            print(f'\n── {year} ──')
            data = _get(f'{MLB_API}/teams?sportIds={SPORT_IDS}'
                        f'&parentOrgIds={PHILLIES_ORG}&season={year}')
            teams = data.get('teams', [])
            time.sleep(DELAY)

            if not teams:
                print(f'  No affiliates found')
                continue

            print(f'  {len(teams)} affiliate(s)')

            for team in teams:
                mlb_team_id = team['id']
                team_name   = team.get('name', '')
                sport_id    = team.get('sport', {}).get('id', 0)
                level       = SPORT_LEVEL.get(sport_id, 'Unknown')

                # ── Get / create Affiliate record ────────────────────────────
                if mlb_team_id not in affiliate_cache:
                    db_aff = Affiliate.query.filter_by(mlb_team_id=mlb_team_id).first()
                    if not db_aff:
                        db_aff = Affiliate.query.filter_by(team_name=team_name).first()
                    if not db_aff:
                        db_aff = Affiliate(
                            mlb_team_id=mlb_team_id,
                            team_name=team_name,
                            level=level,
                            year_start=year,
                            year_end=year,
                        )
                        db.session.add(db_aff)
                        db.session.flush()
                    else:
                        if db_aff.mlb_team_id is None:
                            db_aff.mlb_team_id = mlb_team_id
                        db_aff.year_end = max(db_aff.year_end or year, year)
                    db.session.commit()
                    affiliate_cache[mlb_team_id] = db_aff.id

                affiliate_id = affiliate_cache[mlb_team_id]

                # ── Pull roster ──────────────────────────────────────────────
                roster_data = _get(
                    f'{MLB_API}/teams/{mlb_team_id}/roster'
                    f'?rosterType=fullRoster&season={year}&hydrate=person'
                )
                roster = roster_data.get('roster', [])
                time.sleep(DELAY)

                for entry in roster:
                    person    = entry.get('person', {})
                    mlb_id    = person.get('id')
                    full_name = person.get('fullName', '').strip()
                    position  = entry.get('position', {}).get('abbreviation', '')
                    birth_date = _parse_date(person.get('birthDate'))

                    if not full_name:
                        skipped += 1
                        continue

                    # ── Upsert logic ─────────────────────────────────────────
                    existing = None
                    if mlb_id:
                        existing = MinorPlayer.query.filter_by(mlb_id=mlb_id).first()
                    if not existing and birth_date:
                        existing = MinorPlayer.query.filter_by(
                            full_name=full_name, birth_date=birth_date
                        ).first()

                    if existing:
                        if year > (existing.year_end or 0):
                            existing.year_end      = year
                            existing.affiliate_id   = affiliate_id
                            existing.affiliate_name = team_name
                            existing.level          = level
                        if existing.year_start and year < existing.year_start:
                            existing.year_start = year
                        if not existing.birth_date and birth_date:
                            existing.birth_date = birth_date
                        if not existing.mlb_id and mlb_id:
                            existing.mlb_id   = mlb_id
                            existing.photo_url = _photo_url(mlb_id)
                        updated += 1
                    else:
                        db.session.add(MinorPlayer(
                            mlb_id         = mlb_id,
                            full_name      = full_name,
                            position       = position,
                            birth_date     = birth_date,
                            year_start     = year,
                            year_end       = year,
                            affiliate_id   = affiliate_id,
                            affiliate_name = team_name,
                            level          = level,
                            photo_url      = _photo_url(mlb_id),
                            data_source    = 'mlbstats_api',
                        ))
                        inserted += 1

            db.session.commit()

        print(f'\nMLB Stats API import done: '
              f'{inserted} inserted, {updated} updated, {skipped} skipped.')
        return inserted, updated, skipped
