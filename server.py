from flask import Flask, request, jsonify, render_template
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import threading
import logging
import time
import secrets
from datetime import datetime
from functools import wraps

# Uygulama başlangıç konfigürasyonu
app = Flask(__name__, template_folder="templates")
app.config["SECRET_KEY"] = secrets.token_hex(32)  # Güvenli rastgele anahtar üretimi
socketio = SocketIO(app, cors_allowed_origins="*", logger=True, engineio_logger=True)
CORS(app, resources={r"/*": {"origins": "*"}})

# Logging konfigürasyonu
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - [%(name)s] %(message)s",
    handlers=[
        logging.FileHandler('server.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Sabitler ve Konfigürasyon
API_KEY = secrets.token_urlsafe(32)  # Güvenli API anahtarı üretimi
VALID_COMMANDS = {
    "shutdown": "Sistemi kapatır",
    "restart": "Sistemi yeniden başlatır",
    "sleep": "Uyku moduna alır",
    "volumeup": "Ses seviyesini artırır",
    "volumedown": "Ses seviyesini azaltır",
    "mute": "Sesi kapatır"
}

# Veri yapıları
connected_clients = {}
client_lock = threading.Lock()
command_history = []

def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get("X-API-KEY")
        if not api_key:
            logger.warning("API key missing in request")
            return jsonify({"status": "error", "message": "API key required"}), 401
        if api_key != API_KEY:
            logger.warning(f"Invalid API key attempt: {request.remote_addr}")
            return jsonify({"status": "error", "message": "Invalid API key"}), 403
        return f(*args, **kwargs)
    return decorated_function

# Route'lar
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/clients", methods=["GET"])
@require_api_key
def get_clients():
    with client_lock:
        client_info = [
            {
                "id": cid,
                "ip": info["ip"],
                "connected_at": info["connected_at"],
                "last_active": info["last_active"]
            }
            for cid, info in connected_clients.items()
        ]
    return jsonify({
        "status": "success",
        "clients": client_info,
        "total_clients": len(client_info)
    }), 200

@app.route("/commands", methods=["GET"])
@require_api_key
def get_commands():
    return jsonify({
        "status": "success",
        "commands": VALID_COMMANDS
    }), 200

@app.route("/send-command", methods=["POST"])
@require_api_key
def send_command():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "No JSON data provided"}), 400

        client_id = data.get("client_id")
        command = data.get("command")

        if not client_id or not command:
            return jsonify({"status": "error", "message": "Missing client_id or command"}), 400

        if command not in VALID_COMMANDS:
            return jsonify({"status": "error", "message": f"Invalid command. Valid commands are: {', '.join(VALID_COMMANDS)}"}), 400

        with client_lock:
            if client_id not in connected_clients:
                return jsonify({"status": "error", "message": "Client not found or disconnected"}), 404

            try:
                socketio.emit("execute_command", {
                    "command": command,
                    "timestamp": datetime.now().isoformat()
                }, room=client_id)

                command_history.append({
                    "client_id": client_id,
                    "command": command,
                    "timestamp": datetime.now().isoformat(),
                    "status": "sent"
                })

                logger.info(f"Command '{command}' sent to client {client_id}")
                return jsonify({"status": "success", "message": f"Command '{command}' sent successfully"}), 200

            except Exception as e:
                logger.error(f"Error sending command: {str(e)}")
                return jsonify({"status": "error", "message": "Internal server error"}), 500

    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        return jsonify({"status": "error", "message": "Internal server error"}), 500

# SocketIO event handlers
@socketio.on("connect")
def handle_connect():
    client_id = request.sid
    with client_lock:
        connected_clients[client_id] = {
            "ip": request.remote_addr,
            "connected_at": datetime.now().isoformat(),
            "last_active": datetime.now().isoformat()
        }
    logger.info(f"Client connected: {client_id} from IP: {request.remote_addr}")
    emit("connected", {
        "message": "Connected to server!",
        "client_id": client_id,
        "available_commands": VALID_COMMANDS
    })

@socketio.on("disconnect")
def handle_disconnect():
    client_id = request.sid
    with client_lock:
        if client_id in connected_clients:
            client_info = connected_clients.pop(client_id)
            logger.info(f"Client disconnected: {client_id} from IP: {client_info['ip']}")

@socketio.on("command_result")
def handle_command_result(data):
    client_id = request.sid
    command = data.get("command")
    success = data.get("success", False)
    message = data.get("message", "")

    logger.info(f"Command result from {client_id}: {command} - Success: {success} - Message: {message}")

    command_history.append({
        "client_id": client_id,
        "command": command,
        "timestamp": datetime.now().isoformat(),
        "status": "completed" if success else "failed",
        "message": message
    })

if __name__ == "__main__":
    logger.info(f"Server starting with API key: {API_KEY}")
    socketio.run(app, host="0.0.0.0", port=5000, debug=False)