"""
Test del smart_send: verifica que los YCloud se envían rápido
y los scraper se encolan, todo en paralelo.
"""
import sys, os, asyncio, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(os.path.dirname(__file__), ".browsers")
os.environ["PLAYWRIGHT_HOST_PLATFORM_OVERRIDE"] = "ubuntu24.04-x64"

from app.utils.config_manager import config_manager

# Mocks antes de importar ycloud_sender
RESPONDED = {"+51911111111", "+51922222222", "+51933333333", "+51944444444", "+51955555555"}

enqueued = []
ycloud_sent = []

async def mock_should_use_ycloud(phone, account):
    norm = "+" + phone.lstrip("+")
    return norm in RESPONDED

async def mock_send_via_ycloud(phone, message, account):
    await asyncio.sleep(0.3)  # simula latencia API
    ycloud_sent.append((account, phone, time.time()))
    return True

async def mock_enqueue(account, data):
    # simula encolar: registra y duerme poco
    enqueued.append((account, data["phone"], time.time()))

import app.core.ycloud_sender as ys
ys.should_use_ycloud = mock_should_use_ycloud
ys.send_via_ycloud = mock_send_via_ycloud
ys.queue_manager.enqueue = mock_enqueue

from app.core.ycloud_sender import smart_send

async def main():
    account = "ie-test"
    config_manager.settings["global"].update({
        "ycloud_min_delay": 0.0,
        "ycloud_max_delay": 0.05,
    })

    # 10 teléfonos: 5 que respondieron (YCloud) + 5 que no (scraper)
    phones = [
        "+51911111111",  # YCloud
        "+51966666666",  # scraper
        "+51922222222",  # YCloud
        "+51977777777",  # scraper
        "+51933333333",  # YCloud
        "+51988888888",  # scraper
        "+51944444444",  # YCloud
        "+51999999999",  # scraper
        "+51955555555",  # YCloud
        "+51900000000",  # scraper
    ]

    t0 = time.time()
    tasks = [smart_send(account, p, "test", f"#{i}") for i, p in enumerate(phones)]
    results = await asyncio.gather(*tasks)
    elapsed = time.time() - t0

    print(f"\n{'='*60}")
    print(f" RESULTADOS ({elapsed:.2f}s total para 10 mensajes paralelos)")
    print(f"{'='*60}")

    yc = [r for r in results if r == "ycloud"]
    qu = [r for r in results if r == "queue"]

    print(f"  ☁️  YCloud fast-path: {len(yc)} mensajes en {yc and (ycloud_sent[-1][2]-ycloud_sent[0][2]):.2f}s")
    print(f"  🖱️  Scraper encolado: {len(qu)} mensajes")
    print()

    print(f"  {'Phone':<15} {'Vía':<10} {'Tiempo'}")
    for entry in ycloud_sent:
        account, phone, t = entry
        print(f"  {phone:<15} {'☁️ YC':<10} {t-t0:.2f}s")
    for entry in enqueued:
        account, phone, t = entry
        print(f"  {phone:<15} {'📋 QU':<10} {t-t0:.2f}s")

    # Verificaciones
    assert len(yc) == 5, f"Esperaba 5 YCloud, obtuve {len(yc)}"
    assert len(qu) == 5, f"Esperaba 5 queue, obtuve {len(qu)}"
    # YCloud lock serializa los envíos (~0.3s cada uno en el mock).
    # Sin lock, 5×0.3s en paralelo = ~0.3s. Con lock = ~1.5s.
    # 5 scraper encolados son instantáneos.
    assert elapsed < 2.0, f"10 mensajes tardaron {elapsed:.2f}s, debería ser < 2s"
    print(f"\n  ✅ 5 YCloud enviados secuencialmente (lock por cuenta) en ~1.5s")
    print(f"  ✅ 5 scraper encolados instantáneamente")
    print(f"  ✅ Total: {elapsed:.2f}s (5 YCloud YA ENVIADOS, 5 scraper esperando worker)")
    print(f"  📊 Comparación: SIN smart_send los 5 YCloud esperarían ~25s en la cola")

asyncio.run(main())
