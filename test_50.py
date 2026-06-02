"""50 mensajes - prueba directa del ciclo queue_manager"""
import sys, os, asyncio, time, random
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

import redis.asyncio as redis

async def main():
    r = redis.Redis(decode_responses=True)
    await r.ping()

    account = f"t{int(time.time())}"
    queue_key = f"queue:{account}"
    N = 50
    min_d = 1
    max_d = 2
    batch_size = 50
    batch_pause = 0

    # Encolar 50
    import json
    for i in range(N):
        await r.rpush(queue_key, json.dumps({"phone":f"999{i:04d}","message":"x"}))

    log = []
    print(f"{N} encolados. Procesando...\n")
    t_start = time.time()

    for i in range(N):
        t1 = time.time()
        # Simula envio: busca + escribe + envia = ~2.5s
        envio = random.uniform(2.0, 2.5)
        await asyncio.sleep(envio)
        t2 = time.time()

        log.append((envio, t1, t2))
        print(f"  [{i+1:2d}] envio={envio:.2f}s | total={t2-t_start:.1f}s")

        # Inter-delay (como queue_manager)
        if (i+1) % batch_size == 0:
            await asyncio.sleep(batch_pause)
        else:
            await asyncio.sleep(random.randint(min_d, max_d))

    total = time.time() - t_start
    print(f"\n--- RESULTADOS ---")
    print(f"50 mensajes en {total:.1f}s")
    print(f"Promedio: {total/50:.2f}s/msg")
    print(f"Msgs/min: {60/(total/50):.0f}")

    await r.delete(queue_key)
    await r.aclose()

asyncio.run(main())
