from flask import Flask, render_template, send_from_directory, redirect, url_for, request, session, flash
import io, sys, os, sqlite3
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

# Exemple de simulations
from exemple_btx import exemple_btx_complet, etude_parametrique_reflux

# -----------------------
# Configuration Flask
# -----------------------
app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'change_this_secret_for_prod')

# Dossiers et DB
OUTPUT_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(OUTPUT_DIR, 'users.db')

# -----------------------
# Gestion Base de données
# -----------------------
def init_db():
    """Créer la table utilisateurs si absente"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            is_admin INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()


def get_user(username):
    """Retourne un dictionnaire utilisateur ou None"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT username, password_hash, is_admin FROM users WHERE username=?', (username,))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    return {'username': row[0], 'password_hash': row[1], 'is_admin': bool(row[2])}


def add_user(username, password_hash, is_admin=False):
    """Ajoute un utilisateur, retourne False si existe déjà"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute('INSERT INTO users (username, password_hash, is_admin) VALUES (?,?,?)',
                  (username, password_hash, int(bool(is_admin))))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return False
    conn.close()
    return True


def list_users():
    """Liste tous les utilisateurs"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT username, is_admin FROM users')
    rows = c.fetchall()
    conn.close()
    return [{'username': r[0], 'is_admin': bool(r[1])} for r in rows]


def set_admin(username, is_admin):
    """Change le statut admin d'un utilisateur"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('UPDATE users SET is_admin=? WHERE username=?', (int(bool(is_admin)), username))
    conn.commit()
    conn.close()


def ensure_default_admin():
    """Crée un admin par défaut si la table est vide"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM users')
    n = c.fetchone()[0]
    conn.close()
    if n == 0:
        add_user('admin', generate_password_hash('admin'), is_admin=True)
        print('Default admin created: admin / admin (change password)')


# -----------------------
# Routes principales
# -----------------------
@app.route('/')
def index():
    """Page principale"""
    sandbox = session.get('sandbox', 'allow-scripts')
    username = session.get('username')
    return render_template('index.html', sandbox=sandbox, username=username)


@app.route('/register', methods=['GET', 'POST'])
def register():
    """Inscription utilisateur"""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if get_user(username):
            return render_template('register.html', error='Utilisateur déjà existant')
        add_user(username, generate_password_hash(password))
        session['username'] = username
        return redirect(url_for('index'))
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Connexion utilisateur"""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        u = get_user(username)
        if not u or not check_password_hash(u['password_hash'], password):
            return render_template('login.html', error='Identifiants invalides')
        session['username'] = username
        return redirect(url_for('index'))
    return render_template('login.html')


@app.route('/logout')
def logout():
    """Déconnexion"""
    session.pop('username', None)
    return redirect(url_for('index'))


# -----------------------
# Administration
# -----------------------
def admin_required(func):
    """Décorateur pour vérifier l'accès admin"""
    def wrapper(*args, **kwargs):
        username = session.get('username')
        u = get_user(username) if username else None
        if not u or not u.get('is_admin'):
            return "Access denied", 403
        return func(*args, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper


@app.route('/admin', methods=['GET'])
@admin_required
def admin():
    """Page admin: utilisateurs et fichiers générés"""
    files = []
    for entry in os.listdir(OUTPUT_DIR):
        if entry.lower().endswith(('.png', '.html')):
            st = os.stat(os.path.join(OUTPUT_DIR, entry))
            files.append({'name': entry, 'size': st.st_size, 'mtime': st.st_mtime})
    users = list_users()
    return render_template('admin.html', files=files, users=users)


@app.route('/admin/delete', methods=['POST'])
@admin_required
def admin_delete():
    """Supprime un fichier généré"""
    fname = request.form.get('filename')
    if fname:
        path = os.path.join(OUTPUT_DIR, fname)
        if os.path.exists(path):
            try:
                os.remove(path)
                flash(f'{fname} supprimé')
            except Exception as e:
                flash(str(e))
    return redirect(url_for('admin'))


@app.route('/admin/toggle_admin', methods=['POST'])
@admin_required
def admin_toggle():
    """Basculer l'état admin d'un utilisateur"""
    target = request.form.get('target')
    if target:
        user = get_user(target)
        if user:
            new_admin = not user['is_admin']
            set_admin(target, new_admin)
            flash(f"{target} admin={new_admin}")
        else:
            flash('Utilisateur introuvable')
    return redirect(url_for('admin'))


# -----------------------
# Exécution simulations
# -----------------------
@app.route('/run')
def run():
    """Exécute les exemples BTX et capture stdout"""
    if 'username' not in session:
        return redirect(url_for('login'))

    # sandbox mode
    sandbox_mode = request.args.get('sandbox') or session.get('sandbox', 'allow-scripts')
    session['sandbox'] = sandbox_mode

    buf = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = buf

    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        plt_show_backup = plt.show
        plt.show = lambda *a, **k: None
    except Exception:
        plt_show_backup = None

    try:
        results, thermo, visualizer = exemple_btx_complet()
        try:
            etude_parametrique_reflux()
        except Exception as e:
            print(f"Reflux study error: {e}")
    except Exception as e:
        print(f"Simulation error: {e}")
    finally:
        sys.stdout = old_stdout
        if plt_show_backup:
            try:
                import matplotlib.pyplot as plt
                plt.show = plt_show_backup
            except Exception:
                pass

    output = buf.getvalue()

    # Fichiers générés
    files = {}
    candidates = [
        'btx_bilan_matiere.png',
        'btx_shortcut_results.png',
        'btx_composition_profiles.png',
        'btx_temperature_profile.png',
        'btx_etude_reflux.png',
        'composition_profiles_interactive.html'
    ]
    for name in candidates:
        path = os.path.join(OUTPUT_DIR, name)
        if os.path.exists(path):
            files[name] = url_for('static_file', filename=name)

    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    username = session.get('username')
    return render_template('results.html', output=output, files=files, ts=ts, sandbox_mode=sandbox_mode, username=username)


@app.route('/files/<path:filename>')
def static_file(filename):
    """Servir fichiers statiques générés"""
    return send_from_directory(OUTPUT_DIR, filename)


# -----------------------
# Lancement
# -----------------------
if __name__ == '__main__':
    try:
        init_db()
        ensure_default_admin()
    except Exception as e:
        print('DB init error:', e)
    app.run(host='127.0.0.1', port=5000, debug=True)
