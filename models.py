from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class Player(db.Model):
    __tablename__ = 'players'

    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.String(20), unique=True, nullable=False)  # Lahman playerID
    full_name = db.Column(db.String(100), nullable=False)
    position = db.Column(db.String(20))
    year_start = db.Column(db.Integer)
    year_end = db.Column(db.Integer)
    years_active = db.Column(db.String(50))   # e.g. "1972–1985"
    mlb_id = db.Column(db.Integer)             # MLBAM ID for photo URLs
    photo_url = db.Column(db.String(300))
    collection_status = db.Column(db.String(20), nullable=False, default="Don't Have")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'player_id': self.player_id,
            'full_name': self.full_name,
            'position': self.position,
            'year_start': self.year_start,
            'year_end': self.year_end,
            'years_active': self.years_active,
            'photo_url': self.photo_url,
            'collection_status': self.collection_status,
        }
