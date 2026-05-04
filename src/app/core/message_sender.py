import asyncio
from app.utils.logger import logger
from app.core.browser_manager import browser_manager

async def send_report_task(account: str, data: dict):
    phone = data.get("phone")
    message = data.get("message")
    
    if not phone or not message:
        logger.error(f"[{account}] Datos insuficientes")
        return

    for attempt in range(1, 3):
        try:
            logger.info(f"[{account}] === INICIANDO ENVÍO A {phone} (Intento {attempt}) ===")
            page = await browser_manager.get_page(account)
            
            logger.info(f"[{account}] Paso 1: Verificando URL...")
            if "web.whatsapp.com" not in page.url:
                await page.goto("https://web.whatsapp.com")
            
            logger.info(f"[{account}] Paso 2: Esperando carga principal (#side)...")
            await page.wait_for_selector("#side", timeout=60000)

            logger.info(f"[{account}] Paso 3: Buscando barra de búsqueda...")
            search_box = None
            for selector in [
                'div[contenteditable="true"][data-tab="3"]',
                '#side [role="textbox"]',
                '[aria-label*="Buscar"]',
                '[aria-label*="Search"]'
            ]:
                try:
                    search_box = await page.wait_for_selector(selector, timeout=3000)
                    if search_box:
                        logger.info(f"[{account}] > Selector encontrado: {selector}")
                        break
                except: continue
            
            if not search_box:
                raise Exception("No se encontró la barra de búsqueda")

            logger.info(f"[{account}] Paso 4: Limpiando buscador...")
            await search_box.click()
            await search_box.click(click_count=3)
            await page.keyboard.press("Backspace")
            
            logger.info(f"[{account}] Paso 5: Escribiendo número de teléfono...")
            await search_box.type(phone, delay=100)
            await asyncio.sleep(3)

            logger.info(f"[{account}] Paso 6: Validando resultados en el panel lateral...")
            # Nos limitamos a #pane-side para no detectar headers sueltos del menú
            chat_locator = page.locator('#pane-side [role="listitem"], #pane-side [role="row"], #pane-side [role="button"]').first
            
            try:
                await chat_locator.wait_for(state="visible", timeout=5000)
                logger.info(f"[{account}] > Resultado encontrado y visible.")
            except:
                logger.warn(f"⚠️ [{account}] NO hay resultados para {phone}. Cancelando envío.")
                await page.keyboard.press("Escape")
                return 

            logger.info(f"[{account}] Paso 7: Abriendo chat (Navegación por teclado)...")
            # En lugar de un click ciego, forzamos el foco al buscador y usamos las teclas nativas de WhatsApp
            await search_box.focus()
            await page.keyboard.press("ArrowDown") # Salta al primer resultado REAL
            await asyncio.sleep(0.5)
            await page.keyboard.press("Enter") # Abre el chat
            await asyncio.sleep(2) # Dar tiempo a que el chat cargue a la derecha

            logger.info(f"[{account}] Paso 8: Buscando caja de mensaje...")
            msg_box = None
            for selector in [
                'div[contenteditable="true"][data-tab="10"]',
                '#main [role="textbox"]',
                'footer [contenteditable="true"]',
                '#main div[contenteditable="true"]'
            ]:
                try:
                    msg_box = await page.wait_for_selector(selector, timeout=3000)
                    if msg_box:
                        logger.info(f"[{account}] > Caja de mensaje encontrada: {selector}")
                        break
                except: continue

            if not msg_box:
                raise Exception("No se encontró la caja de mensaje")

            logger.info(f"[{account}] Paso 9: Escribiendo mensaje...")
            await msg_box.click()
            lines = message.split('\n')
            for i, line in enumerate(lines):
                if line:
                    await page.keyboard.insert_text(line)
                if i < len(lines) - 1:
                    await page.keyboard.press("Shift+Enter")

            logger.info(f"[{account}] Paso 10: Enviando mensaje (Enter)...")
            await page.keyboard.press("Enter")
            
            logger.info(f"[{account}] Paso 11: Cerrando chat (Escape)...")
            await asyncio.sleep(1)
            await page.keyboard.press("Escape")
            
            logger.success(f"[{account}] ✅ Mensaje enviado exitosamente a {phone}")
            return

        except Exception as e:
            logger.error(f"[{account}] ❌ Error en intento {attempt}: {str(e)}")
            if attempt == 1:
                await asyncio.sleep(5)
            else:
                logger.error(f"🚨 [{account}] Fallo definitivo para {phone}")

send_message = send_report_task
