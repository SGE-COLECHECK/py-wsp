# Contexto de la sesión - feat/smart-send-and-inactivity

## Rama actual
`feat/smart-send-and-inactivity` (basada en `wsp-hybrid`)

## Qué se implementó en esta sesión

### 1. smart_send() — prioridad YCloud para respondedores
**Archivo:** `src/app/core/ycloud_sender.py:222-256`

```python
async def smart_send(account, phone, message, label="MSG") -> str
```

Decisión al momento de ENQUEUE (no al procesar):
- Si teléfono está inactivo/bloqueado + `block_inactive=True` → `skipped`
- Si cliente ya respondió antes (`response:{phone}` en Redis) → YCloud fast-path con lock por cuenta
- Si no → encolar normalmente (scraper con delays anti-ban)
- Si YCloud falla → fallback a encolar (no se pierde el mensaje)

Delay YCloud: `ycloud_min_delay=0.0`, `ycloud_max_delay=0.1` (casi instantáneo, API oficial)
Lock por cuenta: `asyncio.Lock` por `account` en `_ycloud_locks` dict (preserva orden, independiente entre cuentas)

### 2. Endpoints cambiados en main.py
8 endpoints de mensaje ahora usan `smart_send` en vez de `queue_manager.enqueue`:
- `senddReport` (línea 52)
- `sendWelcomeMessage` (línea 128)
- `sendRegistrationLink` (línea 187)
- `sendCredentials` (línea 242)
- `sendwReport` (línea 314)
- `sendAgenda` (línea 372)
- `sendComunicado` (línea 424)
- `sendWarning` (línea 488)

`addNumber` (línea 74) **NO** se cambió — sigue con `enqueue` porque es tipo `add_contact`, no mensaje.

Import en main.py:5: `from app.core.ycloud_sender import store_response, register_phone, lookup_account, smart_send`

### 3. Sistema de inactividad del phonebook
**Archivo:** `src/app/core/ycloud_sender.py:108-220`

Estados por teléfono (Redis `phonebook:state:{account}` hash):
- `active` (default) — recibe mensajes
- `inactive` — auto tras N días sin respuesta, o manual
- `blocked` — desactivado manualmente (permanente)

Funciones nuevas:
- `get_phone_state(account, phone)` — lee estado
- `set_phone_state(account, phone, state)` — escribe estado
- `deactivate_phone(account, phone)` — manual
- `reactivate_phone(account, phone)` — manual
- `block_phone(account, phone)` — manual permanente
- `get_account_states(account)` — dict {phone: state}
- `auto_deactivate_stale(account, days)` — auto, solo si `ycloud_enabled=True` Y `ycloud_mode="hibrido"` Y `days>0`
- `should_skip_phone(account, phone)` — True si inactivo/bloqueado + `block_inactive=True`

Criterio auto-deactivate (ycloud_sender.py:142-191):
- `first_seen` (cuándo se agregó al phonebook) < `now - days*86400`
- Y NO existe `response:{phone}` en Redis (TTL 24h)
- Y no estaba ya inactive/blocked
- Cuenta desde `first_seen`, no desde última respuesta

### 4. Skip en worker scraper
**Archivo:** `src/app/core/message_sender.py:443-447`

`process_queue_item` revisa `should_skip_phone` antes de procesar (por si un mensaje se encoló antes de marcarse como inactivo).

### 5. Config por cliente (config_manager.py:67-79)
Defaults nuevos en `get_client_config`:
```python
"deactivate_after_days": 0,    # 0 = off, slider 0-30 en UI
"block_inactive": False,        # checkbox en UI
```

### 6. UI
**Archivo:** `src/app/ui/app.py`

**Phonebook** (líneas ~757-820):
- Nueva columna "Activo" con 🟢 activo / 🟡 inactivo / 🔴 bloqueado
- Nueva columna "Acción" con botón "Activar/Desactivar" por fila
- Botón usa `asyncio.run_coroutine_threadsafe(coro, self.loop)` (imgui es sync)

**Client Config modal** (líneas ~933-947):
- Sección "AUTO-INACTIVIDAD (solo con YCloud+webhook)"
- Checkbox "Bloquear envío a inactivos/bloqueados"
- Slider "Desactivar tras N días sin respuesta (0=off)"
- Guardado en SAVE & CLOSE junto con resto de config

**Auto-check periódico** (líneas ~83-85):
- Cada 3s en `update_data`, ejecuta `auto_deactivate_stale(acc, days)` por sesión
- Solo si `ycloud_enabled` Y `mode=="hibrido"` Y `days>0`

**Cache de phonebook** (líneas ~78-95):
- Añadido `state` por entrada (lee de `get_account_states(acc)`)

### 7. Defaults globales nuevos
**Archivo:** `src/app/utils/config_manager.py:31-32, 51-52`

```python
"ycloud_min_delay": 0.0
"ycloud_max_delay": 0.1
```

## Archivos modificados
- `src/app/core/ycloud_sender.py` — smart_send, _get_ycloud_lock, state mgmt
- `src/app/utils/config_manager.py` — 4 defaults nuevos
- `src/app/main.py` — 8 endpoints → smart_send
- `src/app/core/message_sender.py` — skip en worker
- `src/app/ui/app.py` — UI completa
- `test_smart_send.py` (nuevo) — test timing
- `test_phonebook_states.py` (nuevo) — test estados

## Commit
- Hash: `df18f46`
- Branch: `feat/smart-send-and-inactivity`
- Push: **PENDIENTE** (usuario debe correr `git push -u origin feat/smart-send-and-inactivity`)

## Lo que NO se cambió (preservado)
- `process_queue_item` (worker logic) — solo se añadió skip al inicio
- `send_via_ycloud` — idéntico
- `send_report_task` (scraper) — idéntico
- `webhook.py` — idéntico
- `phonebook:reverse`, `phonebook:meta`, `response:{phone}` — idénticos
- Modo híbrido (respondedor→YCloud, no-respondedor→scraper) — comportamiento idéntico
- Datos en Redis — solo se añade `phonebook:state:{account}` (vacío inicialmente)
- `config.json` existente — solo añade keys nuevas con defaults

## Tareas pendientes del usuario
1. `git push -u origin feat/smart-send-and-inactivity` (push manual con credenciales)
2. Probar en `feat/smart-send-and-inactivity` por unos días
3. Si OK, mergear a `wsp-hybrid`:
   ```bash
   git checkout wsp-hybrid
   git merge feat/smart-send-and-inactivity
   git push origin wsp-hybrid
   ```

## Para volver a este contexto en otra sesión
Decir: "Estoy en py-wsp, rama feat/smart-send-and-inactivity. Necesito [X] relacionado con smart_send, inactividad de phonebook, o modo híbrido YCloud."
