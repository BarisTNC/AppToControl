# client.py
import socketio
import os
import time
import pyautogui
import platform
import logging
import json
import uuid
import sqlite3
from datetime import datetime

# Logging konfigürasyonu
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('client.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Konfigürasyon
SERVER_URL = "https://your-domain.com"  # Production URL'inizi buraya yazın
RECONNECT_DELAY = 5
MAX_RECONNECT_ATTEMPTS = 5
DB_PATH = "client_config.db"

class ClientDatabase:
    def __init__(self):
        self.init_db()

    def init_db(self):
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute('''CREATE TABLE IF NOT EXISTS config
            (key TEXT PRIMARY KEY, value TEXT)''')
            conn.commit()

    def get_api_key(self):
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute('SELECT value FROM config WHERE key = "api_key"')
            result = c.fetchone()
            return result[0] if result else None

    def save_api_key(self, api_key):
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute('INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)',
                      ('api_key', api_key))
            conn.commit()

class RemoteClient:
    def __init__(self):
        self.sio = socketio.Client(logger=True, engineio_logger=True)
        self.db = ClientDatabase()
        self.system = platform.system().lower()
        self.client_id = str(uuid.uuid4())
        self.setup_handlers()

        # Sistem bilgilerini topla
        self.system_info = {
            'platform': platform.platform(),
            'processor': platform.processor(),
            'memory': self.get_memory_info(),
            'hostname': platform.node(),
            'python_version': platform.python_version()
        }

        # Komut haritası genişletildi
        self.commands = {
            "shutdown": self.shutdown,
            "restart": self.restart,
            "sleep": self.sleep,
            "lock": self.lock_system,
            "logout": self.logout_user,
            "volumeup": self.volume_up,
            "volumedown": self.volume_down,
            "mute": self.mute,
            "screenshot": self.take_screenshot,
            "processes": self.list_processes,
            "kill": self.kill_process,
            "exec": self.execute_command,
            "sysinfo": self.get_system_info,
            "clipboard": self.get_clipboard,
            "setclipboard": self.set_clipboard,
            "type": self.type_text,
            "press": self.press_key,
            "battery": self.get_battery_info
        }

    def get_memory_info(self):
        try:
            import psutil
            memory = psutil.virtual_memory()
            return {
                'total': memory.total,
                'available': memory.available,
                'percent': memory.percent
            }
        except:
            return "Unable to get memory info"

    def setup_handlers(self):
        @self.sio.event
        def connect():
            logger.info(f"Bağlantı başarılı! Client ID: {self.client_id}")
            # Sistem bilgilerini gönder
            self.sio.emit('system_info', {
                'client_id': self.client_id,
                'system_info': self.system_info
            })

        @self.sio.event
        def disconnect():
            logger.warning("Sunucu bağlantısı kesildi!")

        @self.sio.on("execute_command")
        def on_execute_command(data):
            command = data.get("command")
            command_id = data.get("command_id")
            params = data.get("parameters", {})
            timestamp = data.get("timestamp")

            logger.info(f"Komut alındı: {command} - ID: {command_id}")

            if command in self.commands:
                try:
                    result = self.commands[command](**params) if params else self.commands[command]()
                    self.sio.emit("command_result", {
                        "command": command,
                        "command_id": command_id,
                        "success": True,
                        "result": result,
                        "timestamp": timestamp
                    })
                except Exception as e:
                    error_msg = f"Komut çalıştırılırken hata: {str(e)}"
                    logger.error(error_msg)
                    self.sio.emit("command_result", {
                        "command": command,
                        "command_id": command_id,
                        "success": False,
                        "error": error_msg,
                        "timestamp": timestamp
                    })
            else:
                error_msg = f"Bilinmeyen komut: {command}"
                logger.warning(error_msg)
                self.sio.emit("command_result", {
                    "command": command,
                    "command_id": command_id,
                    "success": False,
                    "error": error_msg,
                    "timestamp": timestamp
                })

    # Yeni sistem komutları
    def lock_system(self):
        if self.system == "windows":
            os.system("rundll32.exe user32.dll,LockWorkStation")
        elif self.system == "darwin":
            os.system("/System/Library/CoreServices/Menu\\ Extras/User.menu/Contents/Resources/CGSession -suspend")
        elif self.system == "linux":
            os.system("loginctl lock-session")
        return {"status": "System locked"}

    def logout_user(self):
        if self.system == "windows":
            os.system("shutdown -l")
        elif self.system == "darwin":
            os.system("osascript -e 'tell application \"System Events\" to log out'")
        elif self.system == "linux":
            os.system("gnome-session-quit --logout --no-prompt")
        return {"status": "User logged out"}

    # Mevcut komutlar güncellendi
    def shutdown(self):
        if self.system == "windows":
            os.system("shutdown /s /t 1")
        elif self.system in ["linux", "darwin"]:
            os.system("shutdown now")
        return {"status": "System shutting down"}

    def restart(self):
        if self.system == "windows":
            os.system("shutdown /r /t 1")
        elif self.system in ["linux", "darwin"]:
            os.system("shutdown -r now")
        return {"status": "System restarting"}

    def sleep(self):
        if self.system == "windows":
            os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
        elif self.system == "linux":
            os.system("systemctl suspend")
        elif self.system == "darwin":
            os.system("pmset sleepnow")
        return {"status": "System going to sleep"}

    def volume_up(self):
        pyautogui.press("volumeup")
        return {"status": "Volume increased"}

    def volume_down(self):
        pyautogui.press("volumedown")
        return {"status": "Volume decreased"}

    def mute(self):
        pyautogui.press("volumemute")
        return {"status": "Volume muted"}

    def take_screenshot(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"screenshot_{timestamp}.png"
        pyautogui.screenshot(filename)
        return {"filename": filename, "status": "Screenshot taken"}

    def list_processes(self):
        import psutil
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                processes.append(proc.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return {"processes": processes}

    def kill_process(self, pid):
        import psutil
        try:
            process = psutil.Process(pid)
            process.kill()
            return {"success": True, "message": f"Process {pid} killed"}
        except psutil.NoSuchProcess:
            return {"success": False, "message": f"Process {pid} not found"}

    def get_system_info(self):
        return self.system_info

    def get_clipboard(self):
        import pyperclip
        return {"text": pyperclip.paste()}

    def set_clipboard(self, text):
        import pyperclip
        pyperclip.copy(text)
        return {"status": "Clipboard content set"}

    def type_text(self, text):
        pyautogui.write(text)
        return {"status": "Text typed"}

    def press_key(self, key):
        pyautogui.press(key)
        return {"status": f"Key {key} pressed"}

    def get_battery_info(self):
        try:
            import psutil
            battery = psutil.sensors_battery()
            if battery:
                return {
                    "percent": battery.percent,
                    "power_plugged": battery.power_plugged,
                    "time_left": battery.secsleft
                }
            return {"error": "No battery found"}
        except:
            return {"error": "Unable to get battery info"}

    def connect_with_retry(self):
        api_key = self.db.get_api_key()

        if not api_key:
            api_key = input("API Key'inizi girin: ")
            self.db.save_api_key(api_key)

        attempts = 0
        while attempts < MAX_RECONNECT_ATTEMPTS:
            try:
                logger.info(f"Sunucuya bağlanılıyor... Deneme {attempts + 1}/{MAX_RECONNECT_ATTEMPTS}")
                self.sio.connect(
                    f"{SERVER_URL}?client_id={self.client_id}&api_key={api_key}",
                    headers={"X-API-KEY": api_key}
                )
                logger.info("Sunucuya bağlantı başarılı!")
                return True
            except Exception as e:
                attempts += 1
                logger.error(f"Bağlantı hatası: {str(e)}")
                if attempts < MAX_RECONNECT_ATTEMPTS:
                    logger.info(f"{RECONNECT_DELAY} saniye sonra tekrar denenecek...")
                    time.sleep(RECONNECT_DELAY)

        logger.error("Maksimum bağlantı deneme sayısına ulaşıldı!")
        return False

    def run(self):
        try:
            if self.connect_with_retry():
                # Heartbeat sistemini başlat
                def send_heartbeat():
                    while self.sio.connected:
                        self.sio.emit('heartbeat', {
                            'system_info': self.system_info,
                            'timestamp': datetime.now().isoformat()
                        })
                        time.sleep(30)  # Her 30 saniyede bir heartbeat gönder

                import threading
                heartbeat_thread = threading.Thread(target=send_heartbeat)
                heartbeat_thread.daemon = True
                heartbeat_thread.start()

                logger.info("İstemci çalışıyor ve komut bekliyor...")
                self.sio.wait()
            else:
                logger.error("Sunucuya bağlanılamadı, program sonlandırılıyor.")
        except KeyboardInterrupt:
            logger.info("İstemci kullanıcı tarafından sonlandırıldı.")
        except Exception as e:
            logger.error(f"Beklenmeyen hata: {str(e)}")
        finally:
            if self.sio.connected:
                self.sio.disconnect()

if __name__ == "__main__":
    client = RemoteClient()
    client.run()