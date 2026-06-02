import requests
import time

BASE_URL = "http://localhost:3000/whatsapp/wapp-web/borrar/senddReport"

NUMBERS = [
    "940740243",
    "971305405",
    "912589856",
    "974458263",
]

TOTAL_MSGS = 50

print(f"Encolando {TOTAL_MSGS} mensajes a {len(NUMBERS)} numeros...")

sent = 0
for i in range(TOTAL_MSGS):
    phone = NUMBERS[i % len(NUMBERS)]
    payload = {
        "telefono_padre": phone,
        "nombre_alumno": f"Alumno Test {i+1}",
        "type_asistance": "INGRESO",
        "timestamp": time.strftime("%H:%M:%S"),
    }
    try:
        res = requests.post(BASE_URL, json=payload, timeout=5)
        sent += 1
        status = "OK" if res.status_code == 200 else f"ERR {res.status_code}"
        print(f"  [{sent}/{TOTAL_MSGS}] {phone} -> {status}")
    except Exception as e:
        print(f"  [{sent+1}/{TOTAL_MSGS}] {phone} -> ERROR: {e}")

print(f"\nTotal encolados: {sent}")
print("Ahora ejecuta: python run_headless.py  (o python run.py --linux si hay GUI)")
