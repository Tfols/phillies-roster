import os
from datetime import timedelta
from functools import wraps

from flask import (Flask, jsonify, redirect, render_template,
                   request, session, url_for)
from models import Player, Affiliate, MinorPlayer, db, VALID_STATUSES

app = Flask(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────
_db_url = os.environ.get('DATABASE_URL', 'postgresql://localhost/phillies')
if _db_url.startswith('postgres://'):
    _db_url = _db_url.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI']  = _db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-change-me')
app.permanent_session_lifetime = timedelta(days=30)

APP_PASSWORD = os.environ.get('APP_PASSWORD', '')

db.init_app(app)


# ── Auth ──────────────────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        if request.form.get('password') == APP_PASSWORD:
            session.permanent = True
            session['logged_in'] = True
            return redirect(url_for('index'))
        error = 'Incorrect password. Please try again.'
    return render_template('login.html', error=error)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# ── Pages ──────────────────────────────────────────────────────────────────────
@app.route('/')
@login_required
def index():
    return render_template('roster.html')


# ── MLB API ───────────────────────────────────────────────────────────────────
@app.route('/api/players')
@login_required
def get_players():
    players = Player.query.order_by(Player.full_name).all()
    return jsonify([p.to_dict() for p in players])


@app.route('/api/players/<int:player_id>/status', methods=['PATCH'])
@login_required
def update_status(player_id):
    player = Player.query.get_or_404(player_id)
    data   = request.get_json(silent=True) or {}
    status = data.get('status', '')
    if status not in VALID_STATUSES:
        return jsonify({'error': 'Invalid status'}), 400
    player.collection_status = status
    db.session.commit()
    return jsonify(player.to_dict())


@app.route('/api/stats')
@login_required
def get_stats():
    total     = Player.query.count()
    have      = Player.query.filter_by(collection_status='Have').count()
    signed    = Player.query.filter_by(collection_status='Have Signed').count()
    dont      = Player.query.filter_by(collection_status="Don't Have").count()
    no_auto   = Player.query.filter_by(collection_status='No Auto Available').count()
    in_person = Player.query.filter_by(collection_status='In Person').count()
    return jsonify({'total': total, 'have': have, 'signed': signed,
                    'dont_have': dont, 'no_auto': no_auto, 'in_person': in_person})


# ── Minor League API ──────────────────────────────────────────────────────────
@app.route('/api/minors')
@login_required
def get_minors():
    players = (MinorPlayer.query
               .filter_by(is_mlb_duplicate=False)
               .order_by(MinorPlayer.full_name)
               .all())
    return jsonify([p.to_dict() for p in players])


@app.route('/api/minors/<int:player_id>/status', methods=['PATCH'])
@login_required
def update_minor_status(player_id):
    player = MinorPlayer.query.get_or_404(player_id)
    data   = request.get_json(silent=True) or {}
    status = data.get('status', '')
    if status not in VALID_STATUSES:
        return jsonify({'error': 'Invalid status'}), 400
    player.collection_status = status
    db.session.commit()
    return jsonify(player.to_dict())


@app.route('/api/minors/stats')
@login_required
def get_minor_stats():
    base      = MinorPlayer.query.filter_by(is_mlb_duplicate=False)
    total     = base.count()
    have      = base.filter_by(collection_status='Have').count()
    signed    = base.filter_by(collection_status='Have Signed').count()
    dont      = base.filter_by(collection_status="Don't Have").count()
    no_auto   = base.filter_by(collection_status='No Auto Available').count()
    in_person = base.filter_by(collection_status='In Person').count()
    return jsonify({'total': total, 'have': have, 'signed': signed,
                    'dont_have': dont, 'no_auto': no_auto, 'in_person': in_person})


@app.route('/api/affiliates')
@login_required
def get_affiliates():
    affs = Affiliate.query.order_by(Affiliate.team_name).all()
    return jsonify([a.to_dict() for a in affs])


# ── Bootstrap: create any missing tables on first request ─────────────────────
_db_ready = False


@app.before_request
def _init_db():
    global _db_ready
    if not _db_ready:
        db.create_all()   # creates any missing tables (Affiliate, MinorPlayer)
        _db_ready = True


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
