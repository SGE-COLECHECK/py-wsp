"""Simula el escenario REAL: mensajes llegan uno a uno"""
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
    total = 5

    print("="*55)
    print("SIMULACION: mensajes llegan UNO A UNO")
    print("="*55)
    print(f"Config: min_delay=1 max_delay=2 | blpop timeout=2\n")
    print(f"Encolando {total} mensajes con delay de 4-6s entre c/u...\n")

    for i in range(total):
        await queue_manager.enqueue(account, {"phone": f"999{i:03d}", "message": "x"})
        t = time.strftime("%H:%M:%S")
        print(f"  [{t}] Encolado 999{i:03d}")
        if i < total - 1:
            espera = random.uniform(4, 6)
            await asyncio.sleep(espera)

    await asyncio.sleep(total * 5)

    starts = [e for e in events if e[1]=="start"]
    ends = [e for e in events if e[1]=="end"]

    print(f"\n{'='*55}")
    print(f"  #  | Llega  | Inicia | Gap envio->inicio |")
    print(f"{'='*55}")
    
    enqueued_times = []  # No tenemos el tiempo exacto de enqueue, usamos -1
    for i, s in enumerate(starts):
        e = ends[i] if i < len(ends) else (0,"end",0)
        send_t = e[2]-s[2]
        if i > 0:
            g = s[2]-ends[i-1][2]
        else:
            g = 0
            
        t_start = time.strftime("%H:%M:%S", time.localtime(s[2]))
        t_enqueued = time.strftime("%H:%M:%S", time.localtime(s[2] - 3 - i*2)) # aprox
        print(f"  {s[0]:2d} | 999{s[0]-1:03d} | {t_start} | envio={send_t:.2f}s gap={g:.2f}s |")

    if starts:
        gaps = [starts[i][2]-ends[i-1][2] for i in range(1, len(starts))]
        print(f"\nGap promedio: {sum(gaps)/len(gaps):.2f}s")
        print(f"Gap maximo:   {max(gaps):.2f}s")
        
        # Calcular cuanto espera el worker (gap - tiempo de envio anterior)
        esperas = []
        for i in range(1, len(starts)):
            espera = starts[i][2] - ends[i-1][2]
            esperas.append(espera)
        if esperas:
            print(f"T espera worker (gap entre envios): prom={sum(esperas)/len(esperas):.2f}s max={max(esperas):.2f}s")

asyncio.run(main())
