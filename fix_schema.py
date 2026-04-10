"""
fix_schema.py — Comprehensive schema migration.

Adds any columns that exist in the SQLAlchemy Player model but are missing
from the production `players` table.  Safe to run multiple times.

Also creates the new `affiliates` and `minor_players` tables if absent.

Run locally with the public DATABASE_URL:
    $env:DATABASE_URL="postgresql://postgres:<pw>@maglev.proxy.rlwy.net:<port>/railway"
    python fix_schema.py
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask
from models import db

# ── App setup ──────────────────────────────────────────────────────────────────
_db_url = os.environ.get('DATABASE_URL', '')
if not _db_url:
    print('ERROR: DATABASE_URL not set.')
    sys.exit(1)
if _db_url.startswith('postgres://'):
    _db_url = _db_url.replace('postgres://', 'postgresql://', 1)

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = _db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

# All columns the Player model expects, and their SQL types if missing
REQUIRED_PLAYER_COLUMNS = [
    ('birth_date',  'DATE'),
    ('created_at',  'TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()'),
    ('updated_at',  'TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()'),
]


def main():
    with app.app_context():
        conn = db.engine.connect()

        # ── 1. Check if players table exists ──────────────────────────────────
        result = conn.execute(db.text(
            "SELECT to_regclass('public.players')"
        ))
        table_exists = result.scalar() is not None

        if not table_exists:
            print('players table does not exist — will be created by db.create_all().')
        else:
            count = conn.execute(db.text('SELECT COUNT(*) FROM players')).scalar()
            print(f'players table exists with {count:,} rows.')

            # ── 2. Add any missing columns ────────────────────────────────────
            existing_cols_result = conn.execute(db.text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'players'
            """))
            existing_cols = {row[0] for row in existing_cols_result}
            print(f'  Existing columns: {sorted(existing_cols)}')

            added = []
            for col_name, col_type in REQUIRED_PLAYER_COLUMNS:
                if col_name not in existing_cols:
                    print(f'  Adding missing column: {col_name} ({col_type.split()[0]})')
                    conn.execute(db.text(
                        f'ALTER TABLE players ADD COLUMN {col_name} {col_type}'
                    ))
                    added.append(col_name)
                else:
                    print(f'  ✓ {col_name} already exists')

            if added:
                conn.commit()
                print(f'  Added columns: {added}')
            else:
                print('  No columns needed adding.')

        conn.close()

        # ── 3. Create any missing tables ──────────────────────────────────────
        print('\nCreating any missing tables (affiliates, minor_players)...')
        db.create_all()
        print('  ✓ All tables created / verified.')

        # ── 4. Final report ───────────────────────────────────────────────────
        with db.engine.connect() as c:
            p = c.execute(db.text('SELECT COUNT(*) FROM players')).scalar()
            a = c.execute(db.text('SELECT COUNT(*) FROM affiliates')).scalar()
            m = c.execute(db.text('SELECT COUNT(*) FROM minor_players')).scalar()
        print('\nCurrent row counts:')
        print(f'  players      : {p:,}')
        print(f'  affiliates   : {a:,}')
        print(f'  minor_players: {m:,}')

        if p == 0:
            print('\n⚠️  players table is EMPTY — run import_data.py to re-import.')
        else:
            print('\n✓ Schema fix complete.')
            print('  Next steps:')
            print('  1. python backfill_dob.py   (fills birth dates — ~15 min)')
            print('  2. python import_minors.py  (imports minor league data)')


if __name__ == '__main__':
    main()
