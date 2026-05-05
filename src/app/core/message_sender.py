import asyncio
import re
import random
from app.utils.logger import logger
from app.core.browser_manager import browser_manager

async def add_contact_task(account: str, data: dict):
    phone = data.get("phone", "")
    name = data.get("name", "")
    
    logger.info(f"[{account}] === INICIANDO TAREA ESPECIAL: Añadir Contacto ===")
    logger.info(f"[{account}] 📞 Nombre: {name} | Teléfono: {phone}")
    
    page = await browser_manager.get_page(account)
    if "web.whatsapp.com" not in page.url:
        await page.goto("https://web.whatsapp.com")
    
    await page.wait_for_selector("#side", timeout=60000)

    try:
        # PASO 1: Nuevo Chat
        logger.info(f"[{account}] [ADD 1/6] Buscando botón 'Nuevo chat'...")
        new_chat_btn = page.locator('button[aria-label="Nuevo chat"], button[aria-label*="Nuevo chat"], span[data-icon="new-chat-outline"]').first
        await new_chat_btn.wait_for(state="visible", timeout=5000)
        await new_chat_btn.click()
        await asyncio.sleep(1)

        # PASO 2: Nuevo Contacto
        logger.info(f"[{account}] [ADD 2/6] Buscando opción 'Nuevo contacto'...")
        new_contact_span = page.locator('span').filter(has_text="Nuevo contacto").first
        await new_contact_span.wait_for(state="visible", timeout=5000)
        await new_contact_span.click()
        await asyncio.sleep(1.5)

        # PASO 3: Rellenar Nombre
        logger.info(f"[{account}] [ADD 3/6] Rellenando campo de nombre...")
        name_field = page.locator('p[dir="auto"].copyable-text, p._aupe.copyable-text').first
        await name_field.wait_for(state="visible", timeout=5000)
        await name_field.click()
        await asyncio.sleep(0.2)
        await page.keyboard.press("Control+A")
        await page.keyboard.press("Backspace")
        await page.keyboard.type(name, delay=50)
        await asyncio.sleep(0.5)

        # PASO 4: Rellenar Teléfono
        logger.info(f"[{account}] [ADD 4/6] Rellenando campo de teléfono...")
        phone_field = page.locator('input[type="text"][aria-label*="Número de teléfono"], input[type="text"][aria-label*="Phone"]').first
        await phone_field.wait_for(state="visible", timeout=5000)
        await phone_field.click()
        await asyncio.sleep(0.2)
        await page.keyboard.press("Control+A")
        await page.keyboard.press("Backspace")
        await page.keyboard.type(phone, delay=50)
        await asyncio.sleep(2)

        # PASO 5: Switch Sincronización
        logger.info(f"[{account}] [ADD 5/6] Verificando switch de sincronización...")
        sync_switch = page.locator('input#sync-contact-switch[role="switch"], input[role="switch"][aria-label*="Sincronizar"]').first
        try:
            await sync_switch.wait_for(state="attached", timeout=3000)
            is_checked = await sync_switch.evaluate("el => el.getAttribute('aria-checked') === 'true'")
            if not is_checked:
                await sync_switch.click()
                await asyncio.sleep(1)
        except:
            logger.warn(f"[{account}] ⚠️ Switch no encontrado o no visible, continuando...")

        # PASO 6: Guardar Contacto
        logger.info(f"[{account}] [ADD 6/6] Guardando contacto y validando...")
        save_btn = page.locator('div[role="button"][aria-label="Guardar contacto"], div[role="button"][aria-label*="Guardar"]').first
        await save_btn.wait_for(state="visible", timeout=10000)
        await save_btn.click()
        await asyncio.sleep(1.5)

        logger.success(f"[{account}] ✅ Contacto añadido exitosamente: {name} ({phone})")

        # PASO 7: Cerrar
        logger.info(f"[{account}] Cerrando formulario...")
        await page.keyboard.press("Escape")
        await asyncio.sleep(0.5)

    except Exception as e:
        logger.error(f"[{account}] ❌ Error al añadir contacto {name}: {str(e)}")
        try:
            await page.keyboard.press("Escape")
            await asyncio.sleep(0.5)
        except: pass
        raise e

