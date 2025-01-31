from functools import wraps
from flask import request, jsonify
from database import Database

db = Database()

def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get("X-API-KEY")
        if not api_key:
            return jsonify({"status": "error", "message": "API anahtarı gerekli"}), 401

        user = db.verify_api_key(api_key)
        if not user:
            return jsonify({"status": "error", "message": "Geçersiz API anahtarı"}), 403

        # İsteğe kullanıcı bilgisini ekle
        request.user_id = user[0]
        request.username = user[1]
        return f(*args, **kwargs)
    return decorated_function
    