"""Test timing del queue_manager"""
import sys, os, asyncio, time, random
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(os.path.dirname(__file__), ".browsers")
os.environ["PLAYWRIGHT_HOST_PLATFORM_OVERRIDE"] = "ubuntu24.04-x64"

from app.utils.config_manager import config_manager
config_manager.settings["global"].update({"min_delay":1,"max_delay":2,"batch_size":7,"batch_pause":0})

events = []
send_count = 0

async def mock_process(account, data):
    global send_count, events
    send_count += 1
    n = send_count
    t1 = time.time()
    events.append((n, "start", t1))
    await asyncio.sleep(random.uniform(1.5, 1.8))
    t2 = time.time()
    events.append((n, "end", t2))

import app.core.queue_manager as qm
qm.process_queue_item = mock_process
from app.core.queue_manager import queue_manager

async def main():
    loop = asyncio.get_event_loop()
    queue_manager.set_main_loop(loop)
    queue_manager.workers = {}
    queue_manager.batch_counters = {}
    await queue_manager.connect()
    if not queue_manager.is_connected:
        print("ERROR: Redis no conectado")
        return

    account = f"test-{int(time.time())}"
    total = 7

    print(f"min_delay={config_manager.get_global('min_delay')} max_delay={config_manager.get_global('max_delay')}")
    print(f"blpop timeout=2 (cambiado de 5)")
    print(f"Encolando {total} mensajes de golpe...\n")

    for i in range(total):
        await queue_manager.enqueue(account, {"phone": f"999{i:03d}", "message": "x"})

    await asyncio.sleep(total * 4)

    starts = [e for e in events if e[1]=="start"]
    ends = [e for e in events if e[1]=="end"]

    print("="*55)
    print("  #  | Teléfono | Envío | Gap ant |")
    print("="*55)
    gaps = []
    for i, s in enumerate(starts):
        e = ends[i] if i < len(ends) else (0,"end",0)
        send_t = e[2]-s[2]
        if i > 0:
            g = s[2]-ends[i-1][2]
            gaps.append(g)
        else:
            g = 0
        print(f"  {s[0]:2d} | 999{s[0]-1:03d}  | {send_t:.2f}s | {g:.2f}s  |")

    if gaps:
        print(f"\nGap promedio: {sum(gaps)/len(gaps):.2f}s")
        print(f"Gap maximo:   {max(gaps):.2f}s")
        print(f"Gap minimo:   {min(gaps):.2f}s")
        esperado_max = 2 + 2  # max_delay + timeout
        if max(gaps) > esperado_max + 1:
            print(f"\n⚠️ GAP ANORMAL > {esperado_max}s - Revisa queue_manager.py:105")
        else:
            print(f"\n✅ Gaps dentro de lo esperado (max_delay={config_manager.get_global('max_delay')} + timeout=2 = {esperado_max}s max)")

asyncio.run(main())
