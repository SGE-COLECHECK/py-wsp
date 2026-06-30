import asyncio
import random
import time
from datetime import datetime, timezone, timedelta
import requests
from app.utils.logger import logger
from app.utils.config_manager import config_manager
from app.core.queue_manager import queue_manager

PERU_TZ = timezone(timedelta(hours=-5))


def normalize_phone(phone: str) -> str:
    cleaned = "".join(filter(str.isdigit, phone))
    if not cleaned.startswith("51"):
        cleaned = "51" + cleaned[-9:] if len(cleaned) >= 9 else "51" + cleaned
    return cleaned


async def get_last_response(phone: str) -> float | None:
    r = await queue_manager.get_redis()
    if not r:
        return None
    val = await r.get(f"response:{normalize_phone(phone)}")
    if val:
        try:
            return float(val)
        except (ValueError, TypeError):
            return None
    return None


async def store_response(phone: str, account: str = ""):
    r = await queue_manager.get_redis()
    if not r:
        return
    nphone = normalize_phone(phone)
    key = f"response:{nphone}"
    now = time.time()
    await r.set(key, now, ex=86400)
    await r.sadd("ycloud:responded", phone)
    if account:
        await r.sadd(f"ycloud:responded:{account}", phone)
        await r.hset(f"last_response:{account}", nphone, now)
        current_state = await r.hget(f"phonebook:state:{account}", nphone)
        if current_state in ("inactive", "blocked"):
            await r.hset(f"phonebook:state:{account}", nphone, "active")
            logger.info(f"[{account}] {nphone} → AUTO-REACTIVADO por webhook", account=account)


async def get_responded_count(account: str = "") -> int:
    r = await queue_manager.get_redis()
    if not r:
        return 0
    if account:
        return await r.scard(f"ycloud:responded:{account}")
    return await r.scard("ycloud:responded")


async def get_responded_phones(account: str = "") -> list:
    r = await queue_manager.get_redis()
    if not r:
        return []
    if account:
        members = await r.smembers(f"ycloud:responded:{account}")
    else:
        members = await r.smembers("ycloud:responded")
    return sorted(members)


async def register_phone(account: str, phone: str):
    mode = config_manager.get_global("phonebook_mode", "all_day")
    if mode == "afternoon_only":
        if datetime.now().hour < 12:
            return
    r = await queue_manager.get_redis()
    if not r:
        return
    nphone = normalize_phone(phone)
    added = await r.sadd(f"phonebook:{account}", nphone)
    if added:
        now_pe = datetime.now(PERU_TZ).replace(tzinfo=None).isoformat(timespec="milliseconds")
        await r.hset(f"phonebook:meta:{account}", nphone, now_pe)
    await r.hset("phonebook:reverse", nphone, account)


async def get_account_phone_count(account: str) -> int:
    r = await queue_manager.get_redis()
    if not r:
        return 0
    return await r.scard(f"phonebook:{account}")


async def get_account_phones(account: str) -> list:
    r = await queue_manager.get_redis()
    if not r:
        return []
    members = await r.smembers(f"phonebook:{account}")
    return sorted(members)


async def get_phonebook_with_meta(account: str) -> list:
    r = await queue_manager.get_redis()
    if not r:
        return []
    phones = await r.smembers(f"phonebook:{account}")
    meta = await r.hgetall(f"phonebook:meta:{account}") or {}
    result = []
    for phone in sorted(phones):
        first_seen = meta.get(phone, "desconocido")
        result.append({"phone": phone, "first_seen": first_seen})
    return result


async def get_phone_status(phone: str) -> str:
    r = await queue_manager.get_redis()
    if not r:
        return "scraper"
    exists = await r.get(f"response:{normalize_phone(phone)}")
    return "ycloud" if exists else "scraper"


PHONE_STATES = ("active", "inactive", "blocked")


async def get_phone_state(account: str, phone: str) -> str:
    """Estado del teléfono en el phonebook del cliente: active | inactive | blocked."""
    r = await queue_manager.get_redis()
    if not r:
        return "active"
    state = await r.hget(f"phonebook:state:{account}", normalize_phone(phone))
    return state if state in PHONE_STATES else "active"


async def set_phone_state(account: str, phone: str, state: str) -> None:
    if state not in PHONE_STATES:
        return
    r = await queue_manager.get_redis()
    if not r:
        return
    await r.hset(f"phonebook:state:{account}", normalize_phone(phone), state)


async def deactivate_phone(account: str, phone: str) -> None:
    await set_phone_state(account, phone, "inactive")
    logger.info(f"[{account}] {phone} → INACTIVO (manual)", account=account)


async def reactivate_phone(account: str, phone: str) -> None:
    await set_phone_state(account, phone, "active")
    logger.info(f"[{account}] {phone} → ACTIVO", account=account)


async def block_phone(account: str, phone: str) -> None:
    await set_phone_state(account, phone, "blocked")
    logger.info(f"[{account}] {phone} → BLOQUEADO", account=account)


