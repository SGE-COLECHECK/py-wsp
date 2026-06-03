# WSP Admin — Documentación del proyecto

## Arquitectura

```
py-wsp/
├── src/
│   └── app/
│       ├── core/
│       │   ├── ycloud_sender.py   ← Lógica híbrida YCloud + phonebook
│       │   ├── message_sender.py  ← Envío por Playwright (scraper) + router
│       │   ├── queue_manager.py   ← Colas Redis por cliente
│       │   └── browser_manager.py ← Navegadores Playwright
│       ├── ui/
│       │   └── app.py             ← GUI imgui (LOGS, QUEUES, YCLOUD, RESPONSES, PHONEBOOK)
│       ├── utils/
│       │   ├── config_manager.py  ← Config persistente (global + por cliente)
│       │   └── logger.py          ← Logger con colores, contadores diarios
│       └── main.py                ← FastAPI: 9 endpoints API + webhook
├── webhook.py                     ← Standalone (no se usa con main.py; solo logging)
├── data/config.json               ← Config persistente
└── run.py                         ← Entry point
```

## Sistema Híbrido YCloud + Scraper

### Flujo

1. Llega un POST a `/whatsapp/wapp-web/{account}/send*`
2. Se encola en Redis (`queue:{account}`)
3. `process_queue_item` decide:
   - Si `should_use_ycloud` → `send_via_ycloud`
   - Si falla o no aplica → `send_report_task` (Playwright)

### Modos por cliente

| Modo | Comportamiento |
|------|---------------|
| `solo_scraper` | Siempre por Playwright |
| `hibrido` | YCloud si respondió en < 24h, sino scraper |
| `solo_ycloud` | Siempre por YCloud (sin fallback) |

### ¿Cómo sabe si el padre respondió?

- Webhook YCloud (`POST /webhook`) recibe `whatsapp.inbound_message.received`
- Guarda `response:{phone_normalized}` con TTL 86400s (24h) en Redis
- `should_use_ycloud` verifica si esa key existe

### Phonebook

- `phonebook:{account}` — set de teléfonos por cliente
- `phonebook:meta:{account}` — hash phone→first_seen
- `phonebook:reverse` — hash phone→account (para webhook)
- Los teléfonos se registran automáticamente via `register_phone` en todos los endpoints API

### Formato de teléfono

- `normalize_phone` → limpia no-dígitos, agrega prefijo `51` si falta
- `send_via_ycloud` → envía como `+519XXXXXXXX`
- Almacenado en Redis sin `+` (e.g. `51940740243`)
- Capacidad: Redis Sets soportan millones. UI probada hasta 5000+ por cliente.

### Zona horaria

- `first_seen` en phonebook se almacena en **hora Lima (UTC-5)**
- Formato: `YYYY-MM-DD HH:MM:SS`
- `response:{phone}` usa `time.time()` (epoch Unix, UTC) — timezone-independiente, solo se compara contra `time() - 86400`

## Configuración

### Global (`data/config.json` → `_global_`)
| Clave | Default | Descripción |
|-------|---------|-------------|
| `ycloud_api_key` | `""` | API key global |
| `ycloud_from` | `"+51963828458"` | Número desde (global) |
| `ycloud_url` | `"https://api.ycloud.com/v2/whatsapp/messages/sendDirectly"` | Endpoint API |
| `phonebook_mode` | `"all_day"` | `"all_day"` o `"afternoon_only"` |

### YCLOUD Tab — Save button

Los cambios en la tabla del tab YCLOUD **no se guardan automáticamente**. Quedan en un buffer (`_yc_buf`) hasta que el usuario presiona **"GUARDAR CAMBIOS"**. Esto evita escrituras accidentales en cada tecla. Botón "DESCARTAR" para re-sincronizar con el archivo.

### Por cliente (en `data/config.json` → `clients.{name}`)
| Clave | Default | Descripción |
|-------|---------|-------------|
| `ycloud_enabled` | `false` | Activar YCloud |
| `ycloud_mode` | `"hibrido"` | Modo de envío |
| `ycloud_api_key` | `""` | API key (hereda global si vacío) |
| `ycloud_from` | `""` | Número desde (hereda global si vacío) |
| `ycloud_url` | `""` | URL API (hereda global si vacío) |

## API Endpoints

| Ruta | Descripción |
|------|-------------|
| `POST /webhook` | Webhook YCloud (inbound messages) |
| `GET /webhook?challenge=X` | Verificación YCloud challenge |
| `GET /health` | Health check |
| `POST /whatsapp/wapp-web/{account}/senddReport` | Reporte diario |
| `POST /whatsapp/wapp-web/{account}/addNumber` | Agregar contacto |
| `POST /whatsapp/wapp-web/{account}/sendWelcomeMessage` | Bienvenida |
| `POST /whatsapp/wapp-web/{account}/sendRegistrationLink` | Link registro |
| `POST /whatsapp/wapp-web/{account}/sendCredentials` | Credenciales |
| `POST /whatsapp/wapp-web/{account}/sendwReport` | Reporte semanal |
| `POST /whatsapp/wapp-web/{account}/sendAgenda` | Agenda escolar |
| `POST /whatsapp/wapp-web/{account}/sendComunicado` | Comunicado |
| `POST /whatsapp/wapp-web/{account}/sendWarning` | LLamado de atención |

## Redis Keys

| Key | Tipo | TTL | Propósito |
|-----|------|-----|-----------|
| `queue:{account}` | List | - | Cola de mensajes |
| `phonebook:{account}` | Set | - | Teléfonos del cliente |
| `phonebook:meta:{account}` | Hash | - | phone→first_seen |
| `phonebook:reverse` | Hash | - | phone→account lookup |
| `response:{phone}` | String | 86400s | Última respuesta (24h) |
| `ycloud:responded` | Set | - | Todos los que respondieron |
| `ycloud:responded:{account}` | Set | - | Por cliente |

## Issues conocidos / Edge cases

### API key case-sensitive
YCloud rechaza keys con mayúsculas. El `config_manager.set_client_config` convierte a minúsculas automáticamente. El modal global también aplica `.lower()`.

### Formato `from` number
Si el usuario escribe `51963828458` sin `+`, `send_via_ycloud` agrega `+` automáticamente.

### Teléfonos sin prefijo 51
`normalize_phone` agrega `51` si falta. Si el teléfono tiene menos de 9 dígitos después del 51, igual se concatena (puede dar número inválido).

### Dos webhooks
Hay dos implementaciones:
- `main.py:564` — integrado en FastAPI, hace `store_response` + `lookup_account`
- `webhook.py` — standalone, solo loguea eventos

Usar `main.py` para el sistema híbrido. `webhook.py` es para debug.

### Validación de 9 dígitos
Algunos endpoints rechazan teléfonos != 9 dígitos (después de limpiar). Números peruanos válidos siempre tienen 9, pero podría fallar si llega un número con código de país incluido (e.g. 51940740243 = 11 dígitos → rechazado).

### `logger.increment_sent` duplicado
`process_queue_item` llama `logger.increment_sent` si YCloud funciona (y hace return). Si YCloud falla, `send_report_task` también llama `increment_sent`. No hay doble conteo por el return temprano.

## Cómo agregar un nuevo endpoint API

1. Crear ruta POST en `main.py` con `background_tasks: BackgroundTasks`
2. Llamar `register_phone(account, phone)` para phonebook automático
3. Encolar con `queue_manager.enqueue(account, payload)`
4. El `type` del payload debe ser `"message"` para que `process_queue_item` lo rutee

## Cómo correr

```bash
python run.py --linux
# Abre GUI en puerto 3000 (FastAPI + UI)
```
