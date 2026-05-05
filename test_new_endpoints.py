import requests
import json

BASE_URL = "http://localhost:3000"
ACCOUNT = "test-session"

def test_welcome():
    print("\n--- Testing Welcome Message ---")
    payload = {
        "telefono_padre": "987654321",
        "usuario": "padre_test",
        "contrasena": "123456",
        "url": "http://example.com/welcome",
        "dry_run": True
    }
    response = requests.post(f"{BASE_URL}/whatsapp/wapp-web/{ACCOUNT}/sendWelcomeMessage", json=payload)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")

def test_registration():
    print("\n--- Testing Registration Link ---")
    payload = {
        "telefono_padre": "912345678",
        "url": "http://example.com/register",
        "dry_run": True
    }
    response = requests.post(f"{BASE_URL}/whatsapp/wapp-web/{ACCOUNT}/sendRegistrationLink", json=payload)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")

if __name__ == "__main__":
    try:
        test_welcome()
        test_registration()
    except Exception as e:
        print(f"Error: {e}")
