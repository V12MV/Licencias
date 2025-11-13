from flask import Flask, request, jsonify
import requests
import datetime
import os

app = Flask(__name__)

# Obtén los valores desde variables de entorno
BASEROW_TOKEN = os.getenv("BASEROW_TOKEN")    # Pon tu token en Render, no en el código
TABLE_ID = os.getenv("BASEROW_TABLE_ID")

def check_license(license_key):
    url = f"https://api.baserow.io/api/database/rows/table/{TABLE_ID}/?user_field_names=true"
    headers = {"Authorization": f"Token {BASEROW_TOKEN}"}
    resp = requests.get(url, headers=headers)
    data = resp.json()
    today = datetime.date.today()
    for row in data["results"]:
        if row["license_key"] == license_key:
            activo = row["activo"]
            expira = row["fecha_expira"]
            dias_restantes = (datetime.date.fromisoformat(expira) - today).days
            if activo and dias_restantes > 0:
                return {"valida": True, "expira": expira, "dias": dias_restantes, "usuario": row.get("usuario","")}
            else:
                return {"valida": False, "expira": expira, "dias": dias_restantes, "usuario": row.get("usuario","")}
    return {"valida": False}

@app.route("/validar", methods=["POST"])
def validar():
    licencia = request.json.get("key","")
    resultado = check_license(licencia)
    return jsonify(resultado), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