async def send_report_task(account: str, data: dict):
    phone = data.get("phone", "")
    message = data.get("message", "")
    
    if not phone or not message:
        logger.error(f"[{account}] Datos insuficientes")
        return

    formatted_phone = re.sub(r'[\s\-\(\)]', '', str(phone))
    if not formatted_phone.startswith('51'):
        formatted_phone = '51' + formatted_phone

    for attempt in range(1, 3):
        try:
            logger.info(f"[{account}] === INICIANDO ENVÍO A {formatted_phone} (Intento {attempt}) ===")
            page = await browser_manager.get_page(account)
            
            if "web.whatsapp.com" not in page.url:
                await page.goto("https://web.whatsapp.com")
            
            await page.wait_for_selector("#side", timeout=60000)

            # --- PASO 1 ---
            logger.info(f"[{account}] [PASO 1] Buscando y limpiando el cuadro de búsqueda...")
            search_selectors = [
                'div[contenteditable="true"][data-tab="3"]',
                'div[contenteditable="true"][title*="búsqueda"]',
                'div[contenteditable="true"][title*="Buscar"]',
                'div[contenteditable="true"][aria-label*="Buscar"]',
                '#side div[role="textbox"]',
                '#side [role="textbox"]',
                '#side div[contenteditable="true"]',
                '#side [contenteditable="true"]',
                'div.lexical-rich-text-input [role="textbox"]',
                '[aria-label*="Buscar o empezar"]',
                '[aria-label*="Busca un chat"]',
                '[aria-label*="Search"]'
            ]
            
            search_box = None
            try:
                search_box = await page.wait_for_selector(", ".join(search_selectors), timeout=15000)
            except:
                raise Exception("No se encontró el cuadro de búsqueda.")

            await search_box.click()
            await asyncio.sleep(0.2)
            await search_box.click(click_count=3)
            await asyncio.sleep(0.05)
            await page.keyboard.press("Backspace")
            logger.info(f"[{account}] [PASO 1] ✅ Cuadro de búsqueda limpio.")

            # --- PASO 2 ---
            logger.info(f"[{account}] [PASO 2] Escribiendo el número y presionando Enter: {formatted_phone}")
            await search_box.type(formatted_phone, delay=50) 
            await page.keyboard.press("Enter")

            # --- PASO 3 ---
            logger.info(f"[{account}] [PASO 3] Verificando si se abrió el chat...")
            await asyncio.sleep(random.uniform(0.5, 1.5))
            
            no_whatsapp_found = await page.evaluate('''() => {
                const text = document.body.innerText;
                return text.includes('No se encontró ningún chat, contacto ni mensaje') || 
                       text.includes('No se encontraron') || 
                       text.includes('Este número no está registrado en WhatsApp') || 
                       text.includes('Invitar a WhatsApp') || 
                       text.includes('Invite to WhatsApp');
            }''')

            if no_whatsapp_found:
                logger.warn(f"⚠️ [{account}] Número {formatted_phone} no tiene WhatsApp o no se encontró.")
                await page.keyboard.press("Escape")
                return

            # --- PASO 4 ---
            logger.info(f"[{account}] [PASO 4] Buscando el cuadro de mensaje...")
            msg_selectors = [
                'div[contenteditable="true"][data-tab="10"]',
                'footer div[contenteditable="true"]',
                'footer [role="textbox"]',
                '#main div[contenteditable="true"]',
                '#main [role="textbox"]'
            ]
            
            msg_box = None
            try:
                msg_box = await page.wait_for_selector(", ".join(msg_selectors), timeout=5000)
                logger.info(f"[{account}] [PASO 4] ✅ Selector principal encontrado")
            except:
                logger.warn(f"[{account}] ⚠️ Probando selectores alternativos...")
                try:
                    fallback_selectors = [
                        'footer div.lexical-rich-text-input [contenteditable="true"]',
                        '[aria-label*="escribe un mensaje"]',
                        '[aria-label*="Type a message"]',
                        '[aria-label*="mensaje"]'
                    ]
                    msg_box = await page.wait_for_selector(", ".join(fallback_selectors), timeout=5000)
                    logger.info(f"[{account}] [PASO 4] ✅ Selector alternativo encontrado")
                except:
                    raise Exception("No se encontró el cuadro de mensaje.")

            await msg_box.click()
            await asyncio.sleep(0.2)
            logger.info(f"[{account}] [PASO 4] ✅ Cuadro de mensaje activo.")

            # --- PASO 4.5 ---
            logger.info(f"[{account}] [PASO 4.5] Limpiando borradores...")
            await page.keyboard.press("Control+A")
            await asyncio.sleep(0.05)
            await page.keyboard.press("Backspace")
            await asyncio.sleep(0.05)

            # --- PASO 5 ---
            logger.info(f"[{account}] [PASO 5] Escribiendo el mensaje de forma fluida...")
            lines = message.split('\n')
            typing_delay = 15 
            
            for i, line in enumerate(lines):
                if len(line) > 0:
                    await page.keyboard.type(line, delay=typing_delay)
                if i < len(lines) - 1:
                    await page.keyboard.press("Shift+Enter")
                    
            logger.info(f"[{account}] [PASO 5] ✅ Mensaje escrito.")

            # --- PASO 6 ---
            await asyncio.sleep(0.1)
            logger.info(f"[{account}] [PASO 6] Enviando mensaje...")
            await page.keyboard.press("Enter")
            
            await asyncio.sleep(0.5)
            logger.success(f"[{account}] ✅ Mensaje enviado a {formatted_phone}.")
            
            await page.keyboard.press("Escape")
            logger.info(f"[{account}] [PASO 6] Chat cerrado.")
            return

        except Exception as e:
            logger.error(f"[{account}] ❌ Error en intento {attempt}: {str(e)}")
            if attempt == 1:
                await asyncio.sleep(5)
            else:
                logger.error(f"🚨 [{account}] Fallo definitivo para {phone}")

async def process_queue_item(account: str, data: dict):
    """Enrutador de tareas dependiendo del tipo."""
    task_type = data.get("type", "message")
    
    if task_type == "add_contact":
        await add_contact_task(account, data)
    elif task_type == "message":
        await send_report_task(account, data)
    else:
        logger.error(f"[{account}] ❌ Tipo de tarea desconocido: {task_type}")

# Alias para mantener compatibilidad con el resto del código si algo lo llamaba directamente
send_message = process_queue_item
