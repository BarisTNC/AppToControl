import sqlite3
import secrets
from datetime import datetime

class Database:
    def __init__(self, db_file="users.db"):
        self.db_file = db_file
        self.init_db()

    def init_db(self):
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            # Kullanıcılar tablosu
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    api_key TEXT UNIQUE NOT NULL,
                    created_at DATETIME NOT NULL,
                    last_login DATETIME
                )
            ''')
            # Kullanıcı logları tablosu
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    action TEXT NOT NULL,
                    timestamp DATETIME NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
            conn.commit()

    def create_user(self, username, password):
        api_key = secrets.token_urlsafe(32)
        try:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO users (username, password, api_key, created_at) VALUES (?, ?, ?, ?)",
                    (username, password, api_key, datetime.now())
                )
                conn.commit()
                return api_key
        except sqlite3.IntegrityError:
            return None

    def verify_api_key(self, api_key):
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, username FROM users WHERE api_key = ?", (api_key,))
            return cursor.fetchone()

    def get_user_api_key(self, username, password):
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT api_key FROM users WHERE username = ? AND password = ?", (username, password))
            result = cursor.fetchone()
            if result:
                # Son giriş zamanını güncelle
                cursor.execute("UPDATE users SET last_login = ? WHERE username = ?", (datetime.now(), username))
                conn.commit()
                return result[0]
            return None
