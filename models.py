from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

VALID_STATUSES = ('Have', 'Have Signed', "Don't Have", 'No Auto Available', 'In Person')


class Player(db.Model):
    """MLB players — all Phillies 1883-present."""
    __tablename__ = 'players'

    id             = db.Column(db.Integer, primary_key=True)
    player_id      = db.Column(db.String(20), unique=True, nullable=False)  # Lahman playerID
    full_name      = db.Column(db.String(100), nullable=False)
    position       = db.Column(db.String(20))
    year_start     = db.Column(db.Integer)
    year_end       = db.Column(db.Integer)
    years_active   = db.Column(db.String(50))   # e.g. "1972–1985"
    mlb_id         = db.Column(db.Integer)       # MLBAM ID for photo URLs
    birth_date     = db.Column(db.Date, nullable=True)   # for deduplication
    photo_url      = db.Column(db.String(300))
    collection_status = db.Column(db.String(20), nullable=False, default="Don't Have")
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at     = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id':               self.id,
            'player_id':        self.player_id,
            'full_name':        self.full_name,
            'position':         self.position,
            'year_start':       self.year_start,
            'year_end':         self.year_end,
            'years_active':     self.years_active,
            'mlb_id':           self.mlb_id,
            'photo_url':        self.photo_url,
            'collection_status': self.collection_status,
        }


class Affiliate(db.Model):
    """Historical and current Phillies minor league affiliate teams."""
    __tablename__ = 'affiliates'

    id            = db.Column(db.Integer, primary_key=True)
    mlb_team_id   = db.Column(db.Integer, nullable=True)   # MLB Stats API team ID
    team_name     = db.Column(db.String(100), nullable=False)
    level         = db.Column(db.String(30), nullable=False)  # Triple-A, Double-A, etc.
    league        = db.Column(db.String(100), nullable=True)
    location      = db.Column(db.String(100), nullable=True)
    year_start    = db.Column(db.Integer, nullable=False)
    year_end      = db.Column(db.Integer, nullable=True)   # None = current

    def to_dict(self):
        return {
            'id':           self.id,
            'mlb_team_id':  self.mlb_team_id,
            'team_name':    self.team_name,
            'level':        self.level,
            'league':       self.league or '',
            'location':     self.location or '',
            'year_start':   self.year_start,
            'year_end':     self.year_end,
        }


class MinorPlayer(db.Model):
    """
    Phillies minor league players (2005-present via MLB Stats API).

    data_source field supports multiple importers:
      'mlbstats_api'  — MLB Stats API (primary)
      'baseball_cube' — Baseball Cube (future, see importers/baseball_cube_stub.py)
    """
    __tablename__ = 'minor_players'

    id               = db.Column(db.Integer, primary_key=True)
    mlb_id           = db.Column(db.Integer, nullable=True, index=True)
    full_name        = db.Column(db.String(100), nullable=False)
    position         = db.Column(db.String(20), nullable=True)
    birth_date       = db.Column(db.Date, nullable=True)
    year_start       = db.Column(db.Integer, nullable=True)
    year_end         = db.Column(db.Integer, nullable=True)
    affiliate_id     = db.Column(db.Integer, db.ForeignKey('affiliates.id'), nullable=True)
    affiliate_name   = db.Column(db.String(100), nullable=True)   # denormalised for speed
    level            = db.Column(db.String(30), nullable=True)
    photo_url        = db.Column(db.String(300), nullable=True)
    collection_status = db.Column(db.String(20), nullable=False, default="Don't Have")
    data_source      = db.Column(db.String(50), nullable=False, default='mlbstats_api')
    is_mlb_duplicate = db.Column(db.Boolean, nullable=False, default=False)
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at       = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        if self.year_start and self.year_end and self.year_start != self.year_end:
            years_active = f"{self.year_start}\u2013{self.year_end}"
        else:
            years_active = str(self.year_start or '')
        return {
            'id':               self.id,
            'mlb_id':           self.mlb_id,
            'full_name':        self.full_name,
            'position':         self.position or '',
            'birth_date':       self.birth_date.isoformat() if self.birth_date else None,
            'year_start':       self.year_start,
            'year_end':         self.year_end,
            'years_active':     years_active,
            'affiliate_name':   self.affiliate_name or '',
            'level':            self.level or '',
            'photo_url':        self.photo_url or '',
            'collection_status': self.collection_status,
            'data_source':      self.data_source,
        }
