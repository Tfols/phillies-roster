"""
Baseball Cube Data Importer — STUB / PLACEHOLDER
=================================================

This module is a placeholder for future Baseball Cube data integration.
When you purchase Baseball Cube data, implement the import_minors() function
below following the interface contract.

INTERFACE CONTRACT
==================
Every importer module must expose:

    import_minors(app, db, Affiliate, MinorPlayer, Player,
                  start_year=None, end_year=None, **kwargs)
        -> (inserted: int, updated: int, skipped: int)

Rules:
  1. Use app.app_context() OR expect the caller to have already pushed a context.
  2. Upsert players — never blindly insert without checking for duplicates.
  3. Deduplication order: mlb_id first, then (full_name + birth_date), then name only.
  4. Set data_source = 'baseball_cube' on all records you create/update.
  5. Return (inserted, updated, skipped) tuple.

HOW TO MAP BASEBALL CUBE FIELDS TO MinorPlayer
===============================================

Baseball Cube typically provides CSV exports. Map columns like this:

  BC field          → MinorPlayer field
  ──────────────    ──────────────────────────────────────────────────────
  FirstName+Last    → full_name  (f"{first} {last}")
  DOB / Birthdate   → birth_date (date.fromisoformat(dob))
  Pos               → position   (standardise — see POSITION_MAP below)
  Team              → affiliate_name (run through TEAM_NAME_MAP)
  Level             → level      (run through LEVEL_MAP below)
  Season / Year     → year_start / year_end (update on subsequent imports)
  MLBID (if avail)  → mlb_id

LOADING DATA
============
Pass the path to the Baseball Cube export file/directory via data_path kwarg:

  from importers import baseball_cube_stub
  baseball_cube_stub.import_minors(app, db, Affiliate, MinorPlayer, Player,
                                   data_path='/path/to/export.csv')
"""

from datetime import date


# ── Normalisation maps ────────────────────────────────────────────────────────
# Extend these as you discover naming differences.

LEVEL_MAP = {
    'AAA':    'Triple-A',
    'AA':     'Double-A',
    'A+':     'High-A',
    'A':      'Single-A',
    'A-':     'Short-Season A',
    'Rk':     'Rookie',
    'DSL':    'Rookie (Intl)',
    'VSL':    'Rookie (Intl)',
    'R':      'Rookie',
}

POSITION_MAP = {
    'RHP': 'P',  'LHP': 'P',  'SP': 'P',  'RP': 'P',
    'CA':  'C',
    'IF':  'IF', 'OF':  'OF',
    # Add more as needed
}

TEAM_NAME_MAP = {
    # 'Baseball Cube Name': 'Standard Name as stored in Affiliate table',
    # Example:
    # 'Lehigh Valley': 'Lehigh Valley IronPigs',
    # 'Jersey Shore':  'Jersey Shore BlueClaws',
}


def _parse_date(s):
    if not s:
        return None
    try:
        return date.fromisoformat(str(s)[:10])
    except Exception:
        return None


def _norm_position(pos):
    return POSITION_MAP.get(pos, pos)


def _norm_team(name):
    return TEAM_NAME_MAP.get(name, name)


def _norm_level(level):
    return LEVEL_MAP.get(level, level)


def import_minors(app, db, Affiliate, MinorPlayer, Player,
                  start_year=None, end_year=None, data_path=None, **kwargs):
    """
    Baseball Cube importer — NOT YET IMPLEMENTED.

    Remove the NotImplementedError and fill in the CSV parsing logic
    once you have the Baseball Cube data export.
    """
    raise NotImplementedError(
        'Baseball Cube importer is not yet implemented.\n'
        'See importers/baseball_cube_stub.py for instructions.\n'
        f'data_path={data_path}, start_year={start_year}, end_year={end_year}'
    )

    # ── Implementation skeleton (fill in below) ───────────────────────────────
    # with app.app_context():
    #     inserted = updated = skipped = 0
    #     affiliate_cache = {}
    #
    #     with open(data_path, newline='', encoding='utf-8') as f:
    #         reader = csv.DictReader(f)
    #         for row in reader:
    #             year = int(row['Season'])
    #             if start_year and year < start_year: continue
    #             if end_year   and year > end_year:   continue
    #
    #             full_name   = f"{row['FirstName']} {row['LastName']}".strip()
    #             birth_date  = _parse_date(row.get('DOB'))
    #             position    = _norm_position(row.get('Pos', ''))
    #             team_name   = _norm_team(row.get('Team', ''))
    #             level       = _norm_level(row.get('Level', ''))
    #             mlb_id      = int(row['MLBID']) if row.get('MLBID') else None
    #
    #             # Get or create Affiliate record
    #             if team_name not in affiliate_cache:
    #                 aff = Affiliate.query.filter_by(team_name=team_name).first()
    #                 if not aff:
    #                     aff = Affiliate(team_name=team_name, level=level,
    #                                     year_start=year, year_end=year)
    #                     db.session.add(aff)
    #                     db.session.flush()
    #                 affiliate_cache[team_name] = aff.id
    #
    #             # Upsert player (same logic as mlbstats_minor.py)
    #             existing = None
    #             if mlb_id:
    #                 existing = MinorPlayer.query.filter_by(mlb_id=mlb_id).first()
    #             if not existing and birth_date:
    #                 existing = MinorPlayer.query.filter_by(
    #                     full_name=full_name, birth_date=birth_date).first()
    #
    #             if existing:
    #                 if year > (existing.year_end or 0):
    #                     existing.year_end = year
    #                 updated += 1
    #             else:
    #                 db.session.add(MinorPlayer(
    #                     mlb_id=mlb_id, full_name=full_name, position=position,
    #                     birth_date=birth_date, year_start=year, year_end=year,
    #                     affiliate_id=affiliate_cache[team_name],
    #                     affiliate_name=team_name, level=level,
    #                     data_source='baseball_cube',
    #                 ))
    #                 inserted += 1
    #
    #     db.session.commit()
    #     return inserted, updated, skipped
