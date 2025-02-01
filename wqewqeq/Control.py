from flask import Flask, jsonify, request
import os

app = Flask(__name__)

# Güvenlik için API Anahtarı
API_KEY = "senin_gizli_anahtarin"

# API anahtarını doğrulama fonksiyonu
def check_api_key():
    api_key = request.headers.get("X-API-KEY")
    if api_key != API_KEY:
        return jsonify({"status": "error", "message": "Yetkisiz erişim!"}), 403

@app.before_request
def before_request():
    if request.endpoint in ["shutdown", "sleep"]:  # Kontrol etmek istediğimiz endpointler
        return check_api_key()

# Ana sayfa
@app.route("/")
def home():
    return """
<h1>Bilgisayar Kontrol Paneli</h1>
<p>Hoş geldiniz! Aşağıdaki endpointlerle bilgisayarınızı kontrol edebilirsiniz:</p>
<ul>
<li>Bilgisayarı kapatma: <code>POST /shutdown</code></li>
<li>Uyku moduna alma: <code>POST /sleep</code></li>
</ul>
"""

# Bilgisayarı kapatma endpointi
@app.route("/shutdown", methods=["POST"])
def shutdown():
    os.system("shutdown /s /t 1")  # Windows için kapatma komutu
    return jsonify({"status": "success", "message": "Bilgisayar kapatılıyor..."})

# Bilgisayarı uyku moduna alma endpointi
@app.route("/sleep", methods=["POST"])
def sleep():
    os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")  # Windows için uyku modu komutu
    return jsonify({"status": "success", "message": "Bilgisayar uyku moduna geçiyor..."})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
    