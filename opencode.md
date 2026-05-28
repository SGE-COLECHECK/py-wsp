# py-wsp - ColeCheck WhatsApp Admin

## Project Overview
Desktop app for bulk WhatsApp messaging automation for the **ColeCheck** educational platform. School administrators send automated WhatsApp notifications to parents (attendance reports, welcome messages, credentials, registration links, agenda, communications, warnings). Uses **Playwright** (headless browser) + **WhatsApp Web**, **Redis** backend, **Dear ImGui** desktop GUI.

## Tech Stack
- **Language:** 100% Python
- **Web Server:** FastAPI + Uvicorn (port 3000)
- **Browser Automation:** Playwright (Chromium, headless by default)
- **Queue:** Redis 7 (via Docker) - async FIFO queue per account
- **GUI:** Dear ImGui via `imgui-bundle`
- **Templates:** Custom welcome message with `{usuario}`, `{contrasena}`, `{url}`, `{fecha}` placeholders
- **Alternative channel:** YCloud WhatsApp Business API (Excel import, cost tracking)

## Directory Structure
```
py-wsp/
├── .gitignore
├── COLECHECK_WSP_ADMIN.ini      # ImGui layout config
├── docker-compose.yml            # Redis 7 Alpine (port 6379, volume anty_wsp_redis_data)
├── requirements.txt              # Python deps
├── run.py                        # Entry point (launches 3 threads)
├── opencode.md                   # This file
├── data/
│   ├── config.json               # Runtime config (gitignored)
│   ├── debug/                    # Debug screenshots
│   └── sessions/                 # Chromium profiles per account (gitignored)
├── src/
│   └── app/
│       ├── main.py               # FastAPI server + 9 REST endpoints
│       ├── core/
│       │   ├── browser_manager.py  # Playwright singleton, per-account contexts
│       │   ├── message_sender.py   # WhatsApp automation (send + add contact)
│       │   └── queue_manager.py    # Redis async queue workers
│       ├── ui/
│       │   └── app.py            # Dear ImGui desktop GUI
│       └── utils/
│           ├── config_manager.py  # JSON config CRUD
│           └── logger.py         # Terminal + GUI logger (circular buffer 300)
├── test_api.py
└── test_new_endpoints.py
```

## Architecture (3 Threads)
```
run.py
├── Thread 1: Playwright async event loop (asyncio)
├── Thread 2: FastAPI/Uvicorn server (port 3000)
└── Thread 3 (main): Dear ImGui desktop GUI
```

Data flow: `External System → POST → FastAPI → enqueue → Redis Queue → worker → Playwright (WhatsApp Web) → Parent's Phone`

## API Endpoints
All under `/whatsapp/wapp-web/{account}/`:
- `POST /senddReport` - Daily attendance report
- `POST /addNumber` - Add contact
- `POST /sendWelcomeMessage` - Welcome + login credentials
- `POST /sendRegistrationLink` - Registration link
- `POST /sendCredentials` - Credentials message
- `POST /sendwReport` - Weekly attendance report
- `POST /sendAgenda` - Academic agenda
- `POST /sendComunicado` - Official communication
- `POST /sendWarning` - Disciplinary warning (severity: leve/moderado/grave)
- `GET /health` - Redis connection health check

All with `dry_run` flag. All responses: `{queueId, sessionName, status: "queued"}`.

## Key Components

### Browser Manager (`browser_manager.py`)
- Singleton, per-account persistent Chromium contexts (`data/sessions/profile_{name}/`)
- States: OFFLINE → STARTING → READY → ERROR
- Monitors `#side` selector for login detection
- Can run headless or visible (configurable per account)
- Cleans up SingletonLock files

### Message Sender (`message_sender.py`)
- `send_report_task()`: Search contact → find input box → type/paste → send (2 retries)
- `add_contact_task()`: New Chat → New Contact → fill fields → detect status → save (2 attempts)
- `process_queue_item()`: Router by `data.type`
- Two send modes: **typing** (letter-by-letter) or **paste** (clipboard)
- Random pre-send delay, timing per phase (prep/search/typing/total)

### Queue Manager (`queue_manager.py`)
- Redis key format: `queue:{account_name}`
- Auto-starts workers on enqueue
- Pause/resume per account
- Batch processing (default: 20 messages, 60s pause)
- Random inter-message delay (default 2-5s)
- Configurable via GUI (Global Config tab)

### GUI (`ui/app.py`)
- **Sidebar** (28%, min 280px): Start All, per-account status (enable/auth/play/settings/delete), New Client button
- **Tabs**: LOGS (colored table), GLOBAL CONFIG (sliders), YCLOUD (Excel import + send)
- **Bottom bar**: Redis status, CPU/RAM
- **Modals**: Delete/add client, config, YCloud settings
- **Theme**: DarculaDarker

### Logger (`logger.py`)
- Singleton, 300-entry circular buffer
- ANSI terminal colors + ImGui UI colors
- Per-account color cycling (8 colors)
- Daily stats (morning/afternoon split)

### Config Manager (`config_manager.py`)
- Singleton, `data/config.json`
- Global: redis host/port, delays, batch settings, send mode, YCloud config
- Per-client: headless, enabled
- Auto-initializes defaults

## Dependencies
- fastapi, uvicorn, pydantic (API)
- playwright (browser automation)
- imgui-bundle (desktop GUI)
- redis + hiredis (queue)
- psutil (CPU/RAM monitoring)
- requests (YCloud API + tests)
- openpyxl (Excel import)

