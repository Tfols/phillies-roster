import os
from datetime import timedelta
from functools import wraps

from authlib.integrations.flask_client import OAuth
from flask import (Flask, jsonify, redirect, render_template,
                   request, session, url_for)
from werkzeug.middleware.proxy_fix import ProxyFix
from models import Player, MinorPlayer, db, VALID_STATUSES

app = Flask(__name__)

# Railway terminates TLS at its edge and forwards as plain HTTP — without
# ProxyFix, url_for(_external=True) builds http:// URLs, which Google
# rejects as a redirect_uri mismatch. ProxyFix reads X-Forwarded-Proto
# from the Railway proxy so generated URLs are correctly https://.
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# ── Configuration ─────────────────────────────────────────────────────────────
_db_url = os.environ.get('DATABASE_URL', 'postgresql://localhost/phillies')
if _db_url.startswith('postgres://'):
    _db_url = _db_url.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI']  = _db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-change-me')
app.permanent_session_lifetime = timedelta(days=30)

# Comma-separated list of Google emails allowed to sign in
ALLOWED_EMAILS = {
    e.strip().lower()
    for e in os.environ.get('ALLOWED_EMAILS', '').split(',')
    if e.strip()
}

# OAuth setup — Google
_google_client_id     = os.environ.get('GOOGLE_CLIENT_ID', '').strip()
_google_client_secret = os.environ.get('GOOGLE_CLIENT_SECRET', '').strip()

# Visible in Railway "Deploy logs" — confirms whether the var is being read.
print(
    f'[auth] GOOGLE_CLIENT_ID present={bool(_google_client_id)} '
    f'len={len(_google_client_id)} '
    f'tail={_google_client_id[-12:] if _google_client_id else "<empty>"}',
    flush=True,
)
print(
    f'[auth] GOOGLE_CLIENT_SECRET present={bool(_google_client_secret)} '
    f'len={len(_google_client_secret)}',
    flush=True,
)
print(
    f'[auth] ALLOWED_EMAILS count={len(ALLOWED_EMAILS)}',
    flush=True,
)

oauth = OAuth(app)
oauth.register(
    name='google',
    client_id=_google_client_id,
    client_secret=_google_client_secret,
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'},
)

db.init_app(app)


def asset_url(filename):
    static_path = os.path.join(app.static_folder, filename)
    try:
        version = int(os.path.getmtime(static_path))
    except OSError:
        version = 0
    return url_for('static', filename=filename, v=version)


@app.context_processor
def inject_asset_url():
    return {'asset_url': asset_url}


@app.after_request
def set_cache_headers(response):
    if request.endpoint == 'static':
        filename = (request.view_args or {}).get('filename', '')
        if filename.endswith(('.css', '.js', '.json')):
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
    return response


# ── Auth ──────────────────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_email'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


@app.route('/login')
def login():
    error = request.args.get('error')
    return render_template('login.html', error=error)


@app.route('/auth/google')
def auth_google():
    redirect_uri = url_for('auth_callback', _external=True)
    print(f'[auth] /auth/google redirect_uri={redirect_uri}', flush=True)
    # Inspect the configured client at request time
    client = oauth.google
    print(
        f'[auth] client.client_id present={bool(getattr(client, "client_id", None))} '
        f'tail={(getattr(client, "client_id", "") or "")[-12:]}',
        flush=True,
    )
    resp = client.authorize_redirect(redirect_uri)
    # resp is a flask redirect — Location header has the full Google URL
    print(f'[auth] redirect Location={resp.headers.get("Location", "<none>")}', flush=True)
    return resp


@app.route('/auth/callback')
def auth_callback():
    try:
        token = oauth.google.authorize_access_token()
    except Exception as e:
        return redirect(url_for('login', error=f'Sign-in failed: {e}'))

    userinfo = token.get('userinfo') or {}
    email = (userinfo.get('email') or '').lower()

    if not email or email not in ALLOWED_EMAILS:
        return redirect(url_for('login',
                                error='This Google account is not authorized.'))

    session.permanent = True
    session['user_email'] = email
    session['user_name']  = userinfo.get('name', '')
    return redirect(url_for('index'))


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


# ── Bootstrap: create any missing tables on first request ─────────────────────
_db_ready = False


@app.before_request
def _init_db():
    global _db_ready
    if not _db_ready:
        db.create_all()   # creates any missing tables (Affiliate, MinorPlayer)
        # Migrate players table: add birth_date column if it was missing from
        # the original schema (added in the minor-league feature update).
        try:
            with db.engine.connect() as conn:
                missing = conn.execute(db.text(
                    "SELECT 1 FROM information_schema.columns "
                    "WHERE table_name='players' AND column_name='birth_date'"
                )).fetchone() is None
                if missing:
                    conn.execute(db.text('ALTER TABLE players ADD COLUMN birth_date DATE'))
                    conn.commit()
                    print('Schema migration: added birth_date column to players.')
        except Exception as e:
            print(f'WARNING: birth_date migration failed (non-fatal): {e}')
        _db_ready = True


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
