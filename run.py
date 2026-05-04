import sys
import os
import threading
import asyncio
import time

# Priorizar la carpeta src actual
base_path = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(base_path, "src")
sys.path.insert(0, src_path)

try:
    import app.main as main_module
    from app.ui.app import run_gui_app
    from app.core.browser_manager import browser_manager
    from app.utils.logger import logger
except ImportError as e:
    print(f"❌ Error de importación: {e}")
    sys.exit(1)

if __name__ == "__main__":
    # 1. Hilo de Playwright
    t_playwright = threading.Thread(target=main_module.run_async_loop, daemon=True)
    t_playwright.start()
    
    # 2. Hilo de API
    t_api = threading.Thread(target=main_module.run_server, daemon=True)
    t_api.start()

    # ESPERA DE SEGURIDAD: Aguardar a que el loop esté listo
    logger.info("Inicializando motores...")
    max_wait = 50
    while main_module.playwright_loop is None and max_wait > 0:
        time.sleep(0.1)
        max_wait -= 1
    
    if main_module.playwright_loop is None:
        logger.error("No se pudo inicializar el motor Playwright.")
        sys.exit(1)

    # VINCULAR EL LOOP AL GESTOR DE COLAS
    from app.core.queue_manager import queue_manager
    queue_manager.set_main_loop(main_module.playwright_loop)

    logger.info("Sistema listo. Abriendo interfaz...")
    
    try:
        # 3. GUI (Hilo principal)
        run_gui_app(main_module.playwright_loop)
    except Exception as e:
        logger.error(f"Error en la GUI: {e}")
    finally:
        logger.info("Cerrando sistema...")
        if main_module.playwright_loop:
            asyncio.run_coroutine_threadsafe(browser_manager.shutdown(), main_module.playwright_loop)
        
        time.sleep(1)
        os._exit(0)
