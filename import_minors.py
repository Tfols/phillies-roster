"""
Phillies Minor League Data Import Orchestrator
==============================================

Steps:
  1. Seed affiliates from Wikipedia (if not already done)
  2. Import players from MLB Stats API (2005–present)
  3. Run deduplication against MLB players table

Usage:
  railway run python import_minors.py                   # full 2005–present import
  railway run python import_minors.py --year 2025       # single year
  railway run python import_minors.py --force           # re-import even if data exists
  railway run python import_minors.py --dedup-only      # skip import, just re-run dedup
"""

import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Player, Affiliate, MinorPlayer

START_YEAR   = 2005
CURRENT_YEAR = 2025


# ── Deduplication ─────────────────────────────────────────────────────────────

def run_dedup():
    """
    Mark minor players who already exist in the MLB players table.

    Match priority:
      1. mlb_id (most reliable — same player ID used by both importers)
      2. full_name + birth_date (catches pre-API players if DOB backfill ran)

    Side effect: if a matched minor player has a non-default collection_status
    and the MLB player is still "Don't Have", the status is carried over.
    """
    print('\nRunning deduplication...')
    minor_players = MinorPlayer.query.filter_by(is_mlb_duplicate=False).all()
    marked = carried = 0

    for mp in minor_players:
        mlb_player = None

        if mp.mlb_id:
            mlb_player = Player.query.filter_by(mlb_id=mp.mlb_id).first()

        if not mlb_player and mp.birth_date and mp.full_name:
            mlb_player = Player.query.filter_by(
                full_name=mp.full_name,
                birth_date=mp.birth_date,
            ).first()

        if mlb_player:
            mp.is_mlb_duplicate = True
            marked += 1
            if (mlb_player.collection_status == "Don't Have"
                    and mp.collection_status != "Don't Have"):
                mlb_player.collection_status = mp.collection_status
                carried += 1

    db.session.commit()
    print(f'Dedup complete: {marked} marked as MLB duplicates, '
          f'{carried} statuses carried over to MLB records.')


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Import Phillies minor league players')
    parser.add_argument('--year',       type=int,  help='Import only this year')
    parser.add_argument('--start-year', type=int,  help='Start year (default 2005)')
    parser.add_argument('--end-year',   type=int,  help='End year (default 2025)')
    parser.add_argument('--force',      action='store_true',
                        help='Re-import even if minor_players table already has data')
    parser.add_argument('--dedup-only', action='store_true',
                        help='Skip import, run dedup only')
    parser.add_argument('--reset',      action='store_true',
                        help='Wipe minor_players and bad affiliates, then re-import')
    args = parser.parse_args()

    start = args.year or args.start_year or START_YEAR
    end   = args.year or args.end_year   or CURRENT_YEAR

    with app.app_context():
        db.create_all()

        # ── Step 1: Affiliates ───────────────────────────────────────────────
        aff_count = Affiliate.query.count()
        if aff_count == 0:
            print('Seeding affiliates from Wikipedia...')
            try:
                from import_affiliates import scrape_affiliates
                records = scrape_affiliates()
                for aff in records:
                    db.session.add(Affiliate(
                        team_name  = aff['team_name'],
                        level      = aff['level'],
                        league     = aff.get('league'),
                        location   = aff.get('location'),
                        year_start = aff['year_start'],
                        year_end   = aff.get('year_end'),
                    ))
                db.session.commit()
                print(f'Seeded {len(records)} affiliates.')
            except Exception as e:
                print(f'WARNING: Affiliate seed failed: {e}')
        else:
            print(f'Affiliates already seeded ({aff_count} records).')

        if args.dedup_only:
            run_dedup()
            return

        # ── Reset: wipe bad data before re-import ────────────────────────────
        if args.reset:
            print('Resetting minor_players table...')
            MinorPlayer.query.delete()
            # Remove affiliates added by the bad import (no location = not from Wikipedia)
            bad_affs = Affiliate.query.filter(
                Affiliate.location.is_(None),
                Affiliate.mlb_team_id.isnot(None),
            ).count()
            Affiliate.query.filter(
                Affiliate.location.is_(None),
                Affiliate.mlb_team_id.isnot(None),
            ).delete()
            db.session.commit()
            print(f'  Cleared minor_players and {bad_affs} non-Wikipedia affiliates.')

        # ── Step 2: Player import ────────────────────────────────────────────
        existing = MinorPlayer.query.count()
        if existing > 0 and not args.reset and not args.force:
            print(f'\nMinor players table already has {existing} records.')
            print('Skipping import. Use --force to re-run, or --dedup-only to re-dedup.')
        else:
            if existing > 0 and args.force:
                print(f'Force mode: existing {existing} records will be updated/extended.')

            print(f'\nImporting minor league players ({start}–{end})...')
            from importers.mlbstats_minor import import_minors as mlb_import
            ins, upd, skp = mlb_import(
                app, db, Affiliate, MinorPlayer, Player,
                start_year=start, end_year=end,
            )
            print(f'Import result: {ins} inserted, {upd} updated, {skp} skipped')

        # ── Step 3: Dedup ────────────────────────────────────────────────────
        run_dedup()

        total = MinorPlayer.query.filter_by(is_mlb_duplicate=False).count()
        dups  = MinorPlayer.query.filter_by(is_mlb_duplicate=True).count()
        print(f'\nFinal minor league roster: {total} unique players ({dups} hidden as MLB duplicates)')


if __name__ == '__main__':
    main()
