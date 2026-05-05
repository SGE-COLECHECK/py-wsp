import asyncio
from fastapi import FastAPI, BackgroundTasks, Request
from app.core.queue_manager import queue_manager
from app.utils.logger import logger
from app.ui.app import run_gui_app

def format_student_name(full_name: str) -> str:
    """Abrevia los dos últimos apellidos a sus iniciales."""
    parts = full_name.strip().split()
    if len(parts) <= 1: return full_name
    if len(parts) == 2: return f"{parts[0]} {parts[1][0]}."
    
    names = parts[:-2]
    surnames = parts[-2:]
    formatted_surnames = " ".join([f"{s[0]}." for s in surnames])
    return f"{' '.join(names)} {formatted_surnames}"

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
        import random
        alumno = format_student_name(data.get("nombre_alumno", "Alumno"))
        tipo = data.get("type_asistance", "REGISTRO")
        tipo_bold = f"*{tipo}*" # Negrita para WhatsApp
        hora = data.get("timestamp", "")
        
        # Variedad de respuestas para evitar que WhatsApp detecte SPAM por mensajes idénticos
        respuestas = ["OK", "Entendido", "Recibido", "👍", "De acuerdo", "Listo", "Copiado", "Sí", "Conforme"]
        random_resp = random.choice(respuestas)
        
        message = f"🚨🇨​​​​​🇴​​​​​🇱​​​​​🇪✅ 🎓 {alumno} || {tipo_bold}: {hora}\n"
        message += f"✨ Responde {random_resp}"

    if not phone:
        logger.error(f"[{account}] Error: No se encontró 'telefono_padre' en el JSON")
        return {"status": "error", "message": "Falta el teléfono"}

    # Encolar para procesamiento asíncrono en Redis
    payload = {"phone": phone, "message": message}
    background_tasks.add_task(queue_manager.enqueue, account, payload)
    
    return {"status": "enqueued", "account": account, "target": phone}

@app.post("/whatsapp/wapp-web/{account}/addNumber")
async def add_number(account: str, request: Request, background_tasks: BackgroundTasks):
    data = await request.json()
    nombre = data.get("nombre")
    telefono = data.get("telefono")

    if not nombre or not telefono:
        return {"status": "error", "message": "Faltan datos obligatorios (nombre, telefono)"}

    payload = {
        "type": "add_contact",
        "name": nombre,
        "phone": telefono,
        "dry_run": data.get("dry_run", False)
    }
    
    background_tasks.add_task(queue_manager.enqueue, account, payload)
    
    return {
        "success": True,
        "message": "Tarea de agregar contacto encolada exitosamente",
        "taskId": f"{account}-{telefono}",
        "sessionName": account,
        "data": {
            "nombre": nombre,
            "telefono": telefono,
            "telefonoOriginal": telefono
        },
        "status": "queued",
        "note": "La tarea se procesará en la cola sin interrumpir otros mensajes"
    }

@app.post("/whatsapp/wapp-web/{account}/sendWelcomeMessage")
async def send_welcome_message(account: str, request: Request, background_tasks: BackgroundTasks):
    from app.utils.config_manager import config_manager
    data = await request.json()
    telefono = data.get("telefono_padre")
    usuario = data.get("usuario")
    contrasena = data.get("contrasena")
    url = data.get("url")

    if not telefono or not usuario or not contrasena or not url:
        return {"status": "error", "message": "Faltan datos obligatorios (telefono_padre, usuario, contrasena, url)"}

    override_enabled = config_manager.get_global("override_welcome", False)
    custom_msg = config_manager.get_global("custom_welcome_msg", "")

    if override_enabled and custom_msg.strip():
        # Permitir variables opcionales en el mensaje estático
        message = custom_msg.replace("{usuario}", usuario).replace("{contrasena}", contrasena).replace("{url}", url)
    else:
        message = f"🌟 *¡Bienvenido a Cole-Check!* 🌟\n\n"
        message += f"Estimado padre de familia, aquí tiene sus credenciales de acceso:\n\n"
        message += f"👤 *Usuario:* {usuario}\n"
        message += f"🔑 *Contraseña:* {contrasena}\n"
        message += f"🌐 *Portal:* {url}\n\n"
        message += f"Por favor, inicie sesión para ver los reportes."

    payload = {
        "type": "message", 
        "phone": telefono,
        "message": message,
        "dry_run": data.get("dry_run", False)
    }
    
    background_tasks.add_task(queue_manager.enqueue, account, payload)
    
    import datetime
    today = datetime.datetime.now().strftime("%d/%m/%Y")

    return {
        "success": True,
        "message": "Mensaje de bienvenida agregado a la cola exitosamente",
        "queueId": f"{account}-welcome-{telefono}",
        "sessionName": account,
        "data": {
            "telefono": telefono,
            "usuario": usuario,
            "url": url,
            "fecha": today
        },
        "status": "queued"
    }

