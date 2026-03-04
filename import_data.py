"""
One-time data import script.

Source: MLB Stats API — fetches every Phillies roster season by season (1883–present).
No external file downloads required.

Run locally:
    $env:DATABASE_URL="postgresql://..."
    python import_data.py

Set DATABASE_URL in your environment before running.
"""

import os
import time

import requests
from dotenv import load_dotenv
from flask import Flask
from models import Player, db

load_dotenv()

# ── Database setup ─────────────────────────────────────────────────────────────
_db_url = os.environ.get('DATABASE_URL', 'postgresql://localhost/phillies')
if _db_url.startswith('postgres://'):
    _db_url = _db_url.replace('postgres://', 'postgresql://', 1)

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = _db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

# ── Constants ──────────────────────────────────────────────────────────────────
MLB_ROSTER_URL = (
    'https://statsapi.mlb.com/api/v1/teams/143/roster'
    '?rosterType=fullRoster&season={year}&hydrate=person(stats(type=career))'
)
MLB_PHOTO_URL = (
    'https://img.mlbstatic.com/mlb-photos/image/upload/'
    'd_people:generic:headshot:67:current.png/'
    'w_213,q_auto:best/v1/people/{mlbam_id}/headshot/67/current'
)

FIRST_YEAR   = 1883
CURRENT_YEAR = 2025


# ── Fetch all Phillies by season ───────────────────────────────────────────────
def fetch_all_phillies() -> dict[int, dict]:
    """
    Query MLB Stats API for every Phillies season 1883–CURRENT_YEAR.
    Returns a dict keyed by MLBAM person_id.
    Note: the API has complete data from ~1920s onward; pre-1920 may be sparse.
    """
    players: dict[int, dict] = {}
    seasons_with_data = 0

    total = CURRENT_YEAR - FIRST_YEAR + 1
    print(f'  Querying {total} seasons ({FIRST_YEAR}–{CURRENT_YEAR})…')
    print('  Progress: ', end='', flush=True)

    for i, year in enumerate(range(FIRST_YEAR, CURRENT_YEAR + 1)):
        # Progress dot every 10 years
        if i % 10 == 0:
            print(f'{year}', end=' ', flush=True)

        try:
            r = requests.get(
                MLB_ROSTER_URL.format(year=year),
                timeout=15,
                headers={'User-Agent': 'phillies-roster-import/1.0'},
            )
            if r.status_code != 200:
                continue

            roster = r.json().get('roster', [])
            if not roster:
                continue

            seasons_with_data += 1
            for entry in roster:
                pid  = entry['person']['id']
                name = entry['person']['fullName']
                pos  = (entry.get('position') or {}).get('abbreviation', 'UTIL')

                if pid not in players:
                    players[pid] = {
                        'mlb_id':    pid,
                        'full_name': name,
                        'position':  pos,
                        'years':     [],
                    }
                players[pid]['years'].append(year)

        except requests.exceptions.Timeout:
            pass  # Skip year silently on timeout
        except Exception as e:
            print(f'\n    Warning {year}: {e}')

        # Be a polite API client — tiny pause every 20 requests
        if i % 20 == 19:
            time.sleep(0.3)

    print()  # newline after progress
    print(f'  Got data for {seasons_with_data} seasons, '
          f'{len(players):,} unique players found.')
    return players


# ── Write to database ──────────────────────────────────────────────────────────
def import_all():
    with app.app_context():
        db.create_all()

        existing = Player.query.count()
        if existing > 0:
            print(f'\nDatabase already contains {existing:,} players.')
            ans = input('Re-import and overwrite? (y/N): ').strip().lower()
            if ans != 'y':
                print('Aborted.')
                return
            Player.query.delete()
            db.session.commit()
            print('Cleared existing data.')

        print('\n[1/2] Fetching all Phillies players from MLB Stats API…')
        all_players = fetch_all_phillies()

        print('\n[2/2] Building database records…')
        records = []
        for data in all_players.values():
            years      = sorted(set(data['years']))
            year_start = years[0]
            year_end   = years[-1]
            years_str  = (str(year_start) if year_start == year_end
                          else f'{year_start}–{year_end}')

            records.append(Player(
                player_id=f'mlb{data["mlb_id"]}',
                full_name=data['full_name'],
                position=data['position'],
                year_start=year_start,
                year_end=year_end,
                years_active=years_str,
                mlb_id=data['mlb_id'],
                photo_url=MLB_PHOTO_URL.format(mlbam_id=data['mlb_id']),
                collection_status="Don't Have",
            ))

        db.session.bulk_save_objects(records)
        db.session.commit()
        print(f'\n✓ Imported {len(records):,} Philadelphia Phillies players.')
        print('  Import complete!\n')


if __name__ == '__main__':
    import_all()
