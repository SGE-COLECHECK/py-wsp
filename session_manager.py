import os
import json
import asyncio
from playwright.async_api import async_playwright, BrowserContext, Page
from logger_manager import logger

class SessionManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SessionManager, cls).__new__(cls)
            cls._instance.playwright = None
            cls._instance.contexts = {} 
            cls._instance.pages = {}    
            cls._instance.is_visible = {} 
            cls._instance.client_status = {} 
            cls._instance.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        return cls._instance

    async def init_playwright(self):
        if not self.playwright:
            logger.log("Iniciando motor Playwright...")
            self.playwright = await async_playwright().start()

    def get_status(self, name: str) -> str:
        return self.client_status.get(name, "OFFLINE")

    async def get_context_for_client(self, name: str, force_visible: bool = False) -> BrowserContext:
        if name in self.contexts:
            if force_visible and not self.is_visible.get(name, False):
                logger.log(f"Reiniciando '{name}' para hacerlo visible...", "WARN")
                await self.contexts[name].close()
                del self.contexts[name]
                if name in self.pages: del self.pages[name]
            else:
                return self.contexts[name]

        await self.init_playwright()
        self.client_status[name] = "STARTING"
        self.is_visible[name] = force_visible

        base_dir = os.path.dirname(os.path.abspath(__file__))
        user_data_dir = os.path.join(base_dir, "sessions", f"profile_{name}")
        os.makedirs(user_data_dir, exist_ok=True)

        mode = "VISIBLE" if force_visible else "INVISIBLE"
        logger.log(f"Lanzando navegador {mode} para '{name}'...")

        try:
            context = await self.playwright.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                headless=not force_visible,
                user_agent=self.user_agent,
                viewport={"width": 1280, "height": 720},
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
            )
            await context.route("**/*.{png,jpg,jpeg,gif,webp,svg}", lambda route: route.abort())
            self.contexts[name] = context
            return context
        except Exception as e:
            logger.log(f"Error al lanzar navegador para {name}: {str(e)}", "ERROR")
            raise e

    async def get_page_for_account(self, name: str, force_visible: bool = False) -> Page:
        context = await self.get_context_for_client(name, force_visible=force_visible)
        
        if name not in self.pages:
            page = context.pages[0] if context.pages else await context.new_page()
            self.pages[name] = page
        
        page = self.pages[name]
        
        if "web.whatsapp.com" not in page.url:
            logger.log(f"Cargando WhatsApp Web para {name}...")
            await page.goto("https://web.whatsapp.com")
            asyncio.create_task(self._watch_for_login(name, page))
        
        return page

    async def _watch_for_login(self, name: str, page: Page):
        try:
            await page.wait_for_selector("#side", timeout=120000)
            self.client_status[name] = "READY"
            logger.log(f"Conexión exitosa para '{name}'", "SUCCESS")
        except:
            self.client_status[name] = "STARTING"
            logger.log(f"Esperando inicio de sesión en '{name}'...", "WARN")

    async def close_all(self):
        logger.log("Cerrando todos los servicios...")
        for name, context in self.contexts.items():
            await context.close()
        if self.playwright:
            await self.playwright.stop()

session_manager = SessionManager()