@app.post("/whatsapp/wapp-web/{account}/sendwReport")
async def send_weekly_report(account: str, request: Request, background_tasks: BackgroundTasks):
    data = await request.json()
    telefono = data.get("telefono_padre")
    alumno = data.get("nombre_alumno", "Alumno")
    padre = data.get("nombre_padre", "Padre")
    
    if not telefono:
        return {"status": "error", "message": "Faltan datos obligatorios (telefono_padre)"}

    dias = {
        "Lunes": data.get("lunes", ""),
        "Martes": data.get("martes", ""),
        "Miércoles": data.get("miercoles", ""),
        "Jueves": data.get("jueves", ""),
        "Viernes": data.get("viernes", "")
    }

    # Calcular asistencias
    total_dias = 0
    dias_asistidos = 0
    for dia, estado in dias.items():
        if estado:  
            total_dias += 1
            if estado.lower() in ["asistencia", "tardanza", "justificado"]:
                dias_asistidos += 1

    porcentaje = int((dias_asistidos / total_dias * 100)) if total_dias > 0 else 0
    
    if porcentaje >= 80: estado_emoji = "🟢"
    elif porcentaje >= 50: estado_emoji = "🟡"
    else: estado_emoji = "🔴"

    message = f"📊 *REPORTE SEMANAL DE ASISTENCIA* 📊\n\n"
    message += f"🎓 *Estudiante:* {alumno}\n"
    message += f"🗓 *Semana:* {data.get('fecha_inicio', '')} al {data.get('fecha_fin', '')}\n\n"
    
    for dia, estado in dias.items():
        if estado:
            icono = "✅" if estado.lower() == "asistencia" else "⚠️" if estado.lower() == "tardanza" else "❌"
            message += f"• {dia}: {icono} {estado}\n"

    try: estrellas = int(data.get("desempeno", 0))
    except: estrellas = 0

    message += f"\n📈 *Asistencia Total:* {porcentaje}%\n"
    message += f"📌 *Estado:* {estado_emoji}\n"
    if estrellas > 0: message += f"⭐ *Desempeño:* {'⭐' * estrellas}\n\n"
    else: message += "\n"
    
    message += "_Mensaje automático de Cole-Check_"

    payload = {
        "type": "message",
        "phone": telefono,
        "message": message,
        "dry_run": data.get("dry_run", False)
    }
    
    background_tasks.add_task(queue_manager.enqueue, account, payload)
    
    return {
        "success": True,
        "message": "Reporte semanal agregado a la cola exitosamente",
        "queueId": f"{account}-wreport-{telefono}",
        "sessionName": account,
        "data": {
            "alumno": alumno,
            "padre": padre,
            "telefono": telefono,
            "grado": data.get("grado", ""),
            "seccion": data.get("seccion", ""),
            "fecha_inicio": data.get("fecha_inicio", ""),
            "fecha_fin": data.get("fecha_fin", ""),
            "desempeno": estrellas,
            "porcentaje_asistencia": str(porcentaje),
            "estado": estado_emoji
        },
        "status": "queued"
    }

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
