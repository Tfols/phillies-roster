"""
One-time data import script.

Sources:
  1. Chadwick Bureau Baseball Databank (Lahman-compatible) – all historical players
  2. Chadwick Bureau ID Register                           – maps Lahman IDs → MLBAM IDs
  3. MLB Stats API                                         – fills gaps for the current season

Run locally:
    python import_data.py

Run on Railway (after first deploy):
    railway run python import_data.py

Set DATABASE_URL in your environment or .env file before running locally.
"""

import csv
import io
import os
from collections import defaultdict

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
REGISTER_URL = (
    'https://raw.githubusercontent.com/chadwickbureau/register/master/data/people.csv'
)
MLB_ROSTER_URL = (
    'https://statsapi.mlb.com/api/v1/teams/143/roster'
    '?rosterType=fullRoster&season={year}'
)
MLB_PERSON_URL = 'https://statsapi.mlb.com/api/v1/people/{pid}'
MLB_PHOTO_URL = (
    'https://img.mlbstatic.com/mlb-photos/image/upload/'
    'd_people:generic:headshot:67:current.png/'
    'w_213,q_auto:best/v1/people/{mlbam_id}/headshot/67/current'
)
CURRENT_YEAR = 2025

# Position field → abbreviation
POSITION_MAP = {
    'G_p':  'P',
    'G_c':  'C',
    'G_1b': '1B',
    'G_2b': '2B',
    'G_3b': '3B',
    'G_ss': 'SS',
    'G_lf': 'LF',
    'G_cf': 'CF',
    'G_rf': 'RF',
    'G_of': 'OF',
    'G_dh': 'DH',
}


# ── Helpers ────────────────────────────────────────────────────────────────────
def primary_position(pos_games: dict) -> str:
    """Return the position with the most games (ignoring PH/PR)."""
    filtered = {k: v for k, v in pos_games.items()
                if k in POSITION_MAP and v > 0}
    if not filtered:
        return 'UTIL'
    return POSITION_MAP[max(filtered, key=filtered.get)]


# ── Step 1: Lahman / Chadwick Databank ────────────────────────────────────────
# Try multiple branch/path combos — repo layout has shifted over time
_RAW = 'https://raw.githubusercontent.com/chadwickbureau/baseballdatabank/{branch}/{subdir}{file}'
_CANDIDATES = [
    ('master', 'core/'), ('main', 'core/'),
    ('master', ''),      ('main', ''),
]

def _fetch_csv(filename: str) -> str:
    for branch, subdir in _CANDIDATES:
        url = _RAW.format(branch=branch, subdir=subdir, file=filename)
        try:
            r = requests.get(url, timeout=60)
            if r.status_code == 200:
                print(f'    Fetched {filename} from {url}')
                return r.text
        except Exception:
            pass
    raise RuntimeError(f'Could not download {filename} from any known Chadwick URL')


def load_databank():
    print('  Downloading People.csv and Appearances.csv from Chadwick Bureau…')

    people: dict[str, dict] = {}
    phi: dict[str, dict] = defaultdict(
        lambda: {'years': [], 'pos': defaultdict(int)}
    )

    for row in csv.DictReader(io.StringIO(_fetch_csv('People.csv'))):
        people[row['playerID']] = row
    print(f'    Loaded {len(people):,} people')

    count = 0
    for row in csv.DictReader(io.StringIO(_fetch_csv('Appearances.csv'))):
        if row['teamID'] == 'PHI':
            pid = row['playerID']
            phi[pid]['years'].append(int(row['yearID']))
            for col in POSITION_MAP:
                try:
                    phi[pid]['pos'][col] += int(row.get(col) or 0)
                except ValueError:
                    pass
            count += 1
    print(f'    Found {len(phi):,} unique Phillies players '
          f'({count:,} appearance-rows)')

    return people, phi