## Infrastructure (Docker)
```yaml
redis:7-alpine, container: anty_wsp_redis, port 6379
persistent volume, AOF fsync every sec, 512MB memory limit
custom bridge network: anty_wsp_network
```

## Git History
- **Origin:** `https://github.com/SGE-COLECHECK/py-wsp.git`
- **Branch:** `overridewelcome` (created from `main`)
- **Branches:** `main`, `overridewelcome`
- **Commits:** 18 (2026-05-04 to 2026-05-13)
- **Last commit message:** "send hjll"

## Testing
- `test_api.py`: Tests daily report, welcome, credentials (dry-run, account: ie-manuel)
- `test_new_endpoints.py`: Tests welcome + registration link (dry-run, account: test-session)

## Conventions
- Spanish throughout (UI, logs, templates)
- Peruvian phone numbers (+51, 9 digits)
- Account names as URL path params (e.g., `ie-manuel`)
- `{usuario}`, `{contrasena}`, `{url}`, `{fecha}` template vars
- Anti-spam: random delays, batch pauses, message variability, dry-run mode
- Error resilience: 2 retries, screenshots to `data/errors/`, fallback CSS selectors

## Contact Addition Status Detection
Detected phone statuses: whatsapp, duplicate, not_on_whatsapp, new (based on DOM elements in the new contact flow)

---

## `overridewelcome` Branch Features

### Per-Client Welcome Message Override
Each client/account can have its own override settings (in `config.json` under `clients.{name}`):
- `override_welcome` (bool) - Enable custom welcome message for this client
- `custom_welcome_msg` (str) - Texto EXACTO que se enviará. Sin variables, sin reemplazos. Soporta saltos de línea.
- `override_min_delay` (int | null) - Per-client min delay between msgs (null = use global)
- `override_max_delay` (int | null) - Per-client max delay between msgs (null = use global)
- `override_batch_size` (int | null) - Per-client batch size (null = use global)
- `override_batch_pause` (int | null) - Per-client batch pause in seconds (null = use global)

### Files Changed
- `config_manager.py`: New methods `get_client_override()` and `get_client_delay()` with fallback to global
- `queue_manager.py`: Uses `get_client_delay()` for per-client delays/batches
- `main.py`: `sendWelcomeMessage` reads override from client config instead of global
- `ui/app.py`: Client Config modal now has sections for Welcome Override, Delay Overrides, Batch Overrides; GLOBAL CONFIG tab updated with notice

### How to Use
1. Click **⚙** (gear icon) next to a client in the sidebar
2. Enable "Override Welcome Message", write custom template
3. Set delay/batch overrides (0 = use global settings from GLOBAL CONFIG tab)
4. Click **SAVE & CLOSE**
5. The welcome message and queue delays will now use per-client values

### Test Send (Client Config)
When override is enabled, a **TEST SEND** section appears:
- Input phone number (with 51 prefix)
- Click **SEND TEST** → enqueues the override message immediately to that number

### `--linux` / `--develop` Flag
`run.py` detects `--linux` or `--develop` in argv to activate Ubuntu 26.04 Playwright compatibility (`.browsers/` path + platform override). Without flag, runs clean (no env vars) — compatible with Windows production.

## Session Changes (2026-05-27)

### Welcome Message Structure
- **Header fijo** (siempre se antepone): `🚨🇨🇴🇱🇪✅ *[fecha]* 👋 ¡Bienvenido/a!`
- **Override = solo el cuerpo**: El text area del override es únicamente el cuerpo del mensaje. El header con marca y fecha se agrega automáticamente.
- **Sin override**: Se usa un cuerpo por defecto (texto de bienvenida genérico).
- **Sin f-strings**: Se usa `.format()` para evitar errores de encoding con Unicode en Windows.
- **Sin zero-width spaces**: Se eliminaron los caracteres U+200B que rompían el parser de Python en Windows.

### Search Delay
- Nuevo setting global `search_delay` (default 2.0s) en GLOBAL CONFIG.
- Pausa después de escribir el número en el buscador y antes de presionar Enter.
- Da tiempo a WhatsApp para encontrar el contacto.
- Post-Enter wait aumentado de 0.5s a 1.0s.

### Windows 500 Error Fixed
- El error `500 Internal Server Error` en `sendWelcomeMessage` era por emojis con zero-width joiners dentro de f-strings en Windows.
- Solución: usar unicode escapes (`\U0001F6A8`) en strings regulares con `.format()`.

### Other Changes
- **overridewelcome branch**: Per-client welcome override + delay/batch overrides
- **Welcome override simplified**: No more `{usuario}`, `{contrasena}`, `{url}`, `{fecha}` — just raw text, sent as-is. Header (brand + date) is auto-prepended.
- **tkinter**: Compiled `_tkinter` from Python 3.14.4 source + extracted Tcl/Tk debs into `.tk-lib/` for this Linux dev machine (no sudo needed)
- **Playwright**: Browsers installed at default location via `PLAYWRIGHT_HOST_PLATFORM_OVERRIDE=ubuntu24.04-x64 playwright install chromium`
- **run.py**: Clean by default; `--linux`/`--develop` flag activates Ubuntu 26.04 patches (`.browsers/` + platform override)
- **Config Manager**: New `get_client_override()` and `get_client_delay()` per-client with global fallback
- **Queue Manager**: Uses `get_client_delay()` for per-client batch/delay settings
- **GUI**: Client Config modal now has: Welcome Override (cuerpo), Test Send, Delay Overrides, Batch Overrides
- **start.sh**: Helper script that activates venv and runs with `--linux`
