from flask import Flask, request, jsonify, redirect, url_for
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import threading
import logging
import time
import os
import platform

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

# Utility Functions for System Commands
def execute_system_command(command):
    try:
        if platform.system() == "Windows":
            if command == "shutdown":
                os.system("shutdown /s /t 1")
            elif command == "restart":
                os.system("shutdown /r /t 1")
            elif command == "sleep":
                os.system("rundll32.exe powrprof.dll,SetSuspendState Sleep")
        else:
            if command == "shutdown":
                os.system("sudo shutdown now")
            elif command == "restart":
                os.system("sudo reboot")
            elif command == "sleep":
                os.system("systemctl suspend")
        logger.info(f"Executed system command: {command}")
        return jsonify({"status": "success", "message": f"Command '{command}' executed successfully."}), 200
    except Exception as e:
        logger.error(f"Error executing system command '{command}': {e}")
        return jsonify({"status": "error", "message": f"Error executing command: {e}"}), 500

# Routes for System Commands
@app.route("/<command>")
def handle_command(command):
    if command not in VALID_COMMANDS:
        return jsonify({"status": "error", "message": "Invalid command"}), 400
    return execute_system_command(command)

@app.route("/")
def index():
    return '''
<h1>System Command Control</h1>
<ul>
<li><a href="/shutdown">Shutdown</a></li>
<li><a href="/restart">Restart</a></li>
<li><a href="/sleep">Sleep</a></li>
</ul>
'''

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

# Command Input for Manual Testing
def command_input_loop():
    while True:
        time.sleep(1)  # Reduce CPU usage
        with client_lock:
            if not connected_clients:
                print("⚠️ No connected clients. Waiting...")
                continue

        print("\n🔹 Connected Clients:")
        for i, (client_id, ip) in enumerate(connected_clients.items(), 1):
            print(f"{i}. {client_id} - {ip}")

        try:
            choice = input("\nSelect client number ('q' to quit): ").strip()
            if choice.lower() == 'q':
                print("Exiting...")
                break

            choice = int(choice) - 1
            client_ids = list(connected_clients.keys())

            if 0 <= choice < len(client_ids):
                selected_client = client_ids[choice]
            else:
                print("⚠️ Invalid selection! Try again.")
                continue

            command = input(f"\nEnter command ({', '.join(VALID_COMMANDS)}): ").strip()
            if command not in VALID_COMMANDS:
                print("⚠️ Invalid command! Try again.")
                continue

            print(f"📤 Sending command: {command} -> {selected_client}")
            socketio.emit("execute_command", {"command": command}, room=selected_client)

        except ValueError:
            print("⚠️ Invalid input! Enter a number or 'q' to quit.")

# Start Command Input Thread
threading.Thread(target=command_input_loop, daemon=True).start()

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)
