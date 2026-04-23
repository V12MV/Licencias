from flask import Flask
from threading import Thread
import os

app = Flask('')

@app.route('/')
def home():
    return "¡Bot Activo y Trabajando, mano!"

def run():
    # Render asigna puertos dinámicamente, por eso usamos os.environ.get
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()
