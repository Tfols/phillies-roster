"""
Railway release-phase script: creates/verifies database tables.
Runs before each new deployment goes live.
"""
import os
from flask import Flask
from models import db

app = Flask(__name__)

_db_url = os.environ.get('DATABASE_URL', '')
if _db_url.startswith('postgres://'):
    _db_url = _db_url.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = _db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

with app.app_context():
    db.create_all()
    print('✓ Database tables created / verified.')