async def get_account_states(account: str) -> dict:
    """Devuelve {phone: state} para todos los teléfonos del cliente."""
    r = await queue_manager.get_redis()
    if not r:
        return {}
    return await r.hgetall(f"phonebook:state:{account}") or {}


async def auto_deactivate_stale(account: str, days: int) -> int:
    """
    Marca como 'inactive' los teléfonos que:
      - Tienen 'first_seen' más viejo que `days`
      - Y nunca respondieron (no hay response:{phone} en Redis)
    Devuelve la cantidad de teléfonos desactivados.
    Solo aplica si el cliente tiene ycloud_enabled=True, ycloud_mode='hibrido' y days > 0.
    """
    if days <= 0:
        return 0
    cfg = config_manager.get_client_config(account)
    if not cfg.get("ycloud_enabled", False):
        return 0
    if cfg.get("ycloud_mode", "hibrido") != "hibrido":
        return 0
    r = await queue_manager.get_redis()
    if not r:
        return 0
    phones = await r.smembers(f"phonebook:{account}")
    meta = await r.hgetall(f"phonebook:meta:{account}") or {}
    cutoff = time.time() - (days * 86400)
    deactivated = 0
    for phone in phones:
        nphone = normalize_phone(phone)
        first_seen_str = meta.get(nphone)
        if not first_seen_str:
            continue
        try:
            first_seen = datetime.fromisoformat(first_seen_str).timestamp()
        except (ValueError, TypeError):
            continue
        if first_seen > cutoff:
            continue
        responded = await r.get(f"response:{nphone}")
        if responded:
            continue
        current = await r.hget(f"phonebook:state:{account}", nphone)
        if current in ("inactive", "blocked"):
            continue
        await r.hset(f"phonebook:state:{account}", nphone, "inactive")
        deactivated += 1
    if deactivated:
        logger.info(
            f"[{account}] Auto-inactivos: {deactivated} (>{days} días sin respuesta)",
            account=account,
        )
    return deactivated


async def should_skip_phone(account: str, phone: str) -> bool:
    """Devuelve True si el teléfono está inactivo/bloqueado Y el cliente tiene block_inactive=True."""
    cfg = config_manager.get_client_config(account)
    if not cfg.get("block_inactive", False):
        return False
    state = await get_phone_state(account, phone)
    return state in ("inactive", "blocked")


async def lookup_account(phone: str) -> str:
    r = await queue_manager.get_redis()
    if not r:
        return ""
    return await r.hget("phonebook:reverse", normalize_phone(phone)) or ""


async def get_all_phonebooks() -> dict:
    r = await queue_manager.get_redis()
    if not r:
        return {}
    accounts = config_manager.get_client_list()
    result = {}
    for acc in accounts:
        phones = await r.smembers(f"phonebook:{acc}")
        result[acc] = sorted(phones)
    return result


def get_ycloud_mode(account: str) -> str:
    cfg = config_manager.get_client_config(account)
    enabled = cfg.get("ycloud_enabled", False)
    if not enabled:
        return "solo_scraper"
    return cfg.get("ycloud_mode", "hibrido")


async def should_use_ycloud(phone: str, account: str) -> bool:
    mode = get_ycloud_mode(account)
    nphone = normalize_phone(phone)
    if mode == "solo_scraper":
        logger.debug(f"YCloud mode=solo_scraper for {account}, skipping")
        return False
    if mode == "solo_ycloud":
        logger.debug(f"YCloud mode=solo_ycloud for {account}, using YCloud")
        return True
    last = await get_last_response(phone)
    has_resp = last is not None
    logger.info(f"YCloud híbrido [{account}] {nphone}: respondió={has_resp}", account=account)
    return has_resp


async def send_via_ycloud(phone: str, message: str, account: str) -> bool:
    cfg = config_manager.get_client_config(account)
    api_key = cfg.get("ycloud_api_key") or config_manager.get_global("ycloud_api_key", "")
    from_number = cfg.get("ycloud_from") or config_manager.get_global("ycloud_from", "+51963828458")
    url = cfg.get("ycloud_url") or config_manager.get_global(
        "ycloud_url",
        "https://api.ycloud.com/v2/whatsapp/messages/sendDirectly",
    )

    if not api_key:
        logger.warn(f"YCloud: API key no configurada para {account}", account=account)
        return False

    to_phone = "+" + normalize_phone(phone)
    if from_number and not from_number.startswith("+"):
        from_number = "+" + from_number

    # Distinguir visualmente mensajes YCloud vs scraper
    body = message.replace(" ▪️ ", " ▫️ ")
    payload = {
        "type": "text",
        "text": {"body": body, "preview_url": False},
        "from": from_number,
        "to": to_phone,
    }
    headers = {
        "X-API-Key": api_key,
        "accept": "application/json",
        "content-type": "application/json",
    }

    def _send():
        return requests.post(url, json=payload, headers=headers, timeout=15)

    try:
        loop = asyncio.get_event_loop()
        resp = await loop.run_in_executor(None, _send)
        if resp.status_code in (200, 202):
            logger.success(f"YCloud ✓ {to_phone}", account=account)
            logger.increment_ycloud_sent(account)
            return True
        logger.error(
            f"YCloud ✗ {to_phone}: {resp.status_code} {resp.text[:200]}",
            account=account,
        )
        return False
    except Exception as e:
        logger.error(f"YCloud ✗ {to_phone}: {e}", account=account)
        return False


