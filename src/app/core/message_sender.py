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
    
    logger.info(f"Añadiendo contacto: {name} ({phone})", account=account)
    
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
        max_wait = 10.0
        poll_interval = 0.5
        elapsed = 0.0
        
        logger.debug("[ADD 5/7] Validando número en WhatsApp...", account=account)
        await asyncio.sleep(2.5)
        
        while elapsed < max_wait:
            # PRIORIDAD 1: ¿SÍ está en WhatsApp? (Si vemos el switch o el mensaje positivo)
            has_whatsapp_msg = await page.get_by_text("está en WhatsApp", exact=False).is_visible()
            has_sync_text = await page.get_by_text("Sincronizar contacto con el teléfono").is_visible()
            switch_exists = await page.locator('div.x1c4vz4f.xs83m0k.xdl72j9.x1g77sc7.xeuugli.x2lwn1j.xozqiw3.x1oa3qoh.x12fk4p8.xymharo, [role="switch"]').count() > 0
            
            if has_whatsapp_msg or has_sync_text or switch_exists:
                # Si el mensaje dice "está en WhatsApp" pero NO dice "no está", entonces es positivo
                if not await page.get_by_text("no está en WhatsApp", exact=True).is_visible():
                    phone_status = "whatsapp"
                    break

            # PRIORIDAD 2: ¿Ya existe?
            if await page.get_by_text("ya está en tus contactos").is_visible():
                phone_status = "duplicate"
                break
            
            # PRIORIDAD 3: ¿Realmente NO está? (Usamos exact=True para evitar confusiones)
            if await page.get_by_text("no está en WhatsApp", exact=True).is_visible():
                await asyncio.sleep(1.5)
                if await page.get_by_text("no está en WhatsApp", exact=True).is_visible():
                    phone_status = "not_on_whatsapp"
                    break
            
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval
        
        logger.debug(f"[ADD 5/7] Estado detectado: {phone_status} (en {elapsed:.1f}s)", account=account)
        
        # === Manejar casos que NO se guardan ===
        
        if phone_status == "duplicate":
            logger.warn(f"{phone} ya existe en contactos. Cancelando.", account=account)
            await page.keyboard.press("Escape")
            await asyncio.sleep(0.3)
            await page.keyboard.press("Escape")
            return
        
        if phone_status == "not_on_whatsapp":
            logger.warn(f"{phone} NO esta en WhatsApp. No se guardara.", account=account)
            await page.keyboard.press("Escape")
            await asyncio.sleep(0.3)
            await page.keyboard.press("Escape")
            return
        
        if phone_status == "whatsapp":
            # Activar switch de sincronización
            logger.debug("[ADD 6/7] Activando switch de sincronización...", account=account)
            try:
                # Intentar con el selector específico proporcionado y fallback de role="switch"
                sync_switch = page.locator('div.x1c4vz4f.xs83m0k.xdl72j9.x1g77sc7.xeuugli.x2lwn1j.xozqiw3.x1oa3qoh.x12fk4p8.xymharo, [role="switch"]').first
                sw_count = await sync_switch.count()
                logger.debug(f"[ADD 6/7] Switches encontrados: {sw_count}", account=account)
                
                if sw_count > 0:
                    await sync_switch.wait_for(state="visible", timeout=5000)
                    is_checked = await sync_switch.get_attribute("aria-checked")
                    logger.info(f"[ADD 6/7] Estado del switch: {is_checked}", account=account)
                    
                    if is_checked != "true":
                        logger.info(f"[ADD 6/7] ESPERANDO 3 SEGUNDOS antes de activar sincronizacion...", account=account)
                        await asyncio.sleep(1); logger.info("3...", account=account)
                        await asyncio.sleep(1); logger.info("2...", account=account)
                        await asyncio.sleep(1); logger.info("1...", account=account)
                        
                        logger.info("[ADD 6/7] Haciendo CLIC en el switch de sincronizacion...", account=account)
                        await sync_switch.click()
                        logger.success("[ADD 6/7] Switch activado con exito", account=account)
                        await asyncio.sleep(2)
                    else:
                        logger.info("[ADD 6/7] El switch ya estaba activado, saltando clic.", account=account)
                else:
                    # Fallback: buscar por JavaScript cualquier elemento que parezca toggle
                    logger.debug("[ADD 6/7] Esperando 3s antes de activar sync (fallback)...", account=account)
                    await asyncio.sleep(3)
                    await page.evaluate('''() => {
                        const switches = document.querySelectorAll('[role="switch"], [role="checkbox"]');
                        if (switches.length > 0) switches[switches.length - 1].click();
                    }''')
                    await asyncio.sleep(2)
            except Exception as sync_err:
                logger.warn(f"No se pudo activar sync: {sync_err}", account=account)
        else:
            logger.info(f"Numero {phone} nuevo (sin WhatsApp detectado). Guardando.", account=account)

        # PASO 7: Guardar Contacto
        # El botón tiene: data-testid="save-contact-btn" aria-label="Guardar contacto"
        # Tarda unos segundos en aparecer después de activar sync
        logger.debug("[ADD 7/7] Esperando botón guardar...", account=account)
        
        if data.get("dry_run"):
            logger.warn("MODO DRY-RUN: Simulado, omitiendo guardar.", account=account)
        else:
            # Selectores: data-testid, aria-label, el botón circular negro con check (span > div > span), o por icono
            save_btn = page.locator('[data-testid="save-contact-btn"], [aria-label="Guardar contacto"], [aria-label="Guardar"], div[role="button"] span[data-icon="check"], div[role="button"] span[data-icon="checkmark"]')
            
            # Fallback para el botón circular negro de la imagen
            if await save_btn.count() == 0:
                save_btn = page.locator('div[role="button"]:has(span[data-icon="check"]), div[role="button"]:has(span[data-icon="checkmark"]), #side ~ div div[role="button"] span').last
            
            saved = False
            
            # INTENTO 1: Esperar hasta 10 segundos a que aparezca el botón
            try:
                logger.info("[ADD 7/7] Buscando boton 'Guardar'...", account=account)
                await save_btn.wait_for(state="visible", timeout=10000)
                
                logger.info("[ADD 7/7] BOTON ENCONTRADO. Esperando 3 segundos de seguridad...", account=account)
                await asyncio.sleep(1); logger.info("3...", account=account)
                await asyncio.sleep(1); logger.info("2...", account=account)
                await asyncio.sleep(1); logger.info("1...", account=account)
                
                logger.info("[ADD 7/7] Presionando boton GUARDAR...", account=account)
                await save_btn.click()
                logger.success("[ADD 7/7] Boton guardar presionado", account=account)
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
                    logger.debug("[ADD 7/7] Intento 2: clic forzado", account=account)
                    await asyncio.sleep(2)
                    
                    still_in_form = await page.get_by_text("Nuevo contacto", exact=True).is_visible()
                    if not still_in_form:
                        saved = True
                except Exception as e2:
                    logger.warn(f"[ADD 7/7] Intento 2 falló: {e2}", account=account)
            
            if not saved:
                logger.warn(f"No se pudo guardar {name} ({phone}). Escapando.", account=account)
                await page.keyboard.press("Escape")
                await asyncio.sleep(0.5)
                await page.keyboard.press("Escape")
                await asyncio.sleep(0.3)
                elapsed_total = time.time() - start_time
                logger.warn(f"Abandonado en {elapsed_total:.2f}s", account=account)
                return

        elapsed_total = time.time() - start_time
        logger.success(f"Contacto guardado: {name} ({phone}) en {elapsed_total:.2f}s", account=account)

        # Cerrar panel si quedó abierto
        try:
            await page.keyboard.press("Escape")
            await asyncio.sleep(0.3)
        except: pass

    except Exception as e:
        logger.error(f"Error al anadir contacto {name}: {str(e)}", account=account)
        try:
            os.makedirs("data/errors", exist_ok=True)
            path = f"data/errors/add_contact_{account}_{int(time.time())}.png"
            await page.screenshot(path=path)
            logger.info(f"Captura de error: {path}", account=account)
        except: pass
        
        try:
            await page.keyboard.press("Escape")
            await asyncio.sleep(0.3)
        except: pass
        raise e

