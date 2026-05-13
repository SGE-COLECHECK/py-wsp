import os
import time
import asyncio
import re
import random
from app.utils.logger import logger
from app.core.browser_manager import browser_manager
from app.utils.config_manager import config_manager

async def add_contact_task(account: str, data: dict):
    phone = data.get("phone", "")
    name = data.get("name", "")
    start_time = time.time()
    
    logger.info(f"👤 Añadiendo contacto: {name} ({phone})", account=account)
    
    page = await browser_manager.get_page(account)
    if "web.whatsapp.com" not in page.url:
        await page.goto("https://web.whatsapp.com")
    
    await page.wait_for_selector("#side", timeout=60000)

    try:
        # PASO 1: Nuevo Chat
        logger.debug("[ADD 1/7] Abriendo 'Nuevo chat'...", account=account)
        new_chat_btn = page.locator('button[aria-label*="chat"], [data-icon="new-chat-outline"], [data-icon="chat"]').first
        await new_chat_btn.wait_for(state="visible", timeout=8000)
        await new_chat_btn.click()
        await asyncio.sleep(1)

        # PASO 2: Nuevo Contacto
        logger.debug("[ADD 2/7] Seleccionando 'Nuevo contacto'...", account=account)
        new_contact_row = page.get_by_text("Nuevo contacto", exact=False).first
        await new_contact_row.wait_for(state="visible", timeout=5000)
        await new_contact_row.click()
        await asyncio.sleep(1.5)

        # PASO 3: Rellenar Nombre
        logger.debug(f"[ADD 3/7] Escribiendo nombre: {name}", account=account)
        name_field = page.locator('div[contenteditable="true"]').first
        await name_field.wait_for(state="visible", timeout=8000)
        await name_field.click()
        await asyncio.sleep(0.3)
        await page.keyboard.press("Control+A")
        await page.keyboard.press("Backspace")
        await page.keyboard.type(name, delay=50)
        await asyncio.sleep(0.3)

        # PASO 4: Rellenar Teléfono
        logger.debug(f"[ADD 4/7] Escribiendo teléfono: {phone}", account=account)
        phone_field = page.locator('div').filter(has_text=re.compile(r"^Teléfono$")).locator('..').locator('input').first
        if not await phone_field.count():
            # Fallback: buscar cualquier input de texto visible en el panel
            phone_field = page.locator('input[type="text"]').last
        
        await phone_field.wait_for(state="visible", timeout=5000)
        await phone_field.click(force=True)
        await asyncio.sleep(0.3)
        await phone_field.fill(phone)

        # PASO 5: Esperar respuesta de WhatsApp con polling inteligente
        # WhatsApp puede mostrar 4 estados tras ingresar el número:
        #   A) "ya está en tus contactos" → CANCELAR
        #   B) "no está en WhatsApp" → CANCELAR (no guardar)
        #   C) "Sincronizar contacto con el teléfono" (tiene WhatsApp) → SYNC + GUARDAR
        #   D) Ningún mensaje especial → solo GUARDAR
        logger.debug("[ADD 5/7] Esperando respuesta de WhatsApp...", account=account)
        
        phone_status = "new"
        max_wait = 5.0
        poll_interval = 0.4
        elapsed = 0.0
        
        await asyncio.sleep(0.8)
        
        while elapsed < max_wait:
            # Caso A: Ya existe en contactos
            already_in_contacts = await page.get_by_text("ya está en tus contactos").is_visible()
            if already_in_contacts:
                phone_status = "duplicate"
                break
            
            # Caso B: No está en WhatsApp
            not_on_whatsapp = await page.get_by_text("no está en WhatsApp").is_visible()
            if not_on_whatsapp:
                phone_status = "not_on_whatsapp"
                break
            
            # Caso C: Tiene WhatsApp - buscar el texto o el switch
            has_whatsapp_text = await page.get_by_text("Sincronizar contacto con el teléfono").is_visible()
            if has_whatsapp_text:
                phone_status = "whatsapp"
                break
            
            # También buscar el switch directamente
            switch_count = await page.locator('[role="switch"]').count()
            if switch_count > 0:
                phone_status = "whatsapp"
                break
            
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval
        
        logger.debug(f"[ADD 5/7] Estado detectado: {phone_status} (en {elapsed:.1f}s)", account=account)
        
        # === Manejar casos que NO se guardan ===
        
        if phone_status == "duplicate":
            logger.warn(f"⚠️ {phone} ya existe en contactos. Cancelando.", account=account)
            await page.keyboard.press("Escape")
            await asyncio.sleep(0.3)
            await page.keyboard.press("Escape")
            return
        
        if phone_status == "not_on_whatsapp":
            logger.warn(f"⚠️ {phone} NO está en WhatsApp. No se guardará.", account=account)
            await page.keyboard.press("Escape")
            await asyncio.sleep(0.3)
            await page.keyboard.press("Escape")
            return
        
        if phone_status == "whatsapp":
            # Activar switch de sincronización
            logger.debug("[ADD 6/7] Activando switch de sincronización...", account=account)
            try:
                # Intentar con role="switch"
                sync_switch = page.locator('[role="switch"]').first
                sw_count = await sync_switch.count()
                logger.debug(f"[ADD 6/7] Switches encontrados: {sw_count}", account=account)
                
                if sw_count > 0:
                    await sync_switch.wait_for(state="visible", timeout=3000)
                    is_checked = await sync_switch.get_attribute("aria-checked")
                    logger.debug(f"[ADD 6/7] Switch aria-checked: {is_checked}", account=account)
                    
                    if is_checked != "true":
                        await sync_switch.click()
                        logger.debug("[ADD 6/7] ✅ Switch clickeado", account=account)
                        await asyncio.sleep(0.5)
                    else:
                        logger.debug("[ADD 6/7] Switch ya estaba activado", account=account)
                else:
                    # Fallback: buscar por JavaScript cualquier elemento que parezca toggle
                    logger.debug("[ADD 6/7] Intentando fallback JS para switch...", account=account)
                    await page.evaluate('''() => {
                        const switches = document.querySelectorAll('[role="switch"], [role="checkbox"]');
                        if (switches.length > 0) switches[switches.length - 1].click();
                    }''')
                    await asyncio.sleep(0.5)
            except Exception as sync_err:
                logger.warn(f"⚠️ No se pudo activar sync: {sync_err}", account=account)
        else:
            logger.info(f"🆕 Número {phone} nuevo (sin WhatsApp detectado). Guardando.", account=account)

        # PASO 7: Guardar Contacto
        # El botón tiene: data-testid="save-contact-btn" aria-label="Guardar contacto"
        # Tarda unos segundos en aparecer después de activar sync
        logger.debug("[ADD 7/7] Esperando botón guardar...", account=account)
        
        if data.get("dry_run"):
            logger.warn("🧪 MODO DRY-RUN: Simulado, omitiendo guardar.", account=account)
        else:
            save_btn = page.locator('[data-testid="save-contact-btn"]')
            saved = False
            
            # INTENTO 1: Esperar hasta 6 segundos a que aparezca el botón
            try:
                await save_btn.wait_for(state="visible", timeout=6000)
                logger.debug("[ADD 7/7] Botón visible. Esperando 3s para asegurar guardado...", account=account)
                await asyncio.sleep(3)
                await save_btn.click()
                logger.debug("[ADD 7/7] ✅ Intento 1: clic en save-contact-btn", account=account)
                await asyncio.sleep(3)
                
                still_in_form = await page.get_by_text("Nuevo contacto", exact=True).is_visible()
                if not still_in_form:
                    saved = True
            except Exception as e1:
                logger.warn(f"[ADD 7/7] Intento 1 falló: {e1}", account=account)
            
            # INTENTO 2: Esperar 3s más e intentar de nuevo
            if not saved:
                logger.debug("[ADD 7/7] Aún en formulario. Esperando 3s para intento 2...", account=account)
                await asyncio.sleep(3)
                try:
                    await save_btn.click(force=True)
                    logger.debug("[ADD 7/7] ✅ Intento 2: clic forzado", account=account)
                    await asyncio.sleep(2)
                    
                    still_in_form = await page.get_by_text("Nuevo contacto", exact=True).is_visible()
                    if not still_in_form:
                        saved = True
                except Exception as e2:
                    logger.warn(f"[ADD 7/7] Intento 2 falló: {e2}", account=account)
            
            if not saved:
                logger.warn(f"⚠️ No se pudo guardar {name} ({phone}). Escapando.", account=account)
                await page.keyboard.press("Escape")
                await asyncio.sleep(0.5)
                await page.keyboard.press("Escape")
                await asyncio.sleep(0.3)
                elapsed_total = time.time() - start_time
                logger.warn(f"⏱️ Abandonado en {elapsed_total:.2f}s", account=account)
                return

        elapsed_total = time.time() - start_time
        logger.success(f"✅ Contacto guardado: {name} ({phone}) en {elapsed_total:.2f}s", account=account)

        # Cerrar panel si quedó abierto
        try:
            await page.keyboard.press("Escape")
            await asyncio.sleep(0.3)
        except: pass

    except Exception as e:
        logger.error(f"❌ Error al añadir contacto {name}: {str(e)}", account=account)
        try:
            os.makedirs("data/errors", exist_ok=True)
            path = f"data/errors/add_contact_{account}_{int(time.time())}.png"
            await page.screenshot(path=path)
            logger.info(f"📸 Captura de error: {path}", account=account)
        except: pass
        
        try:
            await page.keyboard.press("Escape")
            await asyncio.sleep(0.3)
        except: pass
        raise e