# ── Step 2: MLBAM ID register ──────────────────────────────────────────────────
def load_mlbam_map() -> dict[str, int]:
    """Map Lahman playerID → MLBAM person_id."""
    print('  Downloading Chadwick ID register…')
    try:
        r = requests.get(REGISTER_URL, timeout=60)
        r.raise_for_status()
        mlbam: dict[str, int] = {}
        for row in csv.DictReader(io.StringIO(r.text)):
            lahman_key = row.get('key_lahman', '').strip()
            mlbam_key  = row.get('key_mlbam', '').strip()
            if lahman_key and mlbam_key:
                try:
                    mlbam[lahman_key] = int(mlbam_key)
                except ValueError:
                    pass
        print(f'    Loaded {len(mlbam):,} MLBAM mappings')
        return mlbam
    except Exception as exc:
        print(f'    WARNING: could not load MLBAM register ({exc}). Photos skipped.')
        return {}


# ── Step 3: MLB Stats API – current season supplement ─────────────────────────
def fetch_current_season(existing_mlbam_ids: set[int]) -> list[dict]:
    """Return players from the current season not already in existing_mlbam_ids."""
    print(f'  Fetching {CURRENT_YEAR} MLB Stats API roster…')
    new_players = []
    try:
        r = requests.get(MLB_ROSTER_URL.format(year=CURRENT_YEAR), timeout=30)
        r.raise_for_status()
        roster = r.json().get('roster', [])
        for entry in roster:
            pid = entry['person']['id']
            if pid in existing_mlbam_ids:
                continue
            # Fetch full player detail
            detail_r = requests.get(MLB_PERSON_URL.format(pid=pid), timeout=15)
            if not detail_r.ok:
                continue
            person = detail_r.json().get('people', [{}])[0]
            pos_abbr = (person.get('primaryPosition') or {}).get('abbreviation', 'UTIL')
            new_players.append({
                'player_id': f'mlb{pid}',
                'full_name': person.get('fullName', ''),
                'position':  pos_abbr,
                'year_start': CURRENT_YEAR,
                'year_end':   CURRENT_YEAR,
                'years_active': str(CURRENT_YEAR),
                'mlb_id':    pid,
                'photo_url': MLB_PHOTO_URL.format(mlbam_id=pid),
            })
        print(f'    {len(new_players)} new players from {CURRENT_YEAR} roster')
    except Exception as exc:
        print(f'    WARNING: MLB Stats API call failed ({exc})')
    return new_players


# ── Step 4: Write to database ──────────────────────────────────────────────────
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

        print('\n[1/3] Loading Chadwick Baseball Databank…')
        people, phi = load_databank()

        print('\n[2/3] Loading MLBAM ID register…')
        mlbam_map = load_mlbam_map()

        print('\n[3/3] Building player records…')
        records = []
        mlbam_ids_used: set[int] = set()

        for pid, data in phi.items():
            person = people.get(pid)
            if not person:
                continue
            first = person.get('nameFirst', '').strip()
            last  = person.get('nameLast', '').strip()
            full  = f'{first} {last}'.strip()
            if not full:
                continue

            years      = sorted(set(data['years']))
            year_start = years[0]
            year_end   = years[-1]
            years_str  = (str(year_start) if year_start == year_end
                          else f'{year_start}–{year_end}')

            mlbam_id  = mlbam_map.get(pid)
            photo_url = MLB_PHOTO_URL.format(mlbam_id=mlbam_id) if mlbam_id else None
            if mlbam_id:
                mlbam_ids_used.add(mlbam_id)

            records.append(Player(
                player_id=pid,
                full_name=full,
                position=primary_position(dict(data['pos'])),
                year_start=year_start,
                year_end=year_end,
                years_active=years_str,
                mlb_id=mlbam_id,
                photo_url=photo_url,
                collection_status="Don't Have",
            ))

        # Supplement with current-season players missing from databank
        for p in fetch_current_season(mlbam_ids_used):
            records.append(Player(**p, collection_status="Don't Have"))

        db.session.bulk_save_objects(records)
        db.session.commit()
        print(f'\n✓ Imported {len(records):,} Philadelphia Phillies players.')
        print('  Import complete!\n')


if __name__ == '__main__':
    import_all()