async def send_report_task(account: str, data: dict):
    phone = data.get("phone", "")
    message = data.get("message", "")

    if not phone or not message:
        logger.error("Datos insuficientes", account=account)
        return

    formatted_phone = re.sub(r'[\s\-\(\)]', '', str(phone))
    if not formatted_phone.startswith('51'):
        formatted_phone = '51' + formatted_phone

    from app.core.queue_manager import queue_manager
    from app.core.ycloud_sender import normalize_phone

    async def _do_send() -> bool:
        start_task_time = time.time()
        try:
            logger.sending(f"Enviando a {formatted_phone}...", account=account)
            page = await browser_manager.get_page(account)

            if "web.whatsapp.com" not in page.url:
                await page.goto("https://web.whatsapp.com")

            await page.wait_for_selector("#side", timeout=20000)

            await page.keyboard.press("Escape")
            await asyncio.sleep(0.1)

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
                logger.error(f"No se encontró el buscador. Captura: {path}")
                raise e

            await search_box.click()
            await asyncio.sleep(0.05)
            await page.keyboard.press("Control+A")
            await page.keyboard.press("Backspace")
            await asyncio.sleep(0.05)

            search_start = time.time()
            await search_box.type(formatted_phone, delay=25)
            search_delay = config_manager.get_global("search_delay", 2.0)
            await asyncio.sleep(search_delay)
            await page.keyboard.press("Enter")

            await asyncio.sleep(1.5)
            t_search = time.time() - search_start

            dialog_info = await page.evaluate('''() => {
                const dialogs = document.querySelectorAll('[role="dialog"]');
                if (dialogs.length > 0) {
                    return { type: "dialog", text: dialogs[0].innerText.substring(0, 300) };
                }
                const body = document.body.innerText;
                const keywords = [
                    'no se encontró ningún chat', 'no se encontraron',
                    'no está registrado en WhatsApp', 'invitar a WhatsApp',
                    'invite to WhatsApp'
                ];
                for (const kw of keywords) {
                    if (body.toLowerCase().includes(kw)) {
                        return { type: "body", text: kw };
                    }
                }
                return null;
            }''')

            if dialog_info:
                reason = dialog_info["text"][:120]
                logger.warn(f"Numero {formatted_phone} no disponible: {reason}", account=account)
                await page.keyboard.press("Escape")
                return True

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
            except:
                logger.warn("Probando selectores alternativos...", account=account)
                try:
                    fallback_selectors = [
                        'footer div.lexical-rich-text-input [contenteditable="true"]',
                        '[aria-label*="escribe un mensaje"]',
                        '[aria-label*="Type a message"]',
                        '[aria-label*="mensaje"]'
                    ]
                    msg_box = await page.wait_for_selector(", ".join(fallback_selectors), timeout=5000)
                except:
                    raise Exception("No se encontró el cuadro de mensaje.")

            await msg_box.click()
            await asyncio.sleep(0.05)

            await page.keyboard.press("Control+A")
            await asyncio.sleep(0.05)
            await page.keyboard.press("Backspace")
            await asyncio.sleep(0.05)

            typing_start = time.time()

            send_mode = config_manager.get_global("send_mode", "typing")

            if send_mode == "paste":
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
                await asyncio.sleep(0.1)
            else:
                typing_delay = config_manager.get_global("typing_delay", 10)
                lines = message.split('\n')
                for i, line in enumerate(lines):
                    if len(line) > 0:
                        await page.keyboard.type(line, delay=typing_delay)
                    if i < len(lines) - 1:
                        await page.keyboard.press("Shift+Enter")

            t_typing = time.time() - typing_start
            t_prep = search_start - start_task_time
            label = data.get("label", "MENSAJE")
            total_prep = time.time() - start_task_time

            logger.info(f"{label} | Prep: {t_prep:.2f}s | Busq: {t_search:.2f}s | Escr: {t_typing:.2f}s | Total: {total_prep:.2f}s", account=account)

            pre_min = config_manager.get_global("pre_send_min", 1.0)
            pre_max = config_manager.get_global("pre_send_max", 3.0)
            pre_delay = random.uniform(pre_min, pre_max)

            if data.get("dry_run"):
                logger.warn(f"DRY-RUN: OK (delay {pre_delay:.1f}s omitido)", account=account)
            else:
                await asyncio.sleep(pre_delay)
                await page.keyboard.press("Enter")
                await asyncio.sleep(0.1)
                logger.read(f"Enviado a {formatted_phone} (delay: {pre_delay:.1f}s)", account=account)
                logger.increment_sent(account)

            await page.keyboard.press("Escape")

            total_time = time.time() - start_task_time
            logger.info(f"Tarea completada exitosamente en {total_time:.2f}s", account=account)
            return True
        except Exception as e:
            logger.warn(f"Error en envío: {str(e)[:200]}", account=account)
            raise

    is_warning = data.get("is_warning", False)

    try:
        ok = await _do_send()
        if ok and not is_warning:
            r = await queue_manager.get_redis()
            if r:
                nphone = normalize_phone(formatted_phone)
                new_streak = await r.incr(f"send_streak:{nphone}")
                logger.info(f"send_streak:{nphone} → {new_streak}", account=account)
    except Exception as e:
        logger.warn(f"Intento 1 falló para {phone}, recuperando...", account=account)
        await queue_manager.pause_worker(account)
        logger.info(f"Cola de {account} PAUSADA para recovery", account=account)
        try:
            page = await browser_manager.get_page(account)
            await page.reload()
            logger.info(f"Página recargada, esperando #side...", account=account)
            await page.wait_for_selector("#side", timeout=35000)
            await asyncio.sleep(5)
        except Exception as reload_err:
            logger.error(f"Error en recarga: {reload_err}", account=account)
        await queue_manager.resume_worker(account)
        logger.info(f"Cola de {account} REANUDADA, intento 2...", account=account)
        try:
            ok2 = await _do_send()
            if ok2 and not is_warning:
                r = await queue_manager.get_redis()
                if r:
                    nphone = normalize_phone(formatted_phone)
                    new_streak = await r.incr(f"send_streak:{nphone}")
                    logger.info(f"send_streak:{nphone} → {new_streak}", account=account)
        except Exception as e2:
            logger.error(f"Intento 2 falló para {phone}: {e2}", account=account)
            os.makedirs("data/errors", exist_ok=True)
            ss_path = ""
            try:
                page = await browser_manager.get_page(account)
                ss_path = f"data/errors/fail_{account}_{phone}_{int(time.time())}.png"
                await page.screenshot(path=ss_path)
            except:
                pass
            await queue_manager.save_failed(account, data, str(e2), ss_path)
            logger.error(f"Fallo definitivo para {phone}", account=account)
            cfg = config_manager.get_client_config(account)
            if cfg.get("admin_alerts", False):
                admin_phone = config_manager.get_global("admin_phone", "51963828458")
                admin_msg = f"⚠️ ERROR [{account}]\nNo se pudo enviar a {phone}\n{e2}"
                await queue_manager.enqueue(account, {
                    "phone": admin_phone,
                    "message": admin_msg,
                    "label": "ADMIN ALERT",
                    "type": "message",
                    "is_alert": True,
                })

async def process_queue_item(account: str, data: dict):
    """Enrutador de tareas dependiendo del tipo."""
    task_type = data.get("type", "message")

    if task_type == "add_contact":
        await add_contact_task(account, data)
    elif task_type == "message":
        phone = data.get("phone", "")
        from app.core.ycloud_sender import send_via_ycloud, should_use_ycloud
        if await should_use_ycloud(phone, account):
            sent = await send_via_ycloud(phone, data.get("message", ""), account)
            if sent:
                logger.increment_sent(account)
                return
            logger.warn("YCloud falló, usando scraper", account=account)
        await send_report_task(account, data)
    else:
        logger.error(f"Tipo de tarea desconocido: {task_type}", account=account)

# Alias para mantener compatibilidad con el resto del código si algo lo llamaba directamente
send_message = process_queue_item
