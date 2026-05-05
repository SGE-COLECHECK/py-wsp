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
        # Intentamos varios iconos comunes de nuevo chat
        new_chat_btn = page.locator('button[aria-label*="chat"], [data-icon="new-chat-outline"], [data-icon="chat"]').first
        await new_chat_btn.wait_for(state="visible", timeout=8000)
        await new_chat_btn.click()
        await asyncio.sleep(1.5)

        # PASO 2: Nuevo Contacto (Hacer clic en la fila del menú)
        logger.info(f"[{account}] [ADD 2/6] Buscando opción 'Nuevo contacto' en la lista...")
        # En tu captura es una fila que dice "Nuevo contacto"
        new_contact_row = page.get_by_text("Nuevo contacto", exact=False).first
        await new_contact_row.wait_for(state="visible", timeout=5000)
        await new_contact_row.click()
        await asyncio.sleep(2)

        # PASO 3: Rellenar Nombre
        logger.info(f"[{account}] [ADD 3/6] Rellenando campo de nombre...")
        # El primer cuadro editable en el modal de contacto es siempre el Nombre
        name_field = page.locator('div[contenteditable="true"]').first
        await name_field.wait_for(state="visible", timeout=8000)
        await name_field.click()
        await asyncio.sleep(0.5)
        await page.keyboard.press("Control+A")
        await page.keyboard.press("Backspace")
        await page.keyboard.type(name, delay=60)
        await asyncio.sleep(0.5)

        # PASO 4: Rellenar Teléfono
        logger.info(f"[{account}] [ADD 4/6] Rellenando campo de teléfono...")
        # Intentamos encontrar el input que está después del texto "Teléfono"
        phone_field = page.locator('div').filter(has_text=re.compile(r"^Teléfono$")).locator('..').locator('input').first
        if not await phone_field.count():
            # Fallback 2: El último input de tipo texto dentro del diálogo
            phone_field = page.locator('div[role="dialog"] input[type="text"]').last
        
        await phone_field.wait_for(state="visible", timeout=5000)
        await phone_field.click(force=True)
        await asyncio.sleep(0.5)
        await phone_field.fill(phone)
        await asyncio.sleep(1)

        # PASO 5: Switch Sincronizar
        logger.info(f"[{account}] [ADD 5/6] Verificando switch de sincronización...")
        sync_switch = page.locator('[role="checkbox"], [role="switch"], .x10l6tqk.x13vifvy').last
        try:
            await sync_switch.wait_for(state="attached", timeout=3000)
            await sync_switch.click()
            await asyncio.sleep(1)
        except:
            logger.warn(f"[{account}] ⚠️ Switch no encontrado, saltando...")

        # PASO 6: Guardar Contacto
        logger.info(f"[{account}] [ADD 6/6] Guardando contacto y validando...")
        # En WhatsApp Business, a veces el botón es un icono o dice "Guardar"
        save_selectors = [
            'div[role="button"]:has-text("Guardar")',
            'div[role="button"][aria-label*="Guardar"]',
            'div[role="button"] [data-icon="checkmark"]',
            'div[role="button"] [data-icon="check"]',
            'span:has-text("Guardar")',
            'button:has-text("Guardar")'
        ]
        
        save_btn = None
        for sel in save_selectors:
            btn = page.locator(sel).first
            if await btn.count() > 0:
                save_btn = btn
                break
        
        if not save_btn:
             # Último recurso: El botón que esté más a la derecha en la cabecera del modal
             save_btn = page.locator('div[role="dialog"] div[role="button"]').last

        await save_btn.wait_for(state="visible", timeout=5000)
        
        if data.get("dry_run"):
            logger.warn(f"[{account}] 🧪 MODO DRY-RUN: Simulado, omitiendo clic en 'Guardar'.")
        else:
            await save_btn.click()
            await asyncio.sleep(2)

        logger.success(f"[{account}] ✅ Contacto procesado: {name} ({phone})")

        # PASO 7: Cerrar
        try:
            await page.keyboard.press("Escape")
            await asyncio.sleep(0.5)
        except: pass

    except Exception as e:
        logger.error(f"[{account}] ❌ Error al añadir contacto {name}: {str(e)}")
        # Tomar captura de pantalla para diagnóstico
        try:
            os.makedirs("data/errors", exist_ok=True)
            path = f"data/errors/add_contact_{account}_{int(time.time())}.png"
            await page.screenshot(path=path)
            logger.info(f"[{account}] 📸 Captura de error guardada en: {path}")
            # Loggear el HTML del modal para ver los nombres de los campos
            modal_html = await page.locator('div[role="dialog"]').inner_html()
            logger.info(f"[{account}] 📄 Estructura del modal capturada para análisis.")
        except: pass
        
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
            
            if data.get("dry_run"):
                logger.warn(f"[{account}] 🧪 MODO DRY-RUN: Simulado exitosamente, omitiendo 'Enter'.")
            else:
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