_ycloud_locks: dict[str, asyncio.Lock] = {}


def _get_ycloud_lock(account: str) -> asyncio.Lock:
    if account not in _ycloud_locks:
        _ycloud_locks[account] = asyncio.Lock()
    return _ycloud_locks[account]


async def smart_send(account: str, phone: str, message: str, label: str = "MSG") -> str:
    """
    Decide fast-path YCloud o slow-path queue.
    - Fast path: si el cliente ya respondió antes, va directo por YCloud con delay mínimo.
    - Slow path: encola normalmente, el worker lo procesa por scraper con delays anti-ban.
    - Fallback: si YCloud falla, encola como slow path para no perder el mensaje.
    Devuelve 'ycloud' | 'queue' | 'queue_fallback' | 'skipped' para logging.
    """
    if await should_skip_phone(account, phone):
        state = await get_phone_state(account, phone)
        logger.info(f"[{account}] {phone} → SKIP (estado={state})", account=account)
        return "skipped"

    if not await should_use_ycloud(phone, account):
        await queue_manager.enqueue(account, {
            "phone": phone, "message": message, "label": label, "type": "message",
        })
        logger.info(f"[{account}] {phone} → cola (scraper)", account=account)
        return "queue"

    lock = _get_ycloud_lock(account)
    async with lock:
        yc_min = config_manager.get_client_delay(account, "ycloud_min_delay", 0.0)
        yc_max = config_manager.get_client_delay(account, "ycloud_max_delay", 0.1)
        if yc_max > yc_min:
            await asyncio.sleep(random.uniform(yc_min, yc_max))
        sent = await send_via_ycloud(phone, message, account)
        if sent:
            logger.increment_sent(account)
            logger.info(f"[{account}] {phone} → YCloud fast-path ✓", account=account)
            return "ycloud"

    logger.warn(f"[{account}] YCloud falló para {phone}, fallback a cola", account=account)
    await queue_manager.enqueue(account, {
        "phone": phone, "message": message, "label": label, "type": "message",
    })
    return "queue_fallback"


def _get_monday_timestamp() -> float:
    now = datetime.now(PERU_TZ)
    monday = now - timedelta(days=now.weekday())
    monday = monday.replace(hour=0, minute=0, second=0, microsecond=0)
    return monday.timestamp()


async def auto_block_stale(account: str) -> int:
    """
    Revisión semanal programada (review_day a las 8 PM).
    Bloquea teléfonos que NO han respondido desde el lunes de la semana actual.
    Encola mensaje de advertencia antes de bloquear.
    Solo aplica si auto_block_enabled=True en la config del cliente.
    Skip: teléfonos agregados después del lunes, o que ya respondieron esta semana.
    """
    cfg = config_manager.get_client_config(account)
    if not cfg.get("auto_block_enabled", False):
        return 0
    r = await queue_manager.get_redis()
    if not r:
        return 0
    monday_ts = _get_monday_timestamp()
    phones = await r.smembers(f"phonebook:{account}")
    meta = await r.hgetall(f"phonebook:meta:{account}") or {}
    last_responses = await r.hgetall(f"last_response:{account}") or {}
    blocked = 0
    for phone in phones:
        nphone = normalize_phone(phone)
        current_state = await r.hget(f"phonebook:state:{account}", nphone)
        if current_state in ("inactive", "blocked"):
            continue
        first_seen_str = meta.get(nphone)
        if first_seen_str:
            try:
                first_seen = datetime.fromisoformat(first_seen_str).timestamp()
                if first_seen > monday_ts:
                    continue
            except (ValueError, TypeError):
                pass
        last_resp_str = last_responses.get(nphone)
        if last_resp_str:
            try:
                last_resp_ts = float(last_resp_str)
                if last_resp_ts >= monday_ts:
                    continue
            except (ValueError, TypeError):
                pass
        warning_msg = cfg.get("auto_block_message", "")
        if warning_msg:
            await queue_manager.enqueue(account, {
                "phone": nphone,
                "message": warning_msg,
                "label": "AVISO BLOQUEO",
                "type": "message",
                "is_warning": True,
            })
        await r.hset(f"phonebook:state:{account}", nphone, "blocked")
        logger.info(f"[{account}] {nphone} → BLOQUEADO (sin respuesta desde lunes)", account=account)
        blocked += 1
    if blocked:
        logger.info(
            f"[{account}] Auto-bloqueo semanal: {blocked} teléfonos bloqueados",
            account=account,
        )
    return blocked
