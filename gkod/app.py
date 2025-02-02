# app.py
from flask import Flask, request, jsonify, render_template
from flask_socketio import SocketIO, emit, disconnect
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import uuid
import jwt
import datetime
import logging
import os
import ssl
from functools import wraps

# Logging ayarları
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/remotecontrol/server.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-here')
CORS(app, resources={r"/*": {"origins": "*"}})
socketio = SocketIO(app, cors_allowed_origins="*", ping_timeout=60)
limiter = Limiter(app=app, key_func=get_remote_address)

class Database:
    def __init__(self):
        self.db_path = '/var/lib/remotecontrol/database.db'
        try:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            self.init_db()
        except Exception as e:
            logger.error(f"Database initialization error: {e}")
            raise

    def init_db(self):
        try:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()

                # Users table
                c.execute('''CREATE TABLE IF NOT EXISTS users
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    api_key TEXT UNIQUE NOT NULL,
                    last_login TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

                # Clients table with expanded fields
                c.execute('''CREATE TABLE IF NOT EXISTS clients
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_id TEXT UNIQUE NOT NULL,
                    user_id INTEGER,
                    name TEXT,
                    system_info TEXT,
                    last_seen TIMESTAMP,
                    status TEXT,
                    api_key TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users (id))''')

                # Command logs table with expanded tracking
                c.execute('''CREATE TABLE IF NOT EXISTS command_logs
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    client_id TEXT,
                    command TEXT,
                    parameters TEXT,
                    status TEXT,
                    response TEXT,
                    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id))''')

                conn.commit()
        except Exception as e:
            logger.error(f"Error creating tables: {e}")
            raise

    def create_user(self, username, password):
        try:
            api_key = str(uuid.uuid4())
            hashed_password = generate_password_hash(password)

            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                c.execute('''INSERT INTO users
                    (username, password, api_key, created_at)
                    VALUES (?, ?, ?, ?)''',
                    (username, hashed_password, api_key, datetime.datetime.now()))
                conn.commit()
                return api_key
        except sqlite3.IntegrityError:
            logger.warning(f"User creation failed: Username {username} already exists")
            return None
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            return None

    def verify_user(self, username, password):
        try:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                c.execute('''SELECT id, password, api_key FROM users
                    WHERE username = ?''', (username,))
                user = c.fetchone()

                if user and check_password_hash(user[1], password):
                    # Update last login
                    c.execute('''UPDATE users SET last_login = ?
                        WHERE id = ?''', (datetime.datetime.now(), user[0]))
                    conn.commit()
                    return (user[0], user[2])
                return None
        except Exception as e:
            logger.error(f"Error verifying user: {e}")
            return None

    def get_user_by_api_key(self, api_key):
        try:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                c.execute('SELECT id, username FROM users WHERE api_key = ?', (api_key,))
                return c.fetchone()
        except Exception as e:
            logger.error(f"Error getting user by API key: {e}")
            return None

    def register_client(self, client_id, user_id, api_key, system_info=None):
        try:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                c.execute('''INSERT OR REPLACE INTO clients
                    (client_id, user_id, system_info, last_seen, status, api_key)
                    VALUES (?, ?, ?, ?, ?, ?)''',
                    (client_id, user_id, system_info, datetime.datetime.now(), 'active', api_key))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error registering client: {e}")
            return False

    def update_client_status(self, client_id, status, system_info=None):
        try:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                if system_info:
                    c.execute('''UPDATE clients SET status = ?, last_seen = ?, system_info = ?
                        WHERE client_id = ?''',
                        (status, datetime.datetime.now(), system_info, client_id))
                else:
                    c.execute('''UPDATE clients SET status = ?, last_seen = ?
                        WHERE client_id = ?''',
                        (status, datetime.datetime.now(), client_id))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error updating client status: {e}")
            return False

    def log_command(self, user_id, client_id, command, parameters=None, status='sent'):
        try:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                c.execute('''INSERT INTO command_logs
                    (user_id, client_id, command, parameters, status, executed_at)
                    VALUES (?, ?, ?, ?, ?, ?)''',
                    (user_id, client_id, command, parameters, status, datetime.datetime.now()))
                conn.commit()
                return c.lastrowid
        except Exception as e:
            logger.error(f"Error logging command: {e}")
            return None

    def update_command_status(self, command_id, status, response=None):
        try:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                c.execute('''UPDATE command_logs SET status = ?, response = ?, completed_at = ?
                    WHERE id = ?''',
                    (status, response, datetime.datetime.now(), command_id))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error updating command status: {e}")
            return False

db = Database()

def create_token(user_id, api_key):
    payload = {
        'user_id': user_id,
        'api_key': api_key,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=1)
    }
    return jwt.encode(payload, app.config['SECRET_KEY'], algorithm='HS256')

def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-KEY')
        if not api_key:
            return jsonify({'status': 'error', 'message': 'API key required'}), 401

        user = db.get_user_by_api_key(api_key)
        if not user:
            return jsonify({'status': 'error', 'message': 'Invalid API key'}), 401

        return f(*args, **kwargs)
    return decorated_function

# Connected clients dictionary with expanded info
connected_clients = {}

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
        return jsonify({
            'status': 'error',
            'message': 'Username and password are required'
        }), 400

    api_key = db.create_user(username, password)
    if api_key:
        return jsonify({
            'status': 'success',
            'message': 'User created successfully',
            'api_key': api_key
        })
    return jsonify({
        'status': 'error',
        'message': 'Username already exists'
    }), 400

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
            'message': 'Login successful',
            'token': token,
            'api_key': user[1]
        })
    return jsonify({
        'status': 'error',
        'message': 'Invalid username or password'
    }), 401

@app.route('/clients', methods=['GET'])
@require_api_key
def get_clients():
    api_key = request.headers.get('X-API-KEY')
    user = db.get_user_by_api_key(api_key)

    if not user:
        return jsonify({
            'status': 'error',
            'message': 'Invalid API key'
        }), 401

    user_clients = {
        k: v for k, v in connected_clients.items()
        if v.get('user_id') == user[0]
    }

    return jsonify({
        'status': 'success',
        'clients': [
            {
                'client_id': k,
                'status': v.get('status', 'unknown'),
                'last_seen': v.get('last_seen', ''),
                'system_info': v.get('system_info', {})
            }
            for k, v in user_clients.items()
        ]
    })

@app.route('/send-command', methods=['POST'])
@require_api_key
def send_command():
    data = request.json
    client_id = data.get('client_id')
    command = data.get('command')
    parameters = data.get('parameters', {})
    api_key = request.headers.get('X-API-KEY')
    user = db.get_user_by_api_key(api_key)

    if not client_id or not command:
        return jsonify({
            'status': 'error',
            'message': 'Client ID and command are required'
        }), 400

    if client_id not in connected_clients:
        return jsonify({
            'status': 'error',
            'message': 'Client not found'
        }), 404

    if connected_clients[client_id].get('user_id') != user[0]:
        return jsonify({
            'status': 'error',
            'message': 'Access denied for this client'
        }), 403

    command_id = db.log_command(user[0], client_id, command, str(parameters))

    socketio.emit('execute_command', {
        'command': command,
        'parameters': parameters,
        'command_id': command_id,
        'timestamp': datetime.datetime.now().isoformat()
    }, room=client_id)

    return jsonify({
        'status': 'success',
        'message': 'Command sent successfully',
        'command_id': command_id
    })

@socketio.on('connect')
def handle_connect():
    client_id = request.args.get('client_id')
    api_key = request.args.get('api_key')

    if not client_id or not api_key:
        disconnect()
        return False

    user = db.get_user_by_api_key(api_key)
    if not user:
        disconnect()
        return False

    connected_clients[client_id] = {
        'sid': request.sid,
        'user_id': user[0],
        'status': 'active',
        'last_seen': datetime.datetime.now().isoformat(),
        'connected_at': datetime.datetime.now().isoformat()
    }

    db.register_client(client_id, user[0], api_key)
    logger.info(f'Client connected: {client_id}')
    return True

@socketio.on('disconnect')
def handle_disconnect():
    client_id = None
    for cid, data in connected_clients.items():
        if data.get('sid') == request.sid:
            client_id = cid
            break

    if client_id:
        db.update_client_status(client_id, 'inactive')
        del connected_clients[client_id]
        logger.info(f'Client disconnected: {client_id}')

@socketio.on('heartbeat')
def handle_heartbeat(data):
    client_id = None
    for cid, cdata in connected_clients.items():
        if cdata.get('sid') == request.sid:
            client_id = cid
            break

    if client_id:
        connected_clients[client_id]['last_seen'] = datetime.datetime.now().isoformat()
        connected_clients[client_id]['status'] = 'active'
        if 'system_info' in data:
            connected_clients[client_id]['system_info'] = data['system_info']
            db.update_client_status(client_id, 'active', str(data['system_info']))
        else:
            db.update_client_status(client_id, 'active')

@socketio.on('command_result')
def handle_command_result(data):
    client_id = None
    for cid, cdata in connected_clients.items():
        if cdata.get('sid') == request.sid:
            client_id = cid
            break

    if client_id and 'command_id' in data:
        status = 'completed' if data.get('success', False) else 'failed'
        db.update_command_status(
            data['command_id'],
            status,
            str(data.get('result', ''))
        )

@app.errorhandler(Exception)
def handle_error(error):
    message = str(error)
    logger.error(f"An error occurred: {message}")
    return jsonify({'status': 'error', 'message': message}), 500

if __name__ == '__main__':
    # CentOS için SSL sertifika yolları
    cert_path = '/etc/ssl/certs/server.crt'
    key_path = '/etc/ssl/private/server.key'

    # SSL context oluşturma
    if os.path.exists(cert_path) and os.path.exists(key_path):
        ssl_context = (cert_path, key_path)
    else:
        ssl_context = None
        logger.warning("SSL certificates not found, running without SSL")

    # Production için Gunicorn ile çalıştırma
    if os.environ.get('PRODUCTION', False):
        socketio.run(app,
                     host='0.0.0.0',
                     port=int(os.environ.get('PORT', 5000)),
                     debug=False,
                     ssl_context=ssl_context,
                     keyfile=key_path,
                     certfile=cert_path)
    else:
        # Development için
        socketio.run(app,
                     host='0.0.0.0',
                     port=5000,
                     debug=True)