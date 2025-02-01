from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import threading
import logging
import time

# Flask & SocketIO Initialization
app = Flask(__name__)
app.config["SECRET_KEY"] = "your_secret_key"
socketio = SocketIO(app, cors_allowed_origins="*")
CORS(app, resources={r"/*": {"origins": "*"}})

# Logging Setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# API Key
API_KEY = "your_secret_api_key"

# Connected Clients (Thread-Safe)
connected_clients = {}
client_lock = threading.Lock()

# Allowed Commands
VALID_COMMANDS = {"shutdown", "restart", "sleep"}

# API Key Authentication
def require_api_key(f):
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get("X-API-KEY")
        if api_key != API_KEY:
            return jsonify({"status": "error", "message": "Unauthorized access!"}), 403
        return f(*args, **kwargs)
    return decorated_function

@app.route("/")
def index():
    return jsonify({"message": "Server is running!"})

@app.route("/send-command", methods=["POST"])
@require_api_key
def send_command():
    data = request.json
    client_id = data.get("client_id")
    command = data.get("command")

    if not client_id or not command:
        return jsonify({"status": "error", "message": "Missing client_id or command"}), 400

    if command not in VALID_COMMANDS:
        return jsonify({"status": "error", "message": "Invalid command"}), 400

    with client_lock:
        if client_id in connected_clients:
            try:
                logger.info(f"Sending command '{command}' to client {client_id}")
                socketio.emit("execute_command", {"command": command}, room=client_id)
                return jsonify({"status": "success", "message": f"Command sent: {command}"}), 200
            except Exception as e:
                logger.error(f"Error sending command: {e}")
                return jsonify({"status": "error", "message": f"Server error: {e}"}), 500
        else:
            return jsonify({"status": "error", "message": "Client not found"}), 404

@socketio.on("connect")
def handle_connect():
    client_id = request.sid
    with client_lock:
        connected_clients[client_id] = request.remote_addr
    logger.info(f"Client connected: {client_id} - IP: {connected_clients[client_id]}")
    emit("connected", {"message": "Connected to server!"})

@socketio.on("disconnect")
def handle_disconnect():
    client_id = request.sid
    with client_lock:
        if client_id in connected_clients:
            del connected_clients[client_id]
            logger.info(f"Client disconnected: {client_id}")

# **🔹 Terminalden Komut Girişi (Manuel Kontrol)**
def command_input_loop():
    while True:
        time.sleep(1)  # CPU kullanımını düşürmek için kısa bir bekleme süresi
        with client_lock:
            if not connected_clients:
                print("⚠️ Bağlı istemci yok. Bekleniyor...")
                continue

        print("\n🔹 Bağlı istemciler:")
        for i, (client_id, ip) in enumerate(connected_clients.items(), 1):
            print(f"{i}. {client_id} - {ip}")

        try:
            choice = input("\nİstemci numarası seçin (veya 'q' ile çıkın): ").strip()
            if choice.lower() == 'q':
                print("Çıkış yapılıyor...")
                break

            choice = int(choice) - 1
            client_ids = list(connected_clients.keys())

            if 0 <= choice < len(client_ids):
                selected_client = client_ids[choice]
            else:
                print("⚠️ Geçersiz seçim! Tekrar deneyin.")
                continue

            command = input(f"\nKomut girin ({', '.join(VALID_COMMANDS)}): ").strip()
            if command not in VALID_COMMANDS:
                print("⚠️ Geçersiz komut! Tekrar deneyin.")
                continue

            print(f"📤 Komut gönderiliyor: {command} -> {selected_client}")
            socketio.emit("execute_command", {"command": command}, room=selected_client)

        except ValueError:
            print("⚠️ Geçersiz giriş! Sayı girin veya 'q' ile çıkın.")

# **Komut Girişi için Ayrı Bir Thread Başlat**
threading.Thread(target=command_input_loop, daemon=True).start()

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)
