"""Runner headless: solo API + Playwright, sin GUI"""
import sys, os, threading, time, asyncio

if any(f in sys.argv for f in ("--linux", "--develop")):
    _local_browsers = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".browsers")
    if os.path.isdir(_local_browsers):
        os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", _local_browsers)
        os.environ.setdefault("PLAYWRIGHT_HOST_PLATFORM_OVERRIDE", "ubuntu24.04-x64")

base_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
sys.path.insert(0, base_path)

import app.main as main_module
from app.core.browser_manager import browser_manager
from app.utils.logger import logger
from app.core.queue_manager import queue_manager

if __name__ == "__main__":
    # Playwright thread
    t_playwright = threading.Thread(target=main_module.run_async_loop, daemon=True)
    t_playwright.start()

    # API thread
    t_api = threading.Thread(target=main_module.run_server, daemon=True)
    t_api.start()

    # Esperar loop
    logger.info("Inicializando motores...")
    max_wait = 50
    while main_module.playwright_loop is None and max_wait > 0:
        time.sleep(0.1)
        max_wait -= 1

    if main_module.playwright_loop is None:
        logger.error("No se pudo inicializar Playwright")
        sys.exit(1)

    queue_manager.set_main_loop(main_module.playwright_loop)
    logger.info("Sistema listo (headless). API en :3000")

    # Mantener vivo
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Cerrando...")
        if main_module.playwright_loop:
            asyncio.run_coroutine_threadsafe(browser_manager.shutdown(), main_module.playwright_loop)
        time.sleep(1)
        os._exit(0)
