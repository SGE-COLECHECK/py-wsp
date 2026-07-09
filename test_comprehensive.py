#!/usr/bin/env python3
"""
TEST COMPREHENSIVE — Envía a los 3 números por YCloud y scraper,
verifica streaks, bloqueo, recovery, store_response.
"""

import asyncio
import json
import sys
import os
import time
import urllib.request
import urllib.error

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from app.core.queue_manager import queue_manager
from app.utils.config_manager import config_manager


PASS = "✅"
FAIL = "❌"
WARN = "⚠️"

# Los 3 números de prueba
PHONES = ["963828458", "940740243", "986384764"]
ADMIN = PHONES[0]  # 963828458


def api_post(path: str, data: dict) -> dict:
    url = f"http://localhost:3000{path}"
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}


def api_health() -> bool:
    try:
        with urllib.request.urlopen("http://localhost:3000/health", timeout=5) as r:
            return r.status == 200
    except:
        return False


async def test():
    results = []
    ok_count = 0
    fail_count = 0

    def r(name: str, ok: bool, detail: str = ""):
        nonlocal ok_count, fail_count
        icon = PASS if ok else FAIL
        print(f"  {icon} {name}" + (f" — {detail}" if detail else ""))
        results.append({"name": name, "ok": ok, "detail": detail})
        if ok:
            ok_count += 1
        else:
            fail_count += 1

    print("\n" + "=" * 60)
    print("  TEST COMPREHENSIVE — py-wsp definitiva")
    print(f"  {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    app_start = time.time()

    # ─── 1. Health ───
    print("\n─── 1. API ───")
    health = api_health()
    r("API /health responde", health)
    if not health:
        print(f"\n  {FAIL} La API no responde. ¿Ejecutaste 'python run.py --linux'?")
        sys.exit(1)

    # ─── 2. Redis ───
    print("\n─── 2. REDIS ───")
    redis_ok = await queue_manager.get_redis() is not None
    r("Redis conecta", redis_ok)

    # ─── 3. YCloud a los 3 números ───
    print("\n─── 3. YCLOUD (a los 3 números) ───")
    from app.core.ycloud_sender import send_via_ycloud

    for phone in PHONES:
        msg = f"🧪 Test automático YCloud\nHora: {time.strftime('%H:%M:%S')}\nPara verificar entrega"
        ok = await send_via_ycloud(phone, msg, "ie-borrar")
        r(f"YCloud → {phone}", ok)

    # ─── 4. Scraper a los 3 números (vía API) ───
    print("\n─── 4. SCRAPER (a los 3 números, vía API) ───")
    from app.core.ycloud_sender import normalize_phone

    for phone in PHONES:
        # Limpiar response key para forzar scraper
        r_conn = await queue_manager.get_redis()
        if r_conn:
            nphone = normalize_phone(phone)
            await r_conn.delete(f"response:{nphone}")

        # Encolar vía API
        resp = api_post(f"/whatsapp/wapp-web/ie-borrar/senddReport", {
            "telefono_padre": phone,
            "nombre_alumno": f"TEST SCRAPER {phone[-4:]}",
            "type_asistance": "🧪 SCRAPER TEST",
            "timestamp": time.strftime("%H:%M"),
        })
        ok = resp.get("status") == "enqueued"
        r(f"Scraper → {phone} encolado", ok, str(resp))

    # ─── 5. Esperar scraper y verificar streaks ───
    print(f"\n─── 5. ESPERANDO SCRAPER (35s) ───")
    await asyncio.sleep(35)

    r_conn = await queue_manager.get_redis()
    for phone in PHONES:
        nphone = normalize_phone(phone)
        streak = await r_conn.get(f"send_streak:{nphone}")
        state = await r_conn.hget(f"phonebook:state:ie-borrar", nphone)
        r(f"Streak {phone}", streak is not None, f"streak={streak}, state={state}")

    # ─── 6. store_response (simular webhook) ───
    print("\n─── 6. STORE_RESPONSE (simular webhook) ───")
    from app.core.ycloud_sender import store_response

    test_phone = PHONES[0]  # Admin
    nphone = normalize_phone(test_phone)
    old_streak = await r_conn.get(f"send_streak:{nphone}")
    old_state = await r_conn.hget(f"phonebook:state:ie-borrar", nphone)

    await store_response(test_phone, "ie-borrar")

    new_streak = await r_conn.get(f"send_streak:{nphone}")
    new_state = await r_conn.hget(f"phonebook:state:ie-borrar", nphone)
    has_response = await r_conn.exists(f"response:{nphone}")

    r("store_response borra send_streak", new_streak is None, f"antes={old_streak}, despues={new_streak}")
    r("store_response auto-reactiva", new_state == "active", f"antes={old_state}, despues={new_state}")
    r("store_response crea response:key", has_response == 1)

    # ─── 7. Envío por YCloud (ahora con response key, debe ir por YCloud) ───
    print("\n─── 7. SMART_SEND (con response key, debe usar YCloud) ───")
    from app.core.ycloud_sender import smart_send

    result = await smart_send(
        "ie-borrar",
        test_phone,
        f"🧪 Test smart_send con response key\n{time.strftime('%H:%M:%S')}",
        "TEST SMART",
    )
    r("smart_send con response", result in ("ycloud",), f"ruta={result}")

    # ─── 8. auto_block_stale ───
    print("\n─── 8. AUTO_BLOCK_STALE ───")
    cfg = config_manager.get_client_config("ie-borrar")
    was_enabled = cfg.get("auto_block_enabled", False)
    if not was_enabled:
        config_manager.set_client_config("ie-borrar", {"auto_block_enabled": True, "auto_block_message": "⚠️ AVISO: responda o será suspendido"})

    # Crear phones de prueba
    warn_phone = normalize_phone("51999990001")
    block_phone = normalize_phone("51999990002")
    await r_conn.sadd("phonebook:ie-borrar", warn_phone, block_phone)
    await r_conn.set(f"send_streak:{warn_phone}", 2)
    await r_conn.set(f"send_streak:{block_phone}", 3)

    from app.core.ycloud_sender import auto_block_stale
    total = await auto_block_stale("ie-borrar")

    s_warn = await r_conn.hget(f"phonebook:state:ie-borrar", warn_phone)
    s_block = await r_conn.hget(f"phonebook:state:ie-borrar", block_phone)

    r("auto_block_stale streak=2 warning", s_warn is None, f"state={s_warn}")
    r("auto_block_stale streak=3 bloquea", s_block == "blocked", f"state={s_block}")

    # Limpiar
    await r_conn.srem("phonebook:ie-borrar", warn_phone, block_phone)
    await r_conn.delete(f"send_streak:{warn_phone}", f"send_streak:{block_phone}")
    await r_conn.hdel(f"phonebook:state:ie-borrar", warn_phone, block_phone)
    if not was_enabled:
        config_manager.set_client_config("ie-borrar", {"auto_block_enabled": False})

    # ─── 9. Recovery (verificar pause/resume) ───
    print("\n─── 9. QUEUE MANAGER ───")
    await queue_manager.pause_worker("ie-borrar")
    paused = "ie-borrar" in queue_manager.paused_workers
    await queue_manager.resume_worker("ie-borrar")
    resumed = "ie-borrar" not in queue_manager.paused_workers
    r("pause/resume worker", paused and resumed)

    # ─── 10. Estado final ───
    print("\n─── 10. ESTADO FINAL ───")
    for phone in PHONES:
        nphone = normalize_phone(phone)
        streak = await r_conn.get(f"send_streak:{nphone}")
        state = await r_conn.hget(f"phonebook:state:ie-borrar", nphone)
        response = await r_conn.get(f"response:{nphone}")
        print(f"  {phone}: streak={streak}, state={state}, response={'✓' if response else '✗'}")

    failed_count = await r_conn.llen("failed:ie-borrar")
    print(f"  Fallidos totales: {failed_count}")

    # ─── RESUMEN ───
    total = ok_count + fail_count
    print(f"\n{'='*60}")
    print(f"  {'✅ TODAS OK' if fail_count == 0 else f'❌ {fail_count} FALLARON'}  ({ok_count}/{total})")
    print(f"  Tiempo: {time.time() - app_start:.1f}s")
    print(f"{'='*60}")

    if fail_count:
        print(f"\n  Fallos:")
        for t in results:
            if not t["ok"]:
                print(f"    {FAIL} {t['name']}: {t['detail']}")
        print()

    # ─── CLEANUP ───
    print(f"\n─── CLEANUP ───")
    print(f"  Los tests crearon datos en Redis (send_streak, response, states).")
    print(f"  Datos actuales de los 3 números de prueba:")
    for phone in PHONES:
        nphone = normalize_phone(phone)
        streak = await r_conn.get(f"send_streak:{nphone}")
        state = await r_conn.hget(f"phonebook:state:ie-borrar", nphone)
        response = await r_conn.get(f"response:{nphone}")
        print(f"    {phone}: streak={streak}, state={state}, response={'✓' if response else '✗'}")

    try:
        inp = input(f"\n  ¿Resetear datos de prueba? (s/N): ").strip().lower()
    except (EOFError, OSError):
        inp = ""
    if inp == "s":
        for phone in PHONES:
            nphone = normalize_phone(phone)
            await r_conn.delete(f"send_streak:{nphone}", f"response:{nphone}")
            await r_conn.hdel(f"phonebook:state:ie-borrar", nphone)
            await r_conn.hdel(f"phonebook:meta:ie-borrar", nphone)
            await r_conn.srem(f"phonebook:ie-borrar", nphone)
            await r_conn.srem(f"ycloud:responded", phone)
        print(f"  {PASS} Datos de prueba reseteados. Redis limpio.")
    else:
        print(f"  {WARN} Datos de prueba conservados en Redis.")

    return fail_count == 0


if __name__ == "__main__":
    success = asyncio.run(test())
    sys.exit(0 if success else 1)
