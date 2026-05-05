import requests
import time
import json

# Usa el nombre de la sesión que tengas activa en la UI, por defecto 'ie-manuel'
ACCOUNT_NAME = "ie-manuel"
BASE_URL = f"http://localhost:3000/whatsapp/wapp-web/{ACCOUNT_NAME}"
HEADERS = {"Content-Type": "application/json"}

print("=========================================================")
print("🧪 SCRIPT DE PRUEBAS AUTOMATIZADAS (MODO DRY-RUN) 🧪")
print("=========================================================\n")

try:
    # --- 1. PRUEBA DE REPORTE DIARIO ---
    print("➡️ Ejecutando Test: Reporte Diario (/senddReport)")
    payload_diario = {
        "telefono_padre": "963828458",
        "dry_run": True
    }
    res = requests.post(f"{BASE_URL}/senddReport", json=payload_diario, headers=HEADERS)
    print(f"Respuesta: {res.status_code} - {res.json()}\n")

    time.sleep(1)

    # --- 2. PRUEBA DE AÑADIR CONTACTO ---
    print("➡️ Ejecutando Test: Añadir Contacto (/addNumber)")
    payload_contacto = {
        "nombre": "Padre Test",
        "telefono": "963828458",
        "dry_run": True
    }
    res = requests.post(f"{BASE_URL}/addNumber", json=payload_contacto, headers=HEADERS)
    print(f"Respuesta: {res.status_code} - {res.json()}\n")

    time.sleep(1)

    # --- 3. PRUEBA DE MENSAJE DE BIENVENIDA ---
    print("➡️ Ejecutando Test: Welcome Message (/sendWelcomeMessage)")
    payload_welcome = {
        "telefono_padre": "963828458",
        "usuario": "padre123",
        "contrasena": "Temporal2025!",
        "url": "https://portal.colecheck.com",
        "dry_run": True
    }
    res = requests.post(f"{BASE_URL}/sendWelcomeMessage", json=payload_welcome, headers=HEADERS)
    print(f"Respuesta: {res.status_code} - {res.json()}\n")

    time.sleep(1)

    # --- 4. PRUEBA DE REPORTE SEMANAL ---
    print("➡️ Ejecutando Test: Reporte Semanal (/sendwReport)")
    payload_semanal = {
        "dni": "12345678",
        "nombre_alumno": "Ana Sofía Torres López",
        "nombre_padre": "Roberto Torres",
        "telefono_padre": "963828458",
        "grado": "3ro",
        "seccion": "B",
        "fecha_inicio": "20/01/2025",
        "fecha_fin": "24/01/2025",
        "lunes": "Asistencia",
        "martes": "Tardanza",
        "miercoles": "Asistencia",
        "jueves": "Asistencia",
        "viernes": "Falta",
        "desempeno": 4,
        "dry_run": True
    }
    res = requests.post(f"{BASE_URL}/sendwReport", json=payload_semanal, headers=HEADERS)
    print(f"Respuesta: {res.status_code} - {res.json()}\n")

    time.sleep(1)

    # --- 5. PRUEBA DE SALUD Y REDIS ---
    print("➡️ Ejecutando Test: Health Check de Redis (/health)")
    res = requests.get("http://localhost:3000/health")
    print(f"Respuesta: {res.status_code} - {res.json()}\n")

    print("=========================================================")
    print("✅ TODAS LAS PETICIONES ENCOLADAS EXITOSAMENTE ✅")
    print("Mira los logs en tu programa de interfaz gráfica para ver cómo")
    print("el bot procesa todo en modo DRY-RUN (sin enviar nada).")
    print("=========================================================")

except requests.exceptions.ConnectionError:
    print("❌ ERROR: No se pudo conectar a la API.")
    print("Asegúrate de que el bot esté corriendo (python run.py) y en el puerto 3000.")
except Exception as e:
    print(f"❌ ERROR: {e}")
