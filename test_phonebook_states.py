"""
Test del sistema de estados del phonebook (active/inactive/blocked).
"""
import sys, os, asyncio, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(os.path.dirname(__file__), ".browsers")
os.environ["PLAYWRIGHT_HOST_PLATFORM_OVERRIDE"] = "ubuntu24.04-x64"

# Mocks
fake_redis_data = {
    "phonebook:state:test-client": {},
    "phonebook:meta:test-client": {
        "519111": "2026-05-30T10:00:00",  # 5 días atrás
        "519222": "2026-06-03T10:00:00",  # hoy
        "519333": "2026-05-30T10:00:00",  # 5 días atrás, pero respondió
    },
    "phonebook:test-client": {"519111", "519222", "519333"},
    "response:519333": str(time.time()),
}

class FakeRedis:
    def __init__(self, data):
        self.data = data
    async def hgetall(self, k): return dict(self.data.get(k, {}))
    async def hget(self, k, f): return self.data.get(k, {}).get(f)
    async def hset(self, k, f=None, v=None, **kw):
        if f is not None:
            self.data.setdefault(k, {})[f] = v
    async def smembers(self, k): return set(self.data.get(k, set()))
    async def sadd(self, k, *vals):
        s = self.data.setdefault(k, set())
        added = 0
        for v in vals:
            if v not in s:
                s.add(v); added += 1
        return added
    async def get(self, k):
        v = self.data.get(k)
        return v if v is not None else None
    async def ping(self): return True

import app.core.ycloud_sender as ys
ys.queue_manager.get_redis = lambda: _async_return(FakeRedis(fake_redis_data))

async def _async_return(v):
    return v

from app.core.ycloud_sender import (
    get_phone_state, set_phone_state, deactivate_phone,
    reactivate_phone, block_phone, auto_deactivate_stale,
    should_skip_phone,
)
from app.utils.config_manager import config_manager

async def main():
    # Reset state
    fake_redis_data["phonebook:state:test-client"] = {}

    print("="*60)
    print(" TEST: Phonebook states")
    print("="*60)

    # 1. Estado inicial = active
    s = await get_phone_state("test-client", "519111")
    print(f" 1. 519111 estado inicial: {s}")
    assert s == "active"

    # 2. Desactivar
    await deactivate_phone("test-client", "519111")
    s = await get_phone_state("test-client", "519111")
    print(f" 2. 519111 después deactivate: {s}")
    assert s == "inactive"

    # 3. Bloquear otro
    await block_phone("test-client", "519222")
    s = await get_phone_state("test-client", "519222")
    print(f" 3. 519222 después block: {s}")
    assert s == "blocked"

    # 4. Reactivar
    await reactivate_phone("test-client", "519111")
    s = await get_phone_state("test-client", "519111")
    print(f" 4. 519111 después reactivate: {s}")
    assert s == "active"

    # 5. should_skip_phone con block_inactive=False
    config_manager.set_client_config("test-client", {
        "ycloud_enabled": True, "block_inactive": False,
    })
    skip = await should_skip_phone("test-client", "+519222")
    print(f" 5. should_skip(+519222, block_inactive=False): {skip}")
    assert skip is False

    # 6. should_skip_phone con block_inactive=True
    config_manager.set_client_config("test-client", {
        "ycloud_enabled": True, "block_inactive": True,
    })
    skip = await should_skip_phone("test-client", "+519222")
    print(f" 6. should_skip(+519222, block_inactive=True): {skip}")
    assert skip is True

    skip = await should_skip_phone("test-client", "+519111")  # active
    print(f" 7. should_skip(+519111, block_inactive=True): {skip}")
    assert skip is False

    # 8. Auto-deactivate con days=3
    # Reset
    fake_redis_data["phonebook:state:test-client"] = {}
    # 519111 first_seen = 5 días atrás, no respondió → DEBE desactivarse
    # 519222 first_seen = hoy → NO se desactiva
    # 519333 first_seen = 5 días atrás pero SÍ respondió → NO se desactiva
    config_manager.set_client_config("test-client", {"ycloud_enabled": True})
    n = await auto_deactivate_stale("test-client", 3)
    print(f" 8. auto_deactivate_stale(days=3) desactivó: {n}")
    assert n == 1, f"Esperaba 1 (solo 519111), obtuvo {n}"
    s111 = await get_phone_state("test-client", "519111")
    s222 = await get_phone_state("test-client", "519222")
    s333 = await get_phone_state("test-client", "519333")
    print(f"    519111 (5d sin resp): {s111}  ← debe ser inactive")
    print(f"    519222 (hoy): {s222}  ← debe ser active")
    print(f"    519333 (5d pero respondió): {s333}  ← debe ser active")
    assert s111 == "inactive"
    assert s222 == "active"
    assert s333 == "active"

    # 9. Auto-deactivate con days=0 (desactivado)
    fake_redis_data["phonebook:state:test-client"] = {}
    n = await auto_deactivate_stale("test-client", 0)
    print(f" 9. auto_deactivate_stale(days=0) desactivó: {n} (debe ser 0)")
    assert n == 0

    # 10. Auto-deactivate sin YCloud
    config_manager.set_client_config("test-client", {"ycloud_enabled": False})
    fake_redis_data["phonebook:state:test-client"] = {}
    n = await auto_deactivate_stale("test-client", 3)
    print(f"10. auto_deactivate_stale(ycloud_disabled) desactivó: {n} (debe ser 0)")
    assert n == 0

    print("\n" + "="*60)
    print(" ✅ TODOS LOS TESTS PASARON")
    print("="*60)

asyncio.run(main())
