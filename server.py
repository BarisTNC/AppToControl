from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
import os

app = Flask(__name__)
app.config["SECRET_KEY"] = "super-secret-key"
socketio = SocketIO(app, cors_allowed_origins="*")

# İstemciler bağlantı kimliği ile kaydedilecek
connected_clients = {}

# API Anahtarı
API_KEY = "senin_gizli_anahtarin"

# API Anahtarını Doğrulama Fonksiyonu
def check_api_key():
    api_key = request.headers.get("X-API-KEY")
    if api_key != API_KEY:
        return jsonify({"status": "error", "message": "Yetkisiz erişim!"}), 403


@app.before_request
def before_request():
    # Korumalı endpointler için API anahtarını kontrol et
    if request.endpoint in ["send_command"]:
        return check_api_key()


@app.route("/")
def index():
    return jsonify({"message": "Sunucu çalışıyor!"})


# Komut Gönderme Endpoint'i
@app.route("/send-command", methods=["POST"])
def send_command():
    data = request.json
    client_id = data.get("client_id")
    command = data.get("command")

    if client_id in connected_clients:
        emit("execute_command", {"command": command}, room=client_id)
        return jsonify({"status": "success", "message": f"Komut gönderildi: {command}"})
    else:
        return jsonify({"status": "error", "message": "İstemci bulunamadı."}), 404


@socketio.on("connect")
def handle_connect():
    client_id = request.sid
    connected_clients[client_id] = request.remote_addr
    print(f"İstemci bağlandı: {client_id} - IP: {connected_clients[client_id]}")
    emit("connected", {"message": "Sunucuya bağlandınız!"})


@socketio.on("disconnect")
def handle_disconnect():
    client_id = request.sid
    if client_id in connected_clients:
        print(f"İstemci bağlantısı kesildi: {client_id}")
        del connected_clients[client_id]


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)
    