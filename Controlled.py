import socketio
import os

# Socket.IO istemcisi
sio = socketio.Client()

# Sunucu URL'si
SERVER_URL = "http://localhost:5000"

@sio.on("connect")
def on_connect():
    print("Sunucuya bağlandınız!")

@sio.on("disconnect")
def on_disconnect():
    print("Sunucudan bağlantınız kesildi.")

@sio.on("execute_command")
def on_execute_command(data):
    command = data.get("command")
    print(f"Komut alındı: {command}")

    # Komutu çalıştırma
    if command == "shutdown":
        print("Bilgisayar kapatılıyor...")
        os.system("shutdown /s /t 1")  # Windows için kapatma komutu
    elif command == "sleep":
        print("Bilgisayar uyku moduna geçiyor...")
        os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")  # Windows için uyku modu komutu
    else:
        print(f"Bilinmeyen komut: {command}")


# Sunucuya bağlan
try:
    sio.connect(SERVER_URL)
    sio.wait()
except Exception as e:
    print(f"Sunucuya bağlanılamadı: {e}")
    