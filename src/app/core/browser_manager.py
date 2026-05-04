import os
import asyncio
import shutil
from playwright.async_api import async_playwright, BrowserContext, Page
from app.utils.logger import logger
from app.utils.config_manager import config_manager

class BrowserManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(BrowserManager, cls).__new__(cls)
            cls._instance.playwright = None
            cls._instance.contexts = {} 
            cls._instance.pages = {}    
            cls._instance.is_visible = {} 
            cls._instance.client_status = {} 
            cls._instance.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        return cls._instance

    async def init_playwright(self):
        if not self.playwright:
            logger.info("Iniciando motor Playwright...")
            self.playwright = await async_playwright().start()

    def get_status(self, name: str) -> str:
        return self.client_status.get(name, "OFFLINE")

    async def close_client(self, name: str):
        if name in self.contexts:
            logger.info(f"Cerrando navegador de '{name}'...")
            try:
                await self.contexts[name].close()
            except: pass
            if name in self.contexts: del self.contexts[name]
            if name in self.pages: del self.pages[name]
            if name in self.is_visible: del self.is_visible[name]
            self.client_status[name] = "OFFLINE"

    async def get_context(self, name: str, force_visible: bool = False) -> BrowserContext:
        client_cfg = config_manager.get_client_config(name)
        should_be_visible = force_visible or not client_cfg.get("headless", True)

        if name in self.contexts:
            current_visible = self.is_visible.get(name, False)
            if should_be_visible != current_visible:
                await self.close_client(name)
            else:
                return self.contexts[name]

        await self.init_playwright()
        
        # --- LIMPIEZA DE SINGLETON LOCK ---
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../data"))
        user_data_dir = os.path.join(base_dir, "sessions", f"profile_{name}")
        lock_file = os.path.join(user_data_dir, "SingletonLock")
        if os.path.exists(lock_file):
            try:
                os.remove(lock_file)
                logger.info(f"Limpiando bloqueo antiguo para {name}")
            except: pass
        
        os.makedirs(user_data_dir, exist_ok=True)
        logger.info(f"Lanzando navegador para '{name}' (Visible: {should_be_visible})")
        self.is_visible[name] = should_be_visible

        try:
            context = await self.playwright.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                headless=not should_be_visible,
                user_agent=self.user_agent,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
            )
            self.contexts[name] = context
            return context
        except Exception as e:
            logger.error(f"Error crítico en navegador {name}: {e}")
            self.client_status[name] = "OFFLINE"
            raise e

    async def get_page(self, name: str, visible: bool = False) -> Page:
        context = await self.get_context(name, force_visible=visible)
        if name not in self.pages or self.pages[name].is_closed():
            page = await context.new_page() if not context.pages else context.pages[0]
            self.pages[name] = page
        
        page = self.pages[name]
        if "web.whatsapp.com" not in page.url:
            await page.goto("https://web.whatsapp.com")
            asyncio.create_task(self._watch_login(name, page))
        return page

    async def _watch_login(self, name: str, page: Page):
        try:
            self.client_status[name] = "STARTING"
            await page.wait_for_selector("#side", timeout=60000)
            self.client_status[name] = "READY"
        except:
            self.client_status[name] = "STARTING"

    async def shutdown(self):
        for name in list(self.contexts.keys()):
            await self.close_client(name)
        if self.playwright:
            await self.playwright.stop()

browser_manager = BrowserManager()
