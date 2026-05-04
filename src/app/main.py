import asyncio
from fastapi import FastAPI, BackgroundTasks, Request
from app.core.queue_manager import queue_manager
from app.utils.logger import logger
from app.ui.app import run_gui_app

app = FastAPI()

@app.post("/whatsapp/wapp-web/{account}/senddReport")
async def enqueue_report(account: str, request: Request, background_tasks: BackgroundTasks):
    data = await request.json()
    
    # MAPEAMOS TU FORMATO AL QUE NECESITA EL SENDER
    # 1. Teléfono
    phone = data.get("telefono_padre") or data.get("phone")
    
    # 2. Construir mensaje si no viene uno
    message = data.get("message")
    if not message:
        alumno = data.get("nombre_alumno", "Alumno")
        tipo = data.get("type_asistance", "REGISTRO")
        hora = data.get("timestamp", "")
        ubicacion = data.get("ubicacion", "")
        
        message = f"🔔 *REPORTE DE ASISTENCIA*\n\n"
        message += f"Estudiante: *{alumno}*\n"
        message += f"Acción: *{tipo}*\n"
        if hora: message += f"Hora: {hora}\n"
        if ubicacion: message += f"Lugar: {ubicacion}\n"
        message += f"\n_Mensaje automático de Cole-Check_"

    if not phone:
        logger.error(f"[{account}] Error: No se encontró 'telefono_padre' en el JSON")
        return {"status": "error", "message": "Falta el teléfono"}

    # Encolar para procesamiento asíncrono en Redis
    payload = {"phone": phone, "message": message}
    background_tasks.add_task(queue_manager.enqueue, account, payload)
    
    return {"status": "enqueued", "account": account, "target": phone}

@app.get("/health")
async def health():
    return {"status": "ok", "redis": queue_manager.is_connected}

def run_server():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3000)

def run_async_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    global playwright_loop
    playwright_loop = loop
    loop.run_forever()

# Variable global para el loop de playwright
playwright_loop = None
