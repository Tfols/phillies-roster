"""
Scrape the Philadelphia Phillies minor league affiliates from Wikipedia
and seed the affiliates table.

Wikipedia page: https://en.wikipedia.org/wiki/List_of_Philadelphia_Phillies_minor_league_affiliates

Page structure:
  Table 0 — Current affiliates: Class | Team | League | Location | Ballpark | Affiliated (start year)
  Tables 1+ — Historical by season: Season | Triple-A | Double-A | ... | Ref

Usage:
  python import_affiliates.py          # seed to DB (skips if already populated)
  python import_affiliates.py --force  # always re-seed
"""

import re
import sys
import os
import argparse

import requests
from bs4 import BeautifulSoup

WIKI_URL = 'https://en.wikipedia.org/wiki/List_of_Philadelphia_Phillies_minor_league_affiliates'
CURRENT_YEAR = 2025

LEVEL_MAP = {
    'triple-a': 'Triple-A',
    'aaa': 'Triple-A',
    'double-a': 'Double-A',
    'aa': 'Double-A',
    'high-a': 'High-A',
    'class a-advanced': 'High-A',
    'a-advanced': 'High-A',
    'class a advanced': 'High-A',
    'a advanced': 'High-A',
    'single-a': 'Single-A',
    'class a': 'Single-A',
    'low-a': 'Single-A',
    'low a': 'Single-A',
    'class a short season': 'Short-Season A',
    'a short season': 'Short-Season A',
    'short season a': 'Short-Season A',
    'rookie': 'Rookie',
    'r': 'Rookie',
    'foreign rookie': 'Rookie (Intl)',
}


def normalize_level(s):
    key = s.strip().lower()
    return LEVEL_MAP.get(key, s.strip())


def scrape_affiliates():
    """
    Return a list of affiliate dicts:
      {team_name, level, league, location, year_start, year_end}
    year_end=None means currently affiliated.
    """
    print(f'Fetching {WIKI_URL} ...')
    resp = requests.get(WIKI_URL, timeout=20,
                        headers={'User-Agent': 'PhilliesRosterApp/1.0'})
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'lxml')

    tables = soup.find_all('table', class_='wikitable')
    if not tables:
        print('WARNING: No wikitables found — page structure may have changed.')
        return []

    affiliates = []

    # ── Table 0: Current affiliates ──────────────────────────────────────────
    # Columns: Class | Team | League | Location | Ballpark | Affiliated (start yr)
    # The Class (level) cell may span multiple rows (rowspan) for DSL teams.
    current_table = tables[0]
    tbody = current_table.find('tbody') or current_table
    current_level = None

    for row in tbody.find_all('tr'):
        cells = row.find_all(['td', 'th'])
        if not cells:
            continue
        # Skip pure header rows
        if all(c.name == 'th' for c in cells):
            continue

        # Level cell: present when not rowspan-continued
        cell0_text = cells[0].get_text(strip=True)
        if cell0_text and cell0_text not in ('Class', 'Level', ''):
            current_level = normalize_level(cell0_text)
            data_cells = cells[1:]   # remaining: Team, League, Location, Ballpark, Year
        else:
            data_cells = cells       # level was rowspanned — remaining cells shift left

        if len(data_cells) < 4:
            continue

        team_name = data_cells[0].get_text(strip=True)
        league    = data_cells[1].get_text(strip=True) if len(data_cells) > 1 else ''
        location  = data_cells[2].get_text(strip=True) if len(data_cells) > 2 else ''
        aff_text  = data_cells[-1].get_text(strip=True)   # last cell = affiliated year

        try:
            year_start = int(re.search(r'\d{4}', aff_text).group())
        except Exception:
            year_start = CURRENT_YEAR

        if team_name and current_level:
            affiliates.append({
                'team_name':  team_name,
                'level':      current_level,
                'league':     league,
                'location':   location,
                'year_start': year_start,
                'year_end':   None,   # currently affiliated
            })

    print(f'  Current affiliates found: {len(affiliates)}')

    # ── Tables 1+: Historical season tables ──────────────────────────────────
    # Row 0 = header: Season | Triple-A | Double-A | ... | Ref
    # Rows 1+ = data: year  | team     | team     | ...
    team_years = {}  # (team_name, level) -> set of years
    current_names = {a['team_name'] for a in affiliates}

    for table in tables[1:]:
        tbody = table.find('tbody') or table
        all_rows = tbody.find_all('tr')
        if len(all_rows) < 2:
            continue

        # Extract level headers from first row
        header_row = all_rows[0]
        raw_headers = [th.get_text(strip=True) for th in header_row.find_all(['th', 'td'])]
        if not raw_headers or not re.search(r'season', raw_headers[0], re.I):
            continue

        level_cols = []
        for h in raw_headers[1:]:
            if re.search(r'^ref', h, re.I):
                break
            level_cols.append(normalize_level(h))

        for row in all_rows[1:]:
            cells = row.find_all(['th', 'td'])
            if not cells:
                continue
            season_text = cells[0].get_text(strip=True)
            try:
                season = int(re.search(r'\d{4}', season_text).group())
            except Exception:
                continue

            for col_idx, level in enumerate(level_cols):
                cell_idx = col_idx + 1
                if cell_idx >= len(cells):
                    break
                cell = cells[cell_idx]
                # Multiple teams may be in one cell separated by <br>
                raw_text = cell.get_text(separator='|||', strip=True)
                teams_in_cell = [
                    t.strip() for t in raw_text.split('|||')
                    if t.strip() and t.strip() not in ('—', '–', '-', '')
                ]
                for team_name in teams_in_cell:
                    if team_name in current_names:
                        continue   # already captured in current table
                    key = (team_name, level)
                    team_years.setdefault(key, set()).add(season)

    # Convert team_years to affiliate records
    for (team_name, level), years in team_years.items():
        if not years:
            continue
        affiliates.append({
            'team_name':  team_name,
            'level':      level,
            'league':     None,
            'location':   None,
            'year_start': min(years),
            'year_end':   max(years),
        })

    print(f'  Total affiliate records scraped: {len(affiliates)}')
    return affiliates


def seed_to_db(force=False):
    """Seed affiliates table. Skips if already populated (unless force=True)."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from app import app, db
    from models import Affiliate

    with app.app_context():
        existing = Affiliate.query.count()
        if existing > 0 and not force:
            print(f'Affiliates table already has {existing} records. Use --force to re-seed.')
            return

        if force and existing > 0:
            print(f'Force mode: deleting {existing} existing affiliates...')
            Affiliate.query.delete()
            db.session.commit()

        records = scrape_affiliates()
        for aff in records:
            db.session.add(Affiliate(
                team_name=aff['team_name'],
                level=aff['level'],
                league=aff.get('league'),
                location=aff.get('location'),
                year_start=aff['year_start'],
                year_end=aff.get('year_end'),
            ))
        db.session.commit()
        print(f'Inserted {len(records)} affiliates into DB.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Seed Phillies affiliates from Wikipedia')
    parser.add_argument('--force', action='store_true', help='Re-seed even if data exists')
    args = parser.parse_args()
    seed_to_db(force=args.force)