async def send_report_task(account: str, data: dict):
    start_task_time = time.time()
    phone = data.get("phone", "")
    message = data.get("message", "")
    
    if not phone or not message:
        logger.error("Datos insuficientes", account=account)
        return

    formatted_phone = re.sub(r'[\s\-\(\)]', '', str(phone))
    if not formatted_phone.startswith('51'):
        formatted_phone = '51' + formatted_phone

    for attempt in range(1, 3):
        try:
            logger.sending(f"Enviando a {formatted_phone}...", account=account)
            page = await browser_manager.get_page(account)
            
            if "web.whatsapp.com" not in page.url:
                await page.goto("https://web.whatsapp.com")
            
            await page.wait_for_selector("#side", timeout=60000)

            # Limpiar cualquier popup o modal que haya quedado abierto
            await page.keyboard.press("Escape")
            await asyncio.sleep(0.2)

            # --- PASO 1: Buscar el cuadro de búsqueda ---
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
            
            try:
                search_box = await page.wait_for_selector(", ".join(search_selectors), timeout=15000)
            except Exception as e:
                os.makedirs("data/errors", exist_ok=True)
                path = f"data/errors/search_fail_{account}_{int(time.time())}.png"
                await page.screenshot(path=path)
                logger.error(f"❌ No se encontró el buscador. Captura: {path}")
                raise e
            
            # Clic + limpiar lo que haya escrito antes
            await search_box.click()
            await asyncio.sleep(0.1)
            await page.keyboard.press("Control+A")
            await page.keyboard.press("Backspace")
            await asyncio.sleep(0.1)

            # --- PASO 2 ---
            search_start = time.time()
            await search_box.type(formatted_phone, delay=25) 
            await page.keyboard.press("Enter")

            # --- PASO 3 ---
            # Espera humana para que cargue el chat
            await asyncio.sleep(0.5) 
            t_search = time.time() - search_start
            
            no_whatsapp_found = await page.evaluate('''() => {
                const text = document.body.innerText;
                return text.includes('No se encontró ningún chat, contacto ni mensaje') || 
                       text.includes('No se encontraron') || 
                       text.includes('Este número no está registrado en WhatsApp') || 
                       text.includes('Invitar a WhatsApp') || 
                       text.includes('Invite to WhatsApp');
            }''')

            if no_whatsapp_found:
                logger.warn(f"⚠️ Número {formatted_phone} no tiene WhatsApp o no se encontró.", account=account)
                await page.keyboard.press("Escape")
                return

            # --- PASO 4 ---
            # logger.debug("[PASO 4] Buscando el cuadro de mensaje...", account=account)
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
                # logger.debug("[PASO 4] ✅ Selector principal encontrado", account=account)
            except:
                logger.warn("⚠️ Probando selectores alternativos...", account=account)
                try:
                    fallback_selectors = [
                        'footer div.lexical-rich-text-input [contenteditable="true"]',
                        '[aria-label*="escribe un mensaje"]',
                        '[aria-label*="Type a message"]',
                        '[aria-label*="mensaje"]'
                    ]
                    msg_box = await page.wait_for_selector(", ".join(fallback_selectors), timeout=5000)
                    # logger.debug("[PASO 4] ✅ Selector alternativo encontrado", account=account)
                except:
                    raise Exception("No se encontró el cuadro de mensaje.")

            await msg_box.click()
            await asyncio.sleep(0.1)
            
            # --- PASO 4.5 ---
            await page.keyboard.press("Control+A")
            await asyncio.sleep(0.05)
            await page.keyboard.press("Backspace")
            await asyncio.sleep(0.05)

            # --- PASO 5: Escribir mensaje ---
            typing_start = time.time()
            
            send_mode = config_manager.get_global("send_mode", "typing")
            
            if send_mode == "paste":
                # MODO PASTE: Copiar y pegar instantáneo
                await page.evaluate('''(text) => {
                    const dt = new DataTransfer();
                    dt.setData("text/plain", text);
                    const pasteEvent = new ClipboardEvent("paste", {
                        clipboardData: dt,
                        bubbles: true,
                        cancelable: true
                    });
                    document.activeElement.dispatchEvent(pasteEvent);
                }''', message)
                await asyncio.sleep(0.2)
            else:
                # MODO TYPING: Teclear letra por letra
                typing_delay = config_manager.get_global("typing_delay", 10)
                lines = message.split('\n')
                for i, line in enumerate(lines):
                    if len(line) > 0:
                        await page.keyboard.type(line, delay=typing_delay)
                    if i < len(lines) - 1:
                        await page.keyboard.press("Shift+Enter")

            # logger.debug("✅ Mensaje escrito.", account=account)
            t_typing = time.time() - typing_start
            t_prep = search_start - start_task_time
            label = data.get("label", "MENSAJE")
            total_prep = time.time() - start_task_time
            
            logger.info(f"⏱️ {label} | ⚙️ Prep: {t_prep:.2f}s | 🔍 Búsq: {t_search:.2f}s | ⌨️ Escr: {t_typing:.2f}s | 🚀 Total: {total_prep:.2f}s", account=account)

            # --- PASO 6: Enviar ---
            pre_min = config_manager.get_global("pre_send_min", 1.0)
            pre_max = config_manager.get_global("pre_send_max", 3.0)
            pre_delay = random.uniform(pre_min, pre_max)
            
            if data.get("dry_run"):
                logger.warn(f"🧪 DRY-RUN: OK (delay {pre_delay:.1f}s omitido)", account=account)
            else:
                await asyncio.sleep(pre_delay)
                await page.keyboard.press("Enter")
                await asyncio.sleep(0.3)
                logger.read(f"Enviado a {formatted_phone} (delay: {pre_delay:.1f}s)", account=account)
                logger.increment_sent(account)
            
            await page.keyboard.press("Escape")
            # logger.debug("[PASO 6] Chat cerrado.", account=account)
            
            total_time = time.time() - start_task_time
            logger.info(f"🏁 Tarea completada exitosamente en {total_time:.2f}s", account=account)
            return

        except Exception as e:
            logger.error(f"❌ Error en intento {attempt}: {str(e)}", account=account)
            if attempt == 1:
                await asyncio.sleep(5)
            else:
                logger.error(f"Fallo definitivo para {phone}", account=account)

async def process_queue_item(account: str, data: dict):
    """Enrutador de tareas dependiendo del tipo."""
    task_type = data.get("type", "message")
    
    if task_type == "add_contact":
        await add_contact_task(account, data)
    elif task_type == "message":
        await send_report_task(account, data)
    else:
        logger.error(f"❌ Tipo de tarea desconocido: {task_type}", account=account)

# Alias para mantener compatibilidad con el resto del código si algo lo llamaba directamente
send_message = process_queue_item
