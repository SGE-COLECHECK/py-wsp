# ColeCheck WSP Admin

Sistema de envío masivo de mensajes WhatsApp con soporte híbrido **YCloud API** (mensajes rate-free dentro de ventana 24h) + **Playwright** (scraper vía WhatsApp Web). Interfaz gráfica con ImGui, colas Redis por cliente, y phonebook persistente.

## Arquitectura

```
FastAPI (3000) ← API endpoints → Redis Queue → process_queue_item
                                                    ├── YCloud (si respondió en 24h) ✅
                                                    └── Playwright / scraper (fallback) 🌐
```

- **Hybrid mode**: Si el padre respondió en las últimas 24h → YCloud API (rápido, sin scraper). Si no → Playwright.
- **Per-client config**: Cada colegio/cuenta tiene su propia API Key, From Number y modo YCloud.
- **GUI ImGui**: LOGS, QUEUES, YCLOUD, RESPONSES, PHONEBOOK.
- **Persistencia**: Redis con AOF (Docker volumen), config en JSON.

## Requisitos

- Python 3.10+
- Redis (local o Docker)
- Playwright (`playwright install chromium`)
- (Opcional) `python3-tk` para carga de Excel

## Instalación

```bash
pip install -r requirements.txt
playwright install chromium
```

## Uso

```bash
python run.py --linux
```

Abre GUI en `http://localhost:3000` (FastAPI backend en mismo proceso).

## Configuración YCloud

1. Tab **YCLOUD** → tabla por cliente: Enable, Modo, API Key, From, URL
2. Valores vacíos = heredan configuración global
3. API Key se guarda automáticamente en minúsculas (case-sensitive en YCloud)

## API Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/webhook` | Receive YCloud inbound messages |
| GET | `/health` | Health check |
| POST | `/whatsapp/wapp-web/{account}/senddReport` | Reporte diario |
| POST | `/whatsapp/wapp-web/{account}/addNumber` | Agregar contacto |
| POST | `/whatsapp/wapp-web/{account}/sendWelcomeMessage` | Bienvenida |
| POST | `/whatsapp/wapp-web/{account}/sendRegistrationLink` | Link registro |
| POST | `/whatsapp/wapp-web/{account}/sendCredentials` | Credenciales |
| POST | `/whatsapp/wapp-web/{account}/sendwReport` | Reporte semanal |
| POST | `/whatsapp/wapp-web/{account}/sendAgenda` | Agenda escolar |
| POST | `/whatsapp/wapp-web/{account}/sendComunicado` | Comunicado |
| POST | `/whatsapp/wapp-web/{account}/sendWarning` | LLamado de atención |
| POST | `/whatsapp/wapp-web/{account}/sendPhotocheck` | Enviar QR del estudiante |

## Documentación detallada

Ver `opencode.md` para descripción completa del sistema, Redis keys, edge cases, y guía de desarrollo.
