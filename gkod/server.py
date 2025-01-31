from flask import Flask, request, jsonify, render_template
from flask_socketio import SocketIO, emit
from flask_cors import CORS
from database import Database
from auth import require_api_key
import logging

app = Flask(__name__)
db = Database()

# Yeni route'lar ekle
@app.route("/register", methods=["POST"])
def register():
    data = request.json
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"status": "error", "message": "Kullanıcı adı ve şifre gerekli"}), 400

    api_key = db.create_user(username, password)
    if api_key:
        return jsonify({
            "status": "success",
            "message": "Kullanıcı oluşturuldu",
            "api_key": api_key
        })
    return jsonify({"status": "error", "message": "Kullanıcı adı zaten kullanımda"}), 400

@app.route("/login", methods=["POST"])
def login():
    data = request.json
    username = data.get("username")
    password = data.get("password")

    api_key = db.get_user_api_key(username, password)
    if api_key:
        return jsonify({
            "status": "success",
            "message": "Giriş başarılı",
            "api_key": api_key
        })
    return jsonify({"status": "error", "message": "Geçersiz kullanıcı adı veya şifre"}), 401