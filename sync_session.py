import asyncio
from playwright.async_api import async_playwright
import os

async def sync():
    async with async_playwright() as p:
        # Asegurar que el directorio de sesiones existe
        os.makedirs("sessions", exist_ok=True)
        storage_path = "sessions/whatsapp_session.json"
        
        print("\n🚀 Iniciando navegador para sincronización...")
        
        # Abrimos el navegador visible
        browser = await p.chromium.launch(headless=False)
        
        # Si ya existe una sesión, la cargamos para verificarla o actualizarla
        context_args = {}
        if os.path.exists(storage_path):
            context_args["storage_state"] = storage_path
            
        context = await browser.new_context(**context_args)
        page = await context.new_page()
        
        await page.goto("https://web.whatsapp.com")
        
        print("\n⚠️  POR FAVOR: Escanea el código QR en la ventana del navegador.")
        print("El script esperará a que veas tus chats antes de guardar y cerrar.")
        
        # Esperamos a que aparezca el sidebar (indicativo de login exitoso)
        try:
            # Damos 2 minutos para escanear
            await page.wait_for_selector("#side", timeout=120000)
            print("\n✅ ¡Login detectado con éxito!")
            
            # Guardamos el estado de la sesión
            await context.storage_state(path=storage_path)
            print(f"💾 Sesión guardada en: {storage_path}")
            
            # Pequeña espera para asegurar guardado
            await asyncio.sleep(2)
            
        except Exception as e:
            print(f"\n❌ Error o tiempo de espera agotado: {e}")
        
        finally:
            await browser.close()
            print("\n👋 Navegador cerrado. Ya puedes iniciar la API con 'python main.py'")

if __name__ == "__main__":
    asyncio.run(sync())
