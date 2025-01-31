import socketio
import os
import time
import pyautogui
import platform
import logging
import json
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
SERVER_URL = "http://127.0.0.1:5000"
RECONNECT_DELAY = 5  # saniye
MAX_RECONNECT_ATTEMPTS = 5

class RemoteClient:
    def __init__(self):
        self.sio = socketio.Client(logger=True, engineio_logger=True)
        self.system = platform.system().lower()
        self.setup_handlers()
        self.commands = {
            "shutdown": self.shutdown,
            "restart": self.restart,
            "sleep": self.sleep,
            "volumeup": self.volume_up,
            "volumedown": self.volume_down,
            "mute": self.mute
        }

    def setup_handlers(self):
        @self.sio.event
        def connect():
            logger.info("Bağlantı başarılı!")

        @self.sio.event
        def disconnect():
            logger.warning("Sunucu bağlantısı kesildi!")

        @self.sio.on("execute_command")
        def on_execute_command(data):
            command = data.get("command")
            timestamp = data.get("timestamp", datetime.now().isoformat())

            logger.info(f"Komut alındı: {command} - Timestamp: {timestamp}")

            if command in self.commands:
                try:
                    self.commands[command]()
                    self.sio.emit("command_result", {
                        "command": command,
                        "success": True,
                        "timestamp": timestamp,
                        "message": f"{command} komutu başarıyla çalıştırıldı"
                    })
                except Exception as e:
                    error_msg = f"Komut çalıştırılırken hata: {str(e)}"
                    logger.error(error_msg)
                    self.sio.emit("command_result", {
                        "command": command,
                        "success": False,
                        "timestamp": timestamp,
                        "message": error_msg
                    })
            else:
                error_msg = f"Bilinmeyen komut: {command}"
                logger.warning(error_msg)
                self.sio.emit("command_result", {
                    "command": command,
                    "success": False,
                    "timestamp": timestamp,
                    "message": error_msg
                })

    def shutdown(self):
        if self.system == "windows":
            os.system("shutdown /s /t 1")
        elif self.system in ["linux", "darwin"]:
            os.system("shutdown now")

    def restart(self):
        if self.system == "windows":
            os.system("shutdown /r /t 1")
        elif self.system in ["linux", "darwin"]:
            os.system("shutdown -r now")

    def sleep(self):
        if self.system == "windows":
            os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
        elif self.system == "linux":
            os.system("systemctl suspend")
        elif self.system == "darwin":
            os.system("pmset sleepnow")

    def volume_up(self):
        pyautogui.press("volumeup")

    def volume_down(self):
        pyautogui.press("volumedown")

    def mute(self):
        pyautogui.press("volumemute")

    def connect_with_retry(self):
        attempts = 0
        while attempts < MAX_RECONNECT_ATTEMPTS:
            try:
                logger.info(f"Sunucuya bağlanılıyor... Deneme {attempts + 1}/{MAX_RECONNECT_ATTEMPTS}")
                self.sio.connect(SERVER_URL)
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