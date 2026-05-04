import asyncio
import random
import os
from datetime import datetime
from playwright.async_api import Page, TimeoutError
from session_manager import session_manager
from logger_manager import logger

async def human_delay(min_ms=500, max_ms=1500):
    await asyncio.sleep(random.randint(min_ms, max_ms) / 1000)

async def send_report(account: str, data: dict):
    page: Page = await session_manager.get_page_for_account(account)
    phone = data.get("telefono_padre")
    
    try:
        logger.log(f"Iniciando reporte para {account} -> Destino: {phone}")
        
        # 1. Asegurar sidebar
        await page.wait_for_selector("#side", timeout=30000)
        
        # 2. Localizar buscador y limpiar
        search_box = await page.wait_for_selector('#side [role="textbox"]', timeout=5000)
        await search_box.click()
        await page.keyboard.press("Control+A")
        await page.keyboard.press("Backspace")
        
        # 3. Escribir número y presionar Enter
        await search_box.fill(phone)
        await page.keyboard.press("Enter")
        logger.log(f"Buscando {phone}...")
        await human_delay(2000, 3000)

        # 4. Verificar si el chat ya se abrió (por el Enter) o buscarlo
        # Miramos si el nombre del chat aparece en el encabezado principal (#main)
        header_text = ""
        try:
            header_text = await page.inner_text("#main header")
        except: pass

        if phone in header_text or (len(header_text) > 0 and not "haga clic" in header_text.lower()):
            logger.log("Chat detectado automáticamente.")
        else:
            # Si no se abrió solo, buscamos el resultado en el sidebar
            logger.log("Buscando resultado en la lista...")
            try:
                # Buscamos cualquier listitem que no sea el buscador
                results = page.locator('#side [role="listitem"]')
                # Hacemos clic en el primero que encontremos de los resultados
                await results.nth(1).click() # El 0 suele ser el buscador o el perfil
                await human_delay(1000, 1500)
            except:
                # Último recurso: clic por coordenadas debajo del buscador
                bbox = await search_box.bounding_box()
                await page.mouse.click(bbox["x"] + 50, bbox["y"] + 100)
                await human_delay(1000, 1500)

        # 5. Escribir reporte
        msg = (
            f"🎓 Estudiante: {data['nombre_alumno']}\n"
            f"🆔 DNI: {data['dni']}\n"
            f"👨‍👩‍👧 Padre: {data['nombre_padre']}\n"
            f"🏫 Grado/Sec: {data['grado']} \"{data['seccion']}\"\n"
            f"🕒 Hora: {data['timestamp']}\n"
            f"📍 Ubicación: {data['ubicacion']}\n"
            f"📢 Asistencia: {data['type_asistance']}"
        )

        # Buscar caja de mensaje
        msg_box = await page.wait_for_selector('footer [role="textbox"]', timeout=10000)
        await msg_box.click()
        
        # Escribir mensaje
        lines = msg.split('\n')
        for i, line in enumerate(lines):
            await page.keyboard.type(line)
            if i < len(lines) - 1:
                await page.keyboard.down("Shift")
                await page.keyboard.press("Enter")
                await page.keyboard.up("Shift")
        
        await human_delay(500, 1000)
        await page.keyboard.press("Enter")
        
        logger.log(f"✅ Reporte enviado con éxito a {phone}", "SUCCESS")
        
        # Limpiar para la siguiente búsqueda
        await page.keyboard.press("Escape")
        return {"status": "success", "message": "Enviado"}

    except Exception as e:
        logger.log(f"Error enviando reporte a {phone}: {str(e)}", "ERROR")
        return {"status": "error", "message": str(e)}
