# app.py
from flask import Flask, request, jsonify, render_template
from flask_socketio import SocketIO, emit, disconnect
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import sqlite3
import uuid
import hashlib
import jwt
import datetime
import logging
from functools import wraps
import logging

# Logging ayarları
logging.basicConfig(level=logging.DEBUG)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('server.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'  # Değiştirin
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")
limiter = Limiter(app=app, key_func=get_remote_address)

# Veritabanı sınıfı
class Database:
    def __init__(self):
        try:
            self.init_db()
        except Exception as e:
            print(f"Database initialization error: {e}")
            logging.error(f"Database initialization error: {e}")

    def init_db(self):
        try:
            with sqlite3.connect('database.db') as conn:
                c = conn.cursor()
                # Users table
                c.execute('''CREATE TABLE IF NOT EXISTS users
(id INTEGER PRIMARY KEY AUTOINCREMENT,
username TEXT UNIQUE NOT NULL,
password TEXT NOT NULL,
api_key TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

                # Clients table
                c.execute('''CREATE TABLE IF NOT EXISTS clients
(id INTEGER PRIMARY KEY AUTOINCREMENT,
client_id TEXT UNIQUE NOT NULL,
user_id INTEGER,
name TEXT,
last_seen TIMESTAMP,
status TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id))''')

                # Command logs table
                c.execute('''CREATE TABLE IF NOT EXISTS command_logs
(id INTEGER PRIMARY KEY AUTOINCREMENT,
user_id INTEGER,
client_id TEXT,
command TEXT,
status TEXT,
executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id))''')

                conn.commit()
        except Exception as e:
            print(f"Error creating tables: {e}")
            logging.error(f"Error creating tables: {e}")
            raise

    def create_user(self, username, password):
        try:
            api_key = str(uuid.uuid4())
            hashed_password = hashlib.sha256(password.encode()).hexdigest()

            with sqlite3.connect('database.db') as conn:
                c = conn.cursor()
                c.execute('INSERT INTO users (username, password, api_key) VALUES (?, ?, ?)',
                          (username, hashed_password, api_key))
                conn.commit()
                return api_key
        except sqlite3.IntegrityError:
            return None
        except Exception as e:
            print(f"Error creating user: {e}")
            logging.error(f"Error creating user: {e}")
            return None

    def verify_user(self, username, password):
        try:
            hashed_password = hashlib.sha256(password.encode()).hexdigest()
            with sqlite3.connect('database.db') as conn:
                c = conn.cursor()
                c.execute('SELECT id, api_key FROM users WHERE username = ? AND password = ?',
                          (username, hashed_password))
                return c.fetchone()
        except Exception as e:
            print(f"Error verifying user: {e}")
            logging.error(f"Error verifying user: {e}")
            return None

    def get_user_by_api_key(self, api_key):
        try:
            with sqlite3.connect('database.db') as conn:
                c = conn.cursor()
                c.execute('SELECT id, username FROM users WHERE api_key = ?', (api_key,))
                return c.fetchone()
        except Exception as e:
            print(f"Error getting user by API key: {e}")
            logging.error(f"Error getting user by API key: {e}")
            return None

    def create_user(self, username, password):
        api_key = str(uuid.uuid4())
        hashed_password = hashlib.sha256(password.encode()).hexdigest()

        try:
            with sqlite3.connect('database.db') as conn:
                c = conn.cursor()
                c.execute('INSERT INTO users (username, password, api_key) VALUES (?, ?, ?)',
                          (username, hashed_password, api_key))
                conn.commit()
                return api_key
        except sqlite3.IntegrityError:
            return None

    def verify_user(self, username, password):
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        with sqlite3.connect('database.db') as conn:
            c = conn.cursor()
            c.execute('SELECT id, api_key FROM users WHERE username = ? AND password = ?',
                      (username, hashed_password))
            result = c.fetchone()
            return result if result else None

    def get_user_by_api_key(self, api_key):
        with sqlite3.connect('database.db') as conn:
            c = conn.cursor()
            c.execute('SELECT id, username FROM users WHERE api_key = ?', (api_key,))
            return c.fetchone()

    def log_command(self, user_id, client_id, command, status):
        with sqlite3.connect('database.db') as conn:
            c = conn.cursor()
            c.execute('''
INSERT INTO command_logs (user_id, client_id, command, status)
VALUES (?, ?, ?, ?)
                ''', (user_id, client_id, command, status))
            conn.commit()

db = Database()

# JWT token oluşturma
def create_token(user_id, api_key):
    payload = {
        'user_id': user_id,
        'api_key': api_key,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=1)
    }
    return jwt.encode(payload, app.config['SECRET_KEY'], algorithm='HS256')

# API key kontrolü için dekoratör
def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-KEY')
        if not api_key:
            return jsonify({'status': 'error', 'message': 'API key gerekli'}), 401

        user = db.get_user_by_api_key(api_key)
        if not user:
            return jsonify({'status': 'error', 'message': 'Geçersiz API key'}), 401

        return f(*args, **kwargs)
    return decorated_function

# Bağlı istemciler
connected_clients = {}

# Route'lar
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['POST'])
@limiter.limit("5 per minute")
def register():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'status': 'error', 'message': 'Kullanıcı adı ve şifre gerekli'}), 400

    api_key = db.create_user(username, password)
    if api_key:
        return jsonify({
            'status': 'success',
            'message': 'Kullanıcı oluşturuldu',
            'api_key': api_key
        })
    return jsonify({'status': 'error', 'message': 'Kullanıcı adı zaten kullanımda'}), 400

@app.route('/login', methods=['POST'])
@limiter.limit("5 per minute")
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    user = db.verify_user(username, password)
    if user:
        token = create_token(user[0], user[1])
        return jsonify({
            'status': 'success',
            'message': 'Giriş başarılı',
            'token': token,
            'api_key': user[1]
        })
    return jsonify({'status': 'error', 'message': 'Geçersiz kullanıcı adı veya şifre'}), 401

@app.route('/clients', methods=['GET'])
@require_api_key
def get_clients():
    api_key = request.headers.get('X-API-KEY')
    user = db.get_user_by_api_key(api_key)

    user_clients = {k: v for k, v in connected_clients.items() if v.get('user_id') == user[0]}
    return jsonify({
        'status': 'success',
        'clients': list(user_clients.keys())
    })

@app.route('/send-command', methods=['POST'])
@require_api_key
def send_command():
    data = request.json
    client_id = data.get('client_id')
    command = data.get('command')
    api_key = request.headers.get('X-API-KEY')
    user = db.get_user_by_api_key(api_key)

    if not client_id or not command:
        return jsonify({'status': 'error', 'message': 'Client ID ve komut gerekli'}), 400

    if client_id not in connected_clients:
        return jsonify({'status': 'error', 'message': 'İstemci bulunamadı'}), 404

    if connected_clients[client_id].get('user_id') != user[0]:
        return jsonify({'status': 'error', 'message': 'Bu istemciye erişim yetkiniz yok'}), 403

    socketio.emit('execute_command', {
        'command': command,
        'timestamp': datetime.datetime.now().isoformat()
    }, room=client_id)

    db.log_command(user[0], client_id, command, 'sent')
    return jsonify({'status': 'success', 'message': 'Komut gönderildi'})

@app.errorhandler(Exception)
def handle_error(error):
    message = str(error)
    logging.error(f"An error occurred: {message}")
    return jsonify({'status': 'error', 'message': message}), 500

# Socket.IO olayları
@socketio.on('connect')
def handle_connect():
    client_id = request.args.get('client_id')
    api_key = request.args.get('api_key')

    if not client_id or not api_key:
        disconnect()
        return

    user = db.get_user_by_api_key(api_key)
    if not user:
        disconnect()
        return

    connected_clients[client_id] = {
        'sid': request.sid,
        'user_id': user[0],
        'connected_at': datetime.datetime.now()
    }
    logger.info(f'İstemci bağlandı: {client_id}')

@socketio.on('disconnect')
def handle_disconnect():
    client_id = None
    for cid, data in connected_clients.items():
        if data.get('sid') == request.sid:
            client_id = cid
            break

    if client_id:
        del connected_clients[client_id]
        logger.info(f'İstemci ayrıldı: {client_id}')

@socketio.on('command_result')
def handle_command_result(data):
    client_id = None
    for cid, cdata in connected_clients.items():
        if cdata.get('sid') == request.sid:
            client_id = cid
            break

    if client_id:
        user_id = connected_clients[client_id].get('user_id')
        db.log_command(user_id, client_id, data.get('command'), data.get('success'))

if __name__ == '__main__':
    socketio.run(app, debug=False, host='0.0.0.0', port=5000)