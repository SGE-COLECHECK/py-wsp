import threading
import asyncio
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from contextlib import asynccontextmanager

# Importaciones modulares
from session_manager import session_manager
from whatsapp_service import send_report
from gui_manager import launch_gui
from logger_manager import logger

# --- GESTIÓN DE HILOS ASÍNCRONOS ---
# Creamos un loop global para que Playwright viva en su propio hilo
playwright_loop = asyncio.new_event_loop()

def run_playwright_loop():
    asyncio.set_event_loop(playwright_loop)
    playwright_loop.run_forever()

# --- CONFIGURACIÓN API ---
class ReportData(BaseModel):
    dni: str
    nombre_alumno: str
    nombre_padre: str
    telefono_padre: str
    grado: str
    seccion: str
    timestamp: str
    ubicacion: str
    type_asistance: str

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    # Cerrar navegadores al apagar
    future = asyncio.run_coroutine_threadsafe(session_manager.close_all(), playwright_loop)
    future.result()

app = FastAPI(lifespan=lifespan)

@app.post("/whatsapp/wapp-web/{name}/senddReport")
async def post_report(name: str, data: ReportData):
    # Enviamos el trabajo al hilo de Playwright
    future = asyncio.run_coroutine_threadsafe(
        send_report(name, data.model_dump()), 
        playwright_loop
    )
    # Esperamos el resultado de forma síncrona para responder a la API
    result = await asyncio.wrap_future(future)
    
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["message"])
    return result

def run_api():
    uvicorn.run(app, host="0.0.0.0", port=3000, log_level="error")

# --- ARRANQUE ---
if __name__ == "__main__":
    # 1. Hilo del Navegador (Crítico para que funcione)
    threading.Thread(target=run_playwright_loop, daemon=True).start()
    
    # 2. Hilo de la API
    threading.Thread(target=run_api, daemon=True).start()
    
    logger.log("SISTEMA INICIADO - Puerto 3000")
    
    # 3. Lanzar GUI en el hilo principal
    # Pasamos el loop para que la GUI sepa dónde enviar las órdenes
    launch_gui(playwright_loop)
