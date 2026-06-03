import asyncio
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
    key = f"response:{normalize_phone(phone)}"
    now = time.time()
    await r.set(key, now, ex=86400)
    await r.sadd("ycloud:responded", phone)
    if account:
        await r.sadd(f"ycloud:responded:{account}", phone)


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
        from datetime import datetime
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

    payload = {
        "type": "text",
        "text": {"body": message, "preview_url": False},
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
