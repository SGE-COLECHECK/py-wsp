import os
import threading
import asyncio
import time
import uvicorn
import collections
from datetime import datetime
from imgui_bundle import imgui, immapp, hello_imgui
from session_manager import session_manager
from main import app as fastapi_app

class WhatsAppGUI:
    def __init__(self):
        self.new_school_name = ""
        self.sessions = self.refresh_sessions()
        self.status = {} 
        self.logs = collections.deque(maxlen=100) # Guardar últimos 100 logs
        self.add_log("🚀 Sistema iniciado. Listo para gestionar colegios.")
        
        self.api_thread = None
        self.running = True

    def add_log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.logs.append(f"[{timestamp}] {message}")

    def refresh_sessions(self):
        if not os.path.exists("sessions"): return []
        return [f.replace("profile_", "") for f in os.listdir("sessions") if f.startswith("profile_")]

    def start_api(self):
        # Redirigir logs de uvicorn a nuestra consola interna sería ideal, 
        # pero por ahora lo dejamos en un hilo separado.
        uvicorn.run(fastapi_app, host="0.0.0.0", port=3000, log_level="error")

    async def open_login(self, name):
        self.add_log(f"📂 Abriendo navegador para: {name}...")
        try:
            await session_manager.get_page_for_account(name)
            self.status[name] = "Abierto/QR"
            self.add_log(f"✅ Navegador listo para {name}. Escanea el QR.")
        except Exception as e:
            self.add_log(f"🚨 Error en {name}: {str(e)}")

    def run_async_task(self, coro):
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(coro)
        else:
            loop.run_until_complete(coro)

    def draw_ui(self):
        # Forzar que la ventana ocupe todo el espacio
        io = imgui.get_io()
        imgui.set_next_window_pos((0, 0))
        imgui.set_next_window_size(io.display_size)
        
        # Estilo de ventana sin bordes ni barra de título (App completa)
        flags = (imgui.WindowFlags_.no_title_bar | 
                 imgui.WindowFlags_.no_resize | 
                 imgui.WindowFlags_.no_move | 
                 imgui.WindowFlags_.no_collapse |
                 imgui.WindowFlags_.no_bring_to_front_on_focus)

        imgui.begin("MainPanel", None, flags)

        # CABECERA
        imgui.text_ansi_colored("ANTIGRAVITY WHATSAPP MANAGER", (0.2, 0.8, 1, 1))
        imgui.same_line(imgui.get_window_width() - 200)
        imgui.text_disabled(f"API: http://localhost:3000")
        imgui.separator()

        # DOS COLUMNAS: Izquierda (Colegios) | Derecha (Logs)
        imgui.begin_child("LeftPane", (imgui.get_window_width() * 0.4, 0), True)
        
        imgui.text("COLEGIOS / SECCIONES")
        imgui.spacing()
        
        # Agregar nuevo
        _, self.new_school_name = imgui.input_text("##new", self.new_school_name)
        imgui.same_line()
        if imgui.button("Añadir +"):
            if self.new_school_name and self.new_school_name not in self.sessions:
                self.sessions.append(self.new_school_name)
                self.add_log(f"➕ Colegio '{self.new_school_name}' añadido a la lista.")
                self.new_school_name = ""

        imgui.separator()
        imgui.spacing()

        for name in self.sessions:
            imgui.push_id(name)
            
            # Estado
            color = (0.7, 0.1, 0.1, 1)
            if "Abierto" in self.status.get(name, ""): color = (0.9, 0.9, 0, 1)
            if "OK" in self.status.get(name, ""): color = (0, 0.8, 0, 1)
            
            imgui.color_button(f"##st_{name}", color, imgui.ColorEditFlags_.none, (12, 12))
            imgui.same_line()
            imgui.text(name)
            
            imgui.same_line(imgui.get_window_width() * 0.6)
            if imgui.button("LOGIN"):
                self.run_async_task(self.open_login(name))
            
            imgui.same_line()
            if imgui.button("X"):
                if name in self.sessions: self.sessions.remove(name)
            
            imgui.pop_id()
        
        imgui.end_child()

        imgui.same_line()

        # DERECHA: CONSOLA DE LOGS
        imgui.begin_child("RightPane", (0, 0), True)
        imgui.text("CONSOLA DE EVENTOS")
        imgui.separator()
        
        imgui.begin_child("LogScroll", (0, -30), False)
        for log in self.logs:
            if "✅" in log: imgui.text_ansi_colored(log, (0, 1, 0, 1))
            elif "🚨" in log: imgui.text_ansi_colored(log, (1, 0, 0, 1))
            elif "🚀" in log: imgui.text_ansi_colored(log, (0, 0.8, 1, 1))
            else: imgui.text_wrapped(log)
        
        # Auto-scroll al final
        if imgui.get_scroll_y() >= imgui.get_scroll_max_y():
            imgui.set_scroll_here_y(1.0)
            
        imgui.end_child()
        
        if imgui.button("Limpiar Logs"):
            self.logs.clear()
            self.add_log("Consola limpia.")

        imgui.end_child()

        imgui.end()

def main():
    gui = WhatsAppGUI()

    # Iniciar API
    gui.api_thread = threading.Thread(target=gui.start_api, daemon=True)
    gui.api_thread.start()

    params = hello_imgui.RunnerParams()
    params.app_window_params.window_title = "Cole-Check WhatsApp Manager"
    params.app_window_params.window_geometry.size = (1000, 600)
    params.callbacks.show_gui = gui.draw_ui
    
    # Tema oscuro por defecto
    params.imgui_window_params.default_imgui_window_type = hello_imgui.DefaultImguiWindowType.no_default_window
    
    immapp.run(params)

if __name__ == "__main__":
    main()
