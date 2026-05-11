import requests
import time

BASE_URL = "http://localhost:3000/whatsapp/wapp-web/ie-manuel"

def test_daily_reports(count=5):
    print(f"\n🚀 Iniciando Test de {count} Reportes Diarios (Objetivo: ~15s total)")
    
    for i in range(1, count + 1):
        payload = {
            "telefono_padre": "963828458",
            "nombre_alumno": f"Alumno Test {i}",
            "type_asistance": "INGRESO",
            "timestamp": time.strftime("%H:%M:%S"),
            "dry_run": True
        }
        res = requests.post(f"{BASE_URL}/senddReport", json=payload)
        print(f"  [#{i}] Encolado: {res.status_code}")
    
    print(f"✅ {count} peticiones enviadas.")

def run_tests():
    print("=========================================================")
    print("🧪 SCRIPT DE PRUEBAS DE RENDIMIENTO (MODO DRY-RUN) 🧪")
    print("=========================================================")

    # Test de ráfaga
    test_daily_reports(5)

    # Otros tests individuales
    print("\n➡️ Enviando otros tipos de mensajes...")
    
    # Bienvenida
    requests.post(f"{BASE_URL}/sendWelcomeMessage", json={
        "telefono_padre": "963828458",
        "usuario": "padre123",
        "contrasena": "clave123",
        "url": "https://portal.colecheck.com",
        "dry_run": True
    })

    # Credenciales
    requests.post(f"{BASE_URL}/sendCredentials", json={
        "telefono_padre": "963828458",
        "usuario": "pro_user",
        "contrasena": "secret",
        "tenantId": "colegio-test",
        "dry_run": True
    })

    print("\n✅ Todas las peticiones encoladas.")
    print("Mira la interfaz gráfica para ver cómo vuela el bot 🚀")
    print("=========================================================")

if __name__ == "__main__":
    run_tests()
