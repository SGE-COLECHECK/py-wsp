import os
import asyncio
from imgui_bundle import imgui, immapp, hello_imgui
from session_manager import session_manager
from logger_manager import logger

class WhatsAppGUI:
    def __init__(self, loop):
        self.new_school_name = ""
        self.sessions = self.refresh_sessions()
        self.loop = loop # El loop de Playwright que viene de main.py

    def refresh_sessions(self):
        if not os.path.exists("sessions"): return []
        return sorted([f.replace("profile_", "") for f in os.listdir("sessions") if f.startswith("profile_")])

    def open_login(self, name):
        # Enviamos la orden al hilo correcto
        asyncio.run_coroutine_threadsafe(
            session_manager.get_page_for_account(name, force_visible=True), 
            self.loop
        )

    def draw_ui(self):
        io = imgui.get_io()
        imgui.set_next_window_pos((0, 0))
        imgui.set_next_window_size(io.display_size)
        
        flags = (imgui.WindowFlags_.no_title_bar | imgui.WindowFlags_.no_resize | 
                 imgui.WindowFlags_.no_move | imgui.WindowFlags_.no_collapse)

        imgui.begin("Dashboard", None, flags)

        imgui.text_colored((0.3, 0.7, 1, 1), "CONTROL DE COLEGIOS - WHATSAPP")
        imgui.separator()

        # Izquierda
        imgui.begin_child("Left", (imgui.get_window_width() * 0.40, 0), True)
        _, self.new_school_name = imgui.input_text("##new", self.new_school_name)
        imgui.same_line()
        if imgui.button("Añadir +"):
            if self.new_school_name and self.new_school_name not in self.sessions:
                self.sessions.append(self.new_school_name)
                logger.log(f"Colegio '{self.new_school_name}' añadido.")
                self.new_school_name = ""

        imgui.separator()
        for name in self.sessions:
            imgui.push_id(name)
            status = session_manager.get_status(name)
            color = (0.5, 0.5, 0.5, 1)
            if status == "STARTING": color = (1, 0.6, 0, 1)
            if status == "READY": color = (0, 0.9, 0, 1)

            imgui.color_button(f"##st_{name}", color, imgui.ColorEditFlags_.none, (12, 12))
            imgui.same_line()
            imgui.text(name)
            
            imgui.same_line(imgui.get_window_width() * 0.55)
            if imgui.button("VER / AUTH"):
                self.open_login(name)
            
            if status == "READY":
                imgui.same_line()
                imgui.text_colored((0, 1, 0, 1), "[READY]")
            
            imgui.pop_id()
        imgui.end_child()

        imgui.same_line()

        # Derecha: Logs
        imgui.begin_child("Right", (0, 0), True)
        imgui.text("CONSOLA DEL SISTEMA")
        imgui.separator()
        imgui.begin_child("Scroll", (0, 0), False)
        for log_msg in logger.get_logs():
            if "🚨" in log_msg: imgui.text_colored((1, 0.4, 0.4, 1), log_msg)
            elif "✅" in log_msg: imgui.text_colored((0.4, 1, 0.4, 1), log_msg)
            elif "⚠️" in log_msg: imgui.text_colored((1, 0.9, 0.4, 1), log_msg)
            else: imgui.text_wrapped(log_msg)
            
        if imgui.get_scroll_y() >= imgui.get_scroll_max_y():
            imgui.set_scroll_here_y(1.0)
        imgui.end_child()
        imgui.end_child()

        imgui.end()

def launch_gui(loop):
    gui_instance = WhatsAppGUI(loop)
    params = hello_imgui.RunnerParams()
    params.app_window_params.window_title = "WhatsApp Multi-Client"
    params.app_window_params.window_geometry.size = (1000, 600)
    params.callbacks.show_gui = gui_instance.draw_ui
    params.imgui_window_params.default_imgui_window_type = hello_imgui.DefaultImGuiWindowType.no_default_window
    immapp.run(params)
