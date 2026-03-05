"""
Backfill birth_date for all existing MLB players who have an mlb_id.

Run ONCE after deploying the updated models.py that adds the birth_date column.
Required for accurate deduplication against the minor league table.

Usage:
  railway run python backfill_dob.py

Estimated time: ~15-20 min for 2,209 players (0.5s/call)
"""

import sys
import os
import time

import requests
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Player

MLB_API = 'https://statsapi.mlb.com/api/v1'
DELAY   = 0.3   # seconds between requests — stay well clear of rate limits
BATCH   = 100   # commit every N players


def backfill():
    with app.app_context():
        players = (
            Player.query
            .filter(Player.mlb_id.isnot(None), Player.birth_date.is_(None))
            .all()
        )
        total   = len(players)
        updated = 0
        errors  = 0

        print(f'Backfilling DOB for {total} players...')

        for i, player in enumerate(players):
            if i % BATCH == 0 and i > 0:
                db.session.commit()
                print(f'  [{i}/{total}] committed — {updated} updated so far')

            try:
                r = requests.get(f'{MLB_API}/people/{player.mlb_id}', timeout=10)
                if r.status_code != 200:
                    errors += 1
                    continue
                people = r.json().get('people', [])
                if not people:
                    continue
                birth_str = people[0].get('birthDate')
                if birth_str:
                    player.birth_date = date.fromisoformat(birth_str[:10])
                    updated += 1
            except Exception as e:
                print(f'  Error for player {player.mlb_id} ({player.full_name}): {e}')
                errors += 1

            time.sleep(DELAY)

        db.session.commit()
        print(f'\nDone. Updated: {updated} | Errors: {errors} | Total processed: {total}')


if __name__ == '__main__':
    backfill()
