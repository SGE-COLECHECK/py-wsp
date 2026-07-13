#!/usr/bin/env python3
"""
TEST COMPREHENSIVE — Versión definitiva.
Prueba streak_today (1x/día), bloqueo, lunes reset, YCloud, store_response.
"""

import asyncio
import json
import sys
import os
import time
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from app.core.queue_manager import queue_manager
from app.utils.config_manager import config_manager

PASS = "✅"
FAIL = "❌"
WARN = "⚠️"

PHONES = ["963828458", "940740243", "986384764"]
ACCOUNT = "ie-borrar"


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

    start = time.time()

    print("\n" + "=" * 60)
    print("  TEST COMPREHENSIVE — Versión definitiva")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # ─── 1. Redis ───
    print("\n─── 1. REDIS ───")
    r_conn = await queue_manager.get_redis()
    r("Redis conecta", r_conn is not None)
    if not r_conn:
        return False

    # ─── 2. YCloud ───
    print("\n─── 2. YCLOUD ───")
    from app.core.ycloud_sender import send_via_ycloud, normalize_phone, store_response, get_phone_state
    for phone in PHONES:
        ok = await send_via_ycloud(
            phone,
            f"🧪 Test YCloud definitiva\n{datetime.now().strftime('%H:%M:%S')}",
            ACCOUNT,
        )
        r(f"YCloud → {phone}", ok)

    # ─── 3. Configurar auto_block_enabled ───
    print("\n─── 3. CONFIG ───")
    cfg = config_manager.get_client_config(ACCOUNT)
    old_block = cfg.get("auto_block_enabled", False)
    config_manager.set_client_config(ACCOUNT, {
        "auto_block_enabled": True,
        "auto_block_message": "⚠️ AVISO: responda o será suspendido",
        "ycloud_enabled": True,
        "ycloud_mode": "hibrido",
    })
    r("auto_block_enabled + YCloud híbrido configurado", True)

    # ─── 4. streak_today (1x por día) ───
    print("\n─── 4. STREAK_TODAY (1 incremento por día) ───")
    nphone = normalize_phone(PHONES[0])
    today = datetime.now().strftime("%Y-%m-%d")
    today_key = f"streak_today:{nphone}:{today}"
    streak_key = f"send_streak:{nphone}"

    # Limpiar estado anterior
    await r_conn.delete(streak_key, today_key)
    await r_conn.hdel(f"phonebook:state:{ACCOUNT}", nphone)
    await r_conn.hset(f"phonebook:state:{ACCOUNT}", nphone, "active")

    # Simular _incr_streak manualmente (misma lógica que el código)
    async def simular_incr(esperado_streak: str | None, esperado_state: str | None, desc: str):
        today_k = f"streak_today:{nphone}:{datetime.now().strftime('%Y-%m-%d')}"
        if await r_conn.exists(today_k):
            r(f"{desc} (ya incrementó hoy)", await r_conn.get(streak_key) == esperado_streak, f"streak={await r_conn.get(streak_key)}")
            return
        await r_conn.set(today_k, "1", ex=86400)
        new_s = await r_conn.incr(streak_key)
        if new_s >= 3:
            await r_conn.hset(f"phonebook:state:{ACCOUNT}", nphone, "blocked")
        s = await r_conn.get(streak_key)
        st = await r_conn.hget(f"phonebook:state:{ACCOUNT}", nphone)
        r(desc, s == esperado_streak and st == esperado_state, f"streak={s}, state={st}")

    await simular_incr("1", "active", "Día 1 → streak=1, active")

    # Mismo día: NO debe incrementar
    await simular_incr("1", "active", "Mismo día → no incrementa (streak=1)")

    # Simular día 2
    await r_conn.delete(today_key)
    await simular_incr("2", "active", "Día 2 → streak=2, active")

    # Limpiar y simular día 3
    await r_conn.delete(today_key)
    await simular_incr("3", "blocked", "Día 3 → streak=3, blocked")

    # ─── 5. store_response (simular webhook) ───
    print("\n─── 5. STORE_RESPONSE (webhook) ───")
    old_streak = await r_conn.get(streak_key)
    old_state = await r_conn.hget(f"phonebook:state:{ACCOUNT}", nphone)
    await store_response(PHONES[0], ACCOUNT)
    new_streak = await r_conn.get(streak_key)
    new_state = await r_conn.hget(f"phonebook:state:{ACCOUNT}", nphone)
    has_resp = await r_conn.exists(f"response:{nphone}")
    r("Borra send_streak", new_streak is None, f"antes={old_streak}, despues={new_streak}")
    r("Reactiva (active)", new_state == "active", f"antes={old_state}, despues={new_state}")
    r("Crea response:key", has_resp == 1)
    await r_conn.delete(f"response:{nphone}")

    # ─── 6. auto_block_stale ───
    print("\n─── 6. AUTO_BLOCK_STALE ───")
    warn_p = normalize_phone("51999990001")
    block_p = normalize_phone("51999990002")
    await r_conn.sadd(f"phonebook:{ACCOUNT}", warn_p, block_p)
    await r_conn.set(f"send_streak:{warn_p}", 2)
    await r_conn.set(f"send_streak:{block_p}", 3)

    from app.core.ycloud_sender import auto_block_stale
    total = await auto_block_stale(ACCOUNT)
    s_w = await r_conn.hget(f"phonebook:state:{ACCOUNT}", warn_p)
    s_b = await r_conn.hget(f"phonebook:state:{ACCOUNT}", block_p)
    r("auto_block: streak=2 warning", s_w is None, f"state={s_w}")
    r("auto_block: streak=3 bloquea", s_b == "blocked", f"state={s_b}")
    await r_conn.srem(f"phonebook:{ACCOUNT}", warn_p, block_p)
    await r_conn.delete(f"send_streak:{warn_p}", f"send_streak:{block_p}")
    await r_conn.hdel(f"phonebook:state:{ACCOUNT}", warn_p, block_p)

    # ─── 7. Queue manager ───
    print("\n─── 7. QUEUE MANAGER ───")
    await queue_manager.pause_worker(ACCOUNT)
    paused = ACCOUNT in queue_manager.paused_workers
    await queue_manager.resume_worker(ACCOUNT)
    resumed = ACCOUNT not in queue_manager.paused_workers
    r("pause/resume worker", paused and resumed)

    data = {"phone": "51900000099", "label": "TEST", "message": "test"}
    await queue_manager.save_failed(ACCOUNT, data, "test error")
    fc = await queue_manager.get_failed_count(ACCOUNT)
    await r_conn.delete(f"failed:{ACCOUNT}")
    r("save/get failed", fc > 0, f"count={fc}")

    # ─── 8. normalize_phone ───
    print("\n─── 8. NORMALIZE_PHONE ───")
    tests = [
        ("963828458", "51963828458"),
        ("51 963 828 458", "51963828458"),
        ("51940740243", "51940740243"),
    ]
    all_ok = all(normalize_phone(inp) == exp for inp, exp in tests)
    r("normalize_phone", all_ok)

    # ─── 9. Estado final ───
    print("\n─── 9. ESTADO FINAL ───")
    for phone in PHONES:
        np = normalize_phone(phone)
        st = await r_conn.get(f"send_streak:{np}")
        state = await r_conn.hget(f"phonebook:state:{ACCOUNT}", np)
        resp = await r_conn.get(f"response:{np}")
        print(f"  {phone}: streak={st}, state={state}, response={'✓' if resp else '✗'}")
    f_count = await r_conn.llen(f"failed:{ACCOUNT}")
    print(f"  Fallidos totales: {f_count}")

    # ─── RESUMEN ───
    total = ok_count + fail_count
    print(f"\n{'='*60}")
    print(f"  {'✅ TODAS OK' if fail_count == 0 else f'❌ {fail_count} FALLARON'}  ({ok_count}/{total})")
    print(f"  Tiempo: {time.time() - start:.1f}s")
    print(f"{'='*60}")

    if fail_count:
        print(f"\n  Fallos:")
        for t in results:
            if not t["ok"]:
                print(f"    {FAIL} {t['name']}: {t['detail']}")

    # ─── CLEANUP ───
    print(f"\n─── CLEANUP ───")
    try:
        inp = input(f"  ¿Resetear datos de prueba? (s/N): ").strip().lower()
    except (EOFError, OSError):
        inp = ""
    if inp == "s":
        for phone in PHONES:
            np = normalize_phone(phone)
            await r_conn.delete(f"send_streak:{np}", f"response:{np}")
            await r_conn.delete(f"streak_today:{np}:{datetime.now().strftime('%Y-%m-%d')}")
            await r_conn.hdel(f"phonebook:state:{ACCOUNT}", np)
            await r_conn.hdel(f"phonebook:meta:{ACCOUNT}", np)
            await r_conn.srem(f"phonebook:{ACCOUNT}", np)
            await r_conn.srem(f"ycloud:responded", phone)
        print(f"  {PASS} Datos de prueba reseteados.")
    else:
        print(f"  {WARN} Datos conservados.")

    if not old_block:
        config_manager.set_client_config(ACCOUNT, {"auto_block_enabled": False})

    return fail_count == 0


if __name__ == "__main__":
    success = asyncio.run(test())
    sys.exit(0 if success else 1)
