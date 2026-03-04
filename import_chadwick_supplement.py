"""
import_chadwick_supplement.py

Adds pre-modern Phillies players from the Chadwick/Lahman databank
that were missed by the MLB Stats API (typically pre-1920s players).

Your existing players and collection statuses are NOT touched.
Only genuinely new players are inserted.

Usage:
    1. Download the Chadwick databank ZIP from your browser:
         https://github.com/chadwickbureau/baseballdatabank/archive/refs/heads/master.zip
       (or /main.zip if master 404s)

    2. Extract the ZIP anywhere, e.g.:
         C:\\Users\\tomfo\\Downloads\\baseballdatabank-master

    3. Set DATABASE_URL (same as before) then run:
         python import_chadwick_supplement.py "C:\\Users\\tomfo\\Downloads\\baseballdatabank-master"

    You can also pass the ZIP file directly — the script handles both.
"""

import argparse
import csv
import io
import os
import sys
import zipfile
from collections import defaultdict

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

# Position field → abbreviation
POSITION_MAP = {
    'G_p':  'P',  'G_c':  'C',  'G_1b': '1B', 'G_2b': '2B',
    'G_3b': '3B', 'G_ss': 'SS', 'G_lf': 'LF', 'G_cf': 'CF',
    'G_rf': 'RF', 'G_of': 'OF', 'G_dh': 'DH',
}


def primary_position(pos_games: dict) -> str:
    filtered = {k: v for k, v in pos_games.items() if k in POSITION_MAP and v > 0}
    if not filtered:
        return 'UTIL'
    return POSITION_MAP[max(filtered, key=filtered.get)]


# ── CSV loading ────────────────────────────────────────────────────────────────
def _open_csv(source, filename: str):
    """
    Given either a directory path or an open ZipFile, find and return
    a DictReader for the named CSV.  Searches recursively for the file.
    """
    if isinstance(source, zipfile.ZipFile):
        matches = [n for n in source.namelist()
                   if n.endswith(f'/{filename}') or n == filename]
        if not matches:
            raise FileNotFoundError(f'{filename} not found in ZIP')
        with source.open(matches[0]) as f:
            content = io.TextIOWrapper(f, encoding='utf-8').read()
        return csv.DictReader(io.StringIO(content))
    else:
        # Directory — walk to find the file
        for root, _, files in os.walk(source):
            if filename in files:
                f = open(os.path.join(root, filename), encoding='utf-8')
                return csv.DictReader(f)
        raise FileNotFoundError(f'{filename} not found under {source}')


def load_chadwick(path: str):
    """Load People.csv and Appearances.csv from ZIP or folder."""
    if path.lower().endswith('.zip'):
        print(f'  Reading ZIP: {path}')
        with zipfile.ZipFile(path) as z:
            people_reader = _open_csv(z, 'People.csv')
            people = {row['playerID']: row for row in people_reader}
            print(f'  Loaded {len(people):,} people')

            phi = defaultdict(lambda: {'years': [], 'pos': defaultdict(int)})
            app_reader = _open_csv(z, 'Appearances.csv')
            count = 0
            for row in app_reader:
                if row['teamID'] == 'PHI':
                    pid = row['playerID']
                    phi[pid]['years'].append(int(row['yearID']))
                    for col in POSITION_MAP:
                        try:
                            phi[pid]['pos'][col] += int(row.get(col) or 0)
                        except ValueError:
                            pass
                    count += 1
    else:
        print(f'  Reading folder: {path}')
        people = {row['playerID']: row
                  for row in _open_csv(path, 'People.csv')}
        print(f'  Loaded {len(people):,} people')

        phi = defaultdict(lambda: {'years': [], 'pos': defaultdict(int)})
        count = 0
        for row in _open_csv(path, 'Appearances.csv'):
            if row['teamID'] == 'PHI':
                pid = row['playerID']
                phi[pid]['years'].append(int(row['yearID']))
                for col in POSITION_MAP:
                    try:
                        phi[pid]['pos'][col] += int(row.get(col) or 0)
                    except ValueError:
                        pass
                count += 1

    print(f'  {len(phi):,} unique Phillies in Chadwick '
          f'({count:,} appearance rows)')
    return people, phi


# ── Main ───────────────────────────────────────────────────────────────────────
def supplement(databank_path: str):
    with app.app_context():
        db.create_all()

        # Build set of normalised names already in DB
        existing_names = {
            p.full_name.strip().lower()
            for p in Player.query.with_entities(Player.full_name).all()
        }
        existing_player_ids = {
            p.player_id
            for p in Player.query.with_entities(Player.player_id).all()
        }
        print(f'  Database has {len(existing_names):,} players already.')

        print('\n[1/2] Loading Chadwick databank…')
        people, phi = load_chadwick(databank_path)

        print('\n[2/2] Finding new players not already in database…')
        new_records = []
        skipped = 0

        for lahman_id, data in phi.items():
            person = people.get(lahman_id)
            if not person:
                continue

            first = person.get('nameFirst', '').strip()
            last  = person.get('nameLast', '').strip()
            full  = f'{first} {last}'.strip()
            if not full:
                continue

            # Skip if already present (by name or Lahman ID stored as player_id)
            if full.lower() in existing_names:
                skipped += 1
                continue
            if lahman_id in existing_player_ids:
                skipped += 1
                continue

            years      = sorted(set(data['years']))
            year_start = years[0]
            year_end   = years[-1]
            years_str  = (str(year_start) if year_start == year_end
                          else f'{year_start}–{year_end}')

            new_records.append(Player(
                player_id=lahman_id,
                full_name=full,
                position=primary_position(dict(data['pos'])),
                year_start=year_start,
                year_end=year_end,
                years_active=years_str,
                mlb_id=None,
                photo_url=None,
                collection_status="Don't Have",
            ))

        print(f'  {skipped:,} already in database — skipped.')
        print(f'  {len(new_records):,} new players to add.')

        if new_records:
            db.session.bulk_save_objects(new_records)
            db.session.commit()
            print(f'\n✓ Added {len(new_records):,} historical Phillies players.')
        else:
            print('\n✓ No new players to add — database is already complete!')

        total = Player.query.count()
        print(f'  Total players in database: {total:,}\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Supplement Phillies DB with Chadwick/Lahman historical data.'
    )
    parser.add_argument(
        'databank_path',
        help='Path to extracted Chadwick databank folder OR the .zip file itself'
    )
    args = parser.parse_args()

    if not os.path.exists(args.databank_path):
        print(f'ERROR: path not found: {args.databank_path}')
        sys.exit(1)

    supplement(args.databank_path)
