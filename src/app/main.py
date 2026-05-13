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
    payload = {"phone": phone, "message": message, "label": "REPORTE DIARIO"}
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

    import datetime
    today = datetime.datetime.now().strftime("%d/%m/%Y")

    if override_enabled and custom_msg.strip():
        # Permitir variables opcionales en el mensaje estático
        message = custom_msg.replace("{usuario}", usuario).replace("{contrasena}", contrasena).replace("{url}", url).replace("{fecha}", today)
    else:
        message = f"🚨🇨​​​​​🇴​​​​​🇱​​​​​🇪✅ *[ {today} ]*👋 ¡Bienvenido/a!\n"
        message += f"Le damos la bienvenida al sistema de seguimiento académico 📚\n\n"
        message += f"🔔 *Importante:*\n"
        message += f"A través de este medio recibirá notificaciones sobre asistencia y actividades académicas.\n\n"
        message += f"🎫 *Verifique que su hijo(a) lleve siempre su credencial, ya que las notificaciones dependen de su uso al ingresar y salir del colegio.*\n\n"
        message += f"📌 Manténgase atento/a a las notificaciones enviadas.\n\n"
        message += f"👍 Puede reaccionar o responder a los mensajes para mantener activo el servicio.\n\n"
        message += f"🎓 Equipo ColeCheck"

    payload = {
        "type": "message", 
        "phone": telefono,
        "message": message,
        "label": "BIENVENIDA",
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

@app.post("/whatsapp/wapp-web/{account}/sendRegistrationLink")
async def send_registration_link(account: str, request: Request, background_tasks: BackgroundTasks):
    data = await request.json()
    telefono = data.get("telefono_padre")
    url = data.get("url")

    if not telefono or not url:
        logger.error("Faltan datos obligatorios (telefono_padre, url)", account=account)
        return {"status": "error", "message": "Faltan datos obligatorios (telefono_padre, url)"}

    # Validar teléfono (debe ser 9 dígitos)
    phone_clean = "".join(filter(str.isdigit, str(telefono)))
    if len(phone_clean) != 9:
        logger.error(f"Teléfono inválido: {telefono} (debe ser 9 dígitos)", account=account)
        return {"status": "error", "message": f"Teléfono inválido: {telefono} (debe ser 9 dígitos)"}

    import datetime
    today = datetime.datetime.now().strftime("%d/%m/%Y")

    # Construir mensaje de registro estructurado
    message = [
        f"🚨🇨​​​​​🇴​​​​​🇱​​​​​🇪✅ *[ {today} ]*",
        "",
        "👋 Estimado padre/madre:",
        "",
        "📊 Ahora puede revisar la asistencia de su hijo/a en tiempo real.",
        "",
        "📲 Regístrese en menos de 1 minuto:",
        f"🔗 {url}",
        "",
        "1️⃣ Ingrese al enlace",
        "2️⃣ Complete sus datos",
        "3️⃣ Seleccione a su hijo/a",
        "",
        "🔐 Validaremos su información y le enviaremos su acceso por este medio.",
        "",
        "🎓 *Equipo ColeCheck*"
    ]
    final_message = "\n".join(message)

    payload = {
        "type": "message",
        "phone": phone_clean,
        "message": final_message,
        "label": "LINK REGISTRO",
        "dry_run": data.get("dry_run", False)
    }

    background_tasks.add_task(queue_manager.enqueue, account, payload)
    
    logger.success(f"Link de registro encolado para {phone_clean}", account=account)

    return {
        "success": True,
        "message": "Link de registro agregado a la cola exitosamente",
        "queueId": f"{account}-registration-{phone_clean}",
        "sessionName": account,
        "status": "queued",
    }

@app.post("/whatsapp/wapp-web/{account}/sendCredentials")
async def send_credentials(account: str, request: Request, background_tasks: BackgroundTasks):
    data = await request.json()
    telefono = data.get("telefono_padre")
    usuario = data.get("usuario")
    contrasena = data.get("contrasena")
    tenant_id = data.get("tenantId")
    url_over = data.get("url")

    if not telefono or not usuario or not contrasena or not tenant_id:
        logger.error("Faltan datos obligatorios (telefono_padre, usuario, contrasena, tenantId)", account=account)
        return {"status": "error", "message": "Faltan datos obligatorios (telefono_padre, usuario, contrasena, tenantId)"}

    # Validar teléfono (debe ser 9 dígitos)
    phone_clean = "".join(filter(str.isdigit, str(telefono)))
    if len(phone_clean) != 9:
        logger.error(f"Teléfono inválido: {telefono} (debe ser 9 dígitos)", account=account)
        return {"status": "error", "message": f"Teléfono inválido: {telefono} (debe ser 9 dígitos)"}

    import datetime
    today = datetime.datetime.now().strftime("%d/%m/%Y")

    # Usar la URL proporcionada o construirla dinámicamente
    login_url = url_over if url_over else f"https://panel.colecheck.com/{tenant_id}/login"

    # Construir mensaje de credenciales resaltando información clave
    message = [
        "🎓 *Equipo ColeCheck*",
        "",
        "🔐 *Credenciales de acceso:*",
        f"👤 Usuario: {usuario}",
        f"🔑 Contraseña: {contrasena}",
        f"🌐 {login_url}",
        "",
        "⚠️ *Importante:*",
        "Guarde este mensaje y no comparta sus credenciales.",
        "",
        "📲 *¿Por qué usar la plataforma?*",
        "En horarios de ingreso, muchos estudiantes registran su asistencia al mismo tiempo, lo que puede generar demoras en los mensajes de WhatsApp.",
        "Desde la plataforma puede verlo *al instante*, sin esperar."
    ]
    final_message = "\n".join(message)

    payload = {
        "type": "message",
        "phone": phone_clean,
        "message": final_message,
        "label": "CREDENCIALES",
        "dry_run": data.get("dry_run", False)
    }

    background_tasks.add_task(queue_manager.enqueue, account, payload)
    
    logger.success(f"Credenciales encoladas para {usuario} ({phone_clean})", account=account)

    return {
        "success": True,
        "message": "Credenciales agregadas a la cola exitosamente",
        "queueId": f"{account}-credentials-{phone_clean}",
        "sessionName": account,
        "data": {
            "telefono": phone_clean,
            "usuario": usuario,
            "loginUrl": login_url,
            "fecha": today
        },
        "status": "queued",
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
        "label": "REPORTE SEMANAL",
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
@app.post("/whatsapp/wapp-web/{account}/sendAgenda")
async def send_agenda(account: str, request: Request, background_tasks: BackgroundTasks):
    data = await request.json()
    telefono = data.get("telefono_padre")
    titulo = data.get("titulo", "Nueva tarea registrada")
    contenido = data.get("contenido")
    curso = data.get("curso")
    docente = data.get("docente")
    enlace = data.get("enlace", "")

    if not telefono or not contenido or not curso:
        logger.error("Faltan datos obligatorios (telefono_padre, contenido, curso)", account=account)
        return {"status": "error", "message": "Faltan datos obligatorios (telefono_padre, contenido, curso)"}

    phone_clean = "".join(filter(str.isdigit, str(telefono)))
    if len(phone_clean) != 9:
        return {"status": "error", "message": f"Teléfono inválido: {telefono} (debe ser 9 dígitos)"}

    lines = [
        "📘 *AGENDA ESCOLAR* 🇨​​​​​🇴​​​​​🇱​​​​​🇪✅",
        "",
        f"📝 *{titulo}*",
        "",
        contenido,
        "",
        f"📚 {curso}",
    ]
    if docente:
        lines.append(f"👨🏫 {docente}")
    if enlace:
        lines += ["", f"🔗 {enlace}"]
    lines += ["", "🎓 *Equipo ColeCheck*"]

    final_message = "\n".join(lines)

    payload = {
        "type": "message",
        "phone": phone_clean,
        "message": final_message,
        "label": "AGENDA",
        "dry_run": data.get("dry_run", False)
    }

    background_tasks.add_task(queue_manager.enqueue, account, payload)
    logger.success(f"Agenda encolada para {phone_clean}", account=account)

    return {
        "success": True,
        "message": "Agenda escolar agregada a la cola exitosamente",
        "queueId": f"{account}-agenda-{phone_clean}",
        "sessionName": account,
        "data": {
            "telefono": phone_clean,
            "titulo": titulo,
            "curso": curso,
            "docente": docente or "",
        },
        "status": "queued",
    }

@app.post("/whatsapp/wapp-web/{account}/sendComunicado")
async def send_comunicado(account: str, request: Request, background_tasks: BackgroundTasks):
    data = await request.json()
    telefono = data.get("telefono_padre")
    titulo = data.get("titulo")
    contenido = data.get("contenido")
    area = data.get("area", "Dirección")
    enlace = data.get("enlace", "")
    colegio = data.get("colegio", "Equipo ColeCheck")

    if not telefono or not titulo or not contenido:
        logger.error("Faltan datos obligatorios (telefono_padre, titulo, contenido)", account=account)
        return {"status": "error", "message": "Faltan datos obligatorios (telefono_padre, titulo, contenido)"}

    phone_clean = "".join(filter(str.isdigit, str(telefono)))
    if len(phone_clean) != 9:
        return {"status": "error", "message": f"Teléfono inválido: {telefono} (debe ser 9 dígitos)"}

    lines = [
        "📢 *COMUNICADO* 🇨​​​​​🇴​​​​​🇱​​​​​🇪✅",
        "",
        f"📌 *{titulo}*",
        "",
        contenido,
        "",
        f"🏫 {area}",
    ]
    if enlace:
        lines += ["", f"🔗 {enlace}"]
    lines += ["", f"🎓 *{colegio}*"]

    final_message = "\n".join(lines)

    payload = {
        "type": "message",
        "phone": phone_clean,
        "message": final_message,
        "label": "COMUNICADO",
        "dry_run": data.get("dry_run", False)
    }

    background_tasks.add_task(queue_manager.enqueue, account, payload)
    logger.success(f"Comunicado encolado para {phone_clean}", account=account)

    return {
        "success": True,
        "message": "Comunicado agregado a la cola exitosamente",
        "queueId": f"{account}-comunicado-{phone_clean}",
        "sessionName": account,
        "data": {
            "telefono": phone_clean,
            "titulo": titulo,
            "area": area,
            "colegio": colegio,
        },
        "status": "queued",
    }

@app.post("/whatsapp/wapp-web/{account}/sendWarning")
async def send_warning(account: str, request: Request, background_tasks: BackgroundTasks):
    data = await request.json()
    telefono = data.get("telefono_padre")
    titulo = data.get("titulo")
    contenido = data.get("contenido")
    reportado_por = data.get("reportado_por")
    area = data.get("area", "Tutoría")
    enlace = data.get("enlace", "")
    colegio = data.get("colegio", "Equipo ColeCheck")
    gravedad = data.get("gravedad", "leve")  # leve, moderado, grave

    if not telefono or not titulo or not contenido:
        logger.error("Faltan datos obligatorios (telefono_padre, titulo, contenido)", account=account)
        return {"status": "error", "message": "Faltan datos obligatorios (telefono_padre, titulo, contenido)"}

    phone_clean = "".join(filter(str.isdigit, str(telefono)))
    if len(phone_clean) != 9:
        return {"status": "error", "message": f"Teléfono inválido: {telefono} (debe ser 9 dígitos)"}

    # Emoji de gravedad
    gravedad_map = {
        "leve": "🟡",
        "moderado": "🟠",
        "grave": "🔴"
    }
    gravedad_emoji = gravedad_map.get(gravedad.lower(), "🟠")

    lines = [
        f"{gravedad_emoji} *LLAMADO DE ATENCIÓN* 🇨​​​​​🇴​​​​​🇱​​​​​🇪✅",
        "",
        f"⚠️ *{titulo}*",
        "",
        contenido,
        "",
    ]
    if reportado_por:
        lines.append(f"👨🏫 {reportado_por}")
    lines.append(f"🏫 {area}")
    if enlace:
        lines += ["", f"🔗 {enlace}"]
    lines += ["", f"🎓 *{colegio}*"]

    final_message = "\n".join(lines)

    payload = {
        "type": "message",
        "phone": phone_clean,
        "message": final_message,
        "label": "LLAMADO ATENCIÓN",
        "dry_run": data.get("dry_run", False)
    }

    background_tasks.add_task(queue_manager.enqueue, account, payload)
    logger.success(f"Llamado de atención encolado para {phone_clean}", account=account)

    return {
        "success": True,
        "message": "Llamado de atención agregado a la cola exitosamente",
        "queueId": f"{account}-warning-{phone_clean}",
        "sessionName": account,
        "data": {
            "telefono": phone_clean,
            "titulo": titulo,
            "reportado_por": reportado_por or "",
            "area": area,
            "gravedad": gravedad,
            "colegio": colegio,
        },
        "status": "queued",
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
