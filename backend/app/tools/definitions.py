from langchain.tools import tool
from pydantic import BaseModel
from typing import Optional


# ─── SCHÉMAS D'ENTRÉE DES TOOLS ────────────────────────────────────────────────

class SendEmailInput(BaseModel):
    recipient: str
    subject: str
    body: str

class ScheduleMeetingInput(BaseModel):
    attendee: str
    date: str
    time: str
    duration: int  # en minutes

class GenerateQuoteInput(BaseModel):
    customer_name: str
    items: list[str]
    prices: list[float]
    discount: Optional[float] = 0.0

class ClarifyInputSchema(BaseModel):
    ambiguous_request: str
    options: list[str]

class CheckAmbiguityInput(BaseModel):
    request: str


# DÉFINITION DES 5 TOOLS

@tool("send_email", args_schema=SendEmailInput)
def send_email(recipient: str, subject: str, body: str) -> dict:
    """
    Envoie un email à un destinataire.
    À utiliser quand l'utilisateur veut envoyer un message ou un devis par email.
    """
    # MOCK — sera remplacé par une vraie intégration email (SMTP / SendGrid) J4-5
    print(f"[MOCK] Envoi email à {recipient} | Sujet : {subject}")
    return {
        "status": "success",
        "message_id": "mock-email-001",
        "recipient": recipient,
        "subject": subject
    }


@tool("schedule_meeting", args_schema=ScheduleMeetingInput)
def schedule_meeting(attendee: str, date: str, time: str, duration: int) -> dict:
    """
    Planifie une réunion avec un participant.
    À utiliser quand l'utilisateur veut fixer un rendez-vous ou une réunion.
    """
    # MOCK — sera remplacé par une vraie intégration calendrier J4-5
    print(f"[MOCK] Réunion planifiée avec {attendee} le {date} à {time}")
    return {
        "status": "success",
        "calendar_event_id": "mock-event-001",
        "attendee": attendee,
        "date": date,
        "time": time,
        "duration_minutes": duration
    }


@tool("generate_quote", args_schema=GenerateQuoteInput)
def generate_quote(
    customer_name: str,
    items: list[str],
    prices: list[float],
    discount: float = 0.0
) -> dict:
    """
    Génère un devis pour un client.
    À utiliser quand l'utilisateur veut créer un devis commercial.
    """
    # MOCK — sera remplacé par une vraie génération de devis J4-5
    subtotal = sum(prices)
    discount_amount = subtotal * (discount / 100)
    total = subtotal - discount_amount

    print(f"[MOCK] Devis généré pour {customer_name} | Total : {total}")
    return {
        "status": "success",
        "quote_id": "mock-quote-001",
        "customer_name": customer_name,
        "items": items,
        "prices": prices,
        "discount_percent": discount,
        "subtotal": subtotal,
        "discount_amount": discount_amount,
        "total_price": total
    }


@tool("clarify_input", args_schema=ClarifyInputSchema)
def clarify_input(ambiguous_request: str, options: list[str]) -> dict:
    """
    Pose une question de clarification à l'utilisateur.
    À utiliser quand la demande est ambiguë et nécessite plus d'informations.
    """
    # Ce tool génère une question — la réponse viendra du frontend M4
    question = f"Votre demande '{ambiguous_request}' nécessite des précisions."
    if options:
        question += f" Options possibles : {', '.join(options)}"

    print(f"[CLARIFY] {question}")
    return {
        "status": "clarification_needed",
        "clarification_question": question,
        "options": options
    }


@tool("check_for_ambiguity", args_schema=CheckAmbiguityInput)
def check_for_ambiguity(request: str) -> dict:
    """
    Analyse une demande pour détecter les informations manquantes ou ambiguës.
    Toujours appeler ce tool en premier avant d'exécuter toute autre action.
    """
    # MOCK — sera remplacé par une vraie analyse Qwen J2-3
    ambiguities = []

    # Détection basique de mots-clés manquants (logique mock simple)
    if "devis" in request.lower() and "prix" not in request.lower():
        ambiguities.append("Prix unitaire manquant")
    if "email" in request.lower() and "@" not in request:
        ambiguities.append("Adresse email du destinataire manquante")
    if "réunion" in request.lower() and "date" not in request.lower():
        ambiguities.append("Date de la réunion manquante")

    is_ambiguous = len(ambiguities) > 0

    print(f"[AMBIGUITY CHECK] Ambigu : {is_ambiguous} | Problèmes : {ambiguities}")
    return {
        "is_ambiguous": is_ambiguous,
        "ambiguities": ambiguities,
        "confidence": 0.85 if not is_ambiguous else 0.45
    }


# LISTE EXPORTÉE (utilisée par l'agentic loop J2-4)
TOOLS = [
    send_email,
    schedule_meeting,
    generate_quote,
    clarify_input,
    check_for_ambiguity
]