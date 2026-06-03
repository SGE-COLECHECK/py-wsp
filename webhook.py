import hashlib
import hmac
import logging
import os
import sys
import json
from typing import Optional

from fastapi import FastAPI, Request, HTTPException
import uvicorn

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("webhook")

app = FastAPI(title="YCloud Webhook Receiver")

WEBHOOK_SECRET = os.getenv("YCLOUD_WEBHOOK_SECRET", "")

def verify_signature(payload: bytes, signature_header: str, secret: str) -> bool:
    if not secret or not signature_header:
        return False
    params = {}
    for part in signature_header.split(","):
        if "=" in part:
            k, v = part.split("=", 1)
            params[k.strip()] = v.strip()
    timestamp = params.get("t")
    sig = params.get("s")
    if not timestamp or not sig:
        return False
    signed_payload = f"{timestamp}.{payload.decode()}".encode()
    expected = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig)


def handle_whatsapp_inbound_message(payload: dict):
    msg = payload.get("whatsappInboundMessage", {})
    from_number = msg.get("from", "unknown")
    to_number = msg.get("to", "unknown")
    msg_type = msg.get("type", "unknown")
    body_text = ""
    if msg_type == "text":
        body_text = msg.get("text", {}).get("body", "")
    elif msg_type == "interactive":
        body_text = json.dumps(msg.get("interactive", {}))
    elif msg_type == "button":
        body_text = json.dumps(msg.get("button", {}))
    elif msg_type == "image":
        body_text = json.dumps(msg.get("image", {}))
    elif msg_type == "document":
        body_text = json.dumps(msg.get("document", {}))
    elif msg_type == "audio":
        body_text = json.dumps(msg.get("audio", {}))
    elif msg_type == "video":
        body_text = json.dumps(msg.get("video", {}))
    elif msg_type == "location":
        body_text = json.dumps(msg.get("location", {}))
    customer_profile = msg.get("customerProfile", {})
    customer_name = customer_profile.get("name", "unknown")
    log.info(f"  From: {from_number}")
    log.info(f"  To: {to_number}")
    log.info(f"  Customer: {customer_name}")
    log.info(f"  Type: {msg_type}")
    log.info(f"  Body: {body_text}")
    group_id = msg.get("groupId")
    if group_id:
        log.info(f"  Group ID: {group_id}")
    if from_number == "+51963828458":
        log.info("*** MENSAJE DE YRSAN ***")

def handle_whatsapp_message_updated(payload: dict):
    msg = payload.get("whatsappMessage", {})
    log.info(f"  ID: {msg.get('id')} | Status: {msg.get('status')} | WAMID: {msg.get('wamid')}")

def handle_whatsapp_business_account(payload: dict):
    ba = payload.get("whatsappBusinessAccount", {})
    log.info(f"  Account: {ba.get('id')} | VerifiedName: {ba.get('verifiedName')}")

def handle_whatsapp_phone_number(payload: dict):
    pn = payload.get("whatsappPhoneNumber", {})
    log.info(f"  Phone: {pn.get('phoneNumber')} | Status: {pn.get('status')} | Quality: {pn.get('qualityRating')}")

def handle_whatsapp_template(payload: dict):
    tmpl = payload.get("whatsappTemplate", {})
    log.info(f"  Template: {tmpl.get('name')} | Language: {tmpl.get('language')} | Status: {tmpl.get('status')}")

def handle_whatsapp_flow(payload: dict):
    flow = payload.get("whatsappFlow", {})
    log.info(f"  Flow: {flow.get('id')} | Status: {flow.get('status')}")

def handle_whatsapp_payment(payload: dict):
    pmt = payload.get("whatsappPayment", {})
    log.info(f"  Payment: {pmt.get('id')} | Status: {pmt.get('status')}")

def handle_whatsapp_smb(payload: dict):
    smb = payload.get("whatsappSmb", {})
    log.info(f"  SMB: {json.dumps(smb, default=str)}")

def handle_whatsapp_user_preferences(payload: dict):
    prefs = payload.get("whatsappUserPreferences", {})
    log.info(f"  Preferences: {json.dumps(prefs, default=str)}")

def handle_sms_inbound_received(payload: dict):
    sms = payload.get("smsInbound", {})
    log.info(f"  From: {sms.get('from', 'unknown')}")
    log.info(f"  To: {sms.get('to', 'unknown')}")
    log.info(f"  Text: {sms.get('text', '')}")

def handle_sms_message_updated(payload: dict):
    sms = payload.get("smsMessage", {})
    log.info(f"  ID: {sms.get('id')} | Status: {sms.get('status')}")

def handle_contact_event(payload: dict):
    contact = payload.get("contact", {})
    log.info(f"  Contact: {contact.get('id')} | Phone: {contact.get('phoneNumber')} | Name: {contact.get('firstName', '')} {contact.get('lastName', '')}")

def handle_contact_unsubscribe(payload: dict):
    unsub = payload.get("contactUnsubscribe", {})
    log.info(f"  Phone: {unsub.get('phoneNumber')} | Channel: {unsub.get('channel')}")

def handle_email_delivery_updated(payload: dict):
    email = payload.get("emailDelivery", {})
    log.info(f"  To: {email.get('to')} | Status: {email.get('status')} | MessageID: {email.get('messageId')}")

def handle_voice_message_updated(payload: dict):
    voice = payload.get("voiceMessage", {})
    log.info(f"  To: {voice.get('to')} | Status: {voice.get('status')} | Duration: {voice.get('duration')}")

EVENT_HANDLERS = {
    # WhatsApp
    "whatsapp.inbound_message.received": handle_whatsapp_inbound_message,
    "whatsapp.message.updated": handle_whatsapp_message_updated,
    "whatsapp.business_account.deleted": handle_whatsapp_business_account,
    "whatsapp.business_account.reviewed": handle_whatsapp_business_account,
    "whatsapp.business_account.updated": handle_whatsapp_business_account,
    "whatsapp.phone_number.deleted": handle_whatsapp_phone_number,
    "whatsapp.phone_number.name_updated": handle_whatsapp_phone_number,
    "whatsapp.phone_number.quality_updated": handle_whatsapp_phone_number,
    "whatsapp.template.category_updated": handle_whatsapp_template,
    "whatsapp.template.quality_updated": handle_whatsapp_template,
    "whatsapp.template.reviewed": handle_whatsapp_template,
    "whatsapp.flow.status_change": handle_whatsapp_flow,
    "whatsapp.payment.updated": handle_whatsapp_payment,
    "whatsapp.smb.app.state.sync": handle_whatsapp_smb,
    "whatsapp.smb.history": handle_whatsapp_smb,
    "whatsapp.smb.message.echoes": handle_whatsapp_smb,
    "whatsapp.user.preferences": handle_whatsapp_user_preferences,
    # Contact
    "contact.attributes_changed": handle_contact_event,
    "contact.created": handle_contact_event,
    "contact.deleted": handle_contact_event,
    "contact.unsubscribe.created": handle_contact_unsubscribe,
    "contact.unsubscribe.deleted": handle_contact_unsubscribe,
    # SMS
    "sms.inbound.received": handle_sms_inbound_received,
    "sms.message.updated": handle_sms_message_updated,
    # Email
    "email.delivery.updated": handle_email_delivery_updated,
    # Voice
    "voice.message.updated": handle_voice_message_updated,
}

@app.post("/webhook")
async def webhook(request: Request):
    body = await request.body()
    sig_header = request.headers.get("YCloud-Signature", "")
    content_type = request.headers.get("content-type", "")

    log.info("=" * 60)
    log.info("Webhook received!")
    log.info(f"Headers: {dict(request.headers)}")

    if not body:
        log.warning("Empty body")
        return {"status": "ok"}

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        log.warning(f"Invalid JSON: {body}")
        return {"status": "ok"}

    event_type = payload.get("type", "unknown")
    log.info(f"Event type: {event_type}")

    if WEBHOOK_SECRET:
        valid = verify_signature(body, sig_header, WEBHOOK_SECRET)
        log.info(f"Signature valid: {valid}")

    handler = EVENT_HANDLERS.get(event_type)
    if handler:
        handler(payload)
    else:
        log.info(f"Unhandled event type: {event_type}")
        log.info(f"Full payload: {json.dumps(payload, indent=2, default=str)}")

    log.info("=" * 60)
    return {"status": "ok"}


@app.get("/webhook")
async def verify_challenge(request: Request):
    challenge = request.query_params.get("challenge")
    if challenge:
        log.info(f"Verification challenge received: {challenge}")
        return int(challenge)
    return {"status": "ok"}


@app.get("/")
async def root():
    return {
        "service": "YCloud Webhook Receiver",
        "status": "running",
        "webhook_url": "/webhook",
        "server": f"http://localhost:{PORT}",
    }


if __name__ == "__main__":
    PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
    log.info(f"Starting webhook server on port {PORT}")
    log.info(f"Configure YCloud webhook to: https://TU_DOMINIO.ngrok-free.app/webhook")
    log.info(f"Set YCLOUD_WEBHOOK_SECRET env var for signature verification")
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")
