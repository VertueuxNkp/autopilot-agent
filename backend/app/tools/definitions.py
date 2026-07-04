from langchain.tools import tool
from pydantic import BaseModel
from typing import Optional
import re


# ─── SCHÉMAS D'ENTRÉE DES TOOLS ────────────────────────────────────────────────

class SendEmailInput(BaseModel):
    recipient: str
    subject: str
    body: str

class ScheduleMeetingInput(BaseModel):
    attendee: str
    date: str
    time: str
    duration: int

class GenerateQuoteInput(BaseModel):
    customer_name: str
    items: list[str]
    prices: list[float]
    discount: Optional[float] = 0.0
    tva: Optional[float] = 18.0  # TVA Bénin par défaut

class ClarifyInputSchema(BaseModel):
    ambiguous_request: str
    options: list[str]

class CheckAmbiguityInput(BaseModel):
    request: str


# ─── DÉFINITION DES 5 TOOLS ────────────────────────────────────────────────────

@tool("send_email", args_schema=SendEmailInput)
def send_email(recipient: str, subject: str, body: str) -> dict:
    """
    Envoie un email à un destinataire.
    À utiliser quand l'utilisateur veut envoyer un message ou un devis par email.
    Le recipient doit être une adresse email valide contenant @.
    """
    # Validation de l'adresse email
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, recipient):
        raise ValueError(
            f"Adresse email invalide : '{recipient}'. "
            f"Une adresse email doit contenir @ et un domaine valide (ex: jean@example.com)"
        )

    # MOCK — sera remplacé par SMTP réel J5
    print(f"[MOCK] Envoi email à {recipient} | Sujet : {subject}")
    return {
        "status": "success",
        "message_id": "mock-email-001",
        "recipient": recipient,
        "subject": subject,
        "body": body
    }


@tool("schedule_meeting", args_schema=ScheduleMeetingInput)
def schedule_meeting(attendee: str, date: str, time: str, duration: int) -> dict:
    """
    Planifie une réunion avec un participant.
    À utiliser quand l'utilisateur veut fixer un rendez-vous ou une réunion.
    La date doit être au format JJ/MM/AAAA et l'heure au format HH:MM.
    """
    # Validation basique de la durée
    if duration <= 0 or duration > 480:
        raise ValueError(
            f"Durée invalide : {duration} minutes. "
            f"La durée doit être entre 1 et 480 minutes (8 heures max)."
        )

    # MOCK — sera remplacé par Google Calendar J5
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
    discount: float = 0.0,
    tva: float = 18.0
) -> dict:
    """
    Génère un devis complet pour un client avec TVA et remise.
    À utiliser quand l'utilisateur veut créer un devis commercial.
    Les items et prices doivent avoir le même nombre d'éléments.
    """
    # Validation
    if len(items) != len(prices):
        raise ValueError(
            f"Le nombre d'articles ({len(items)}) ne correspond pas "
            f"au nombre de prix ({len(prices)}). "
            f"Chaque article doit avoir un prix."
        )

    if any(p < 0 for p in prices):
        raise ValueError("Les prix ne peuvent pas être négatifs.")

    if discount < 0 or discount > 100:
        raise ValueError(f"La remise ({discount}%) doit être entre 0 et 100.")

    # Calcul complet
    subtotal_ht = sum(prices)
    discount_amount = subtotal_ht * (discount / 100)
    total_ht = subtotal_ht - discount_amount
    tva_amount = total_ht * (tva / 100)
    total_ttc = total_ht + tva_amount

    print(f"[MOCK] Devis généré pour {customer_name} | Total TTC : {total_ttc:.2f}")
    return {
        "status": "success",
        "quote_id": "mock-quote-001",
        "customer_name": customer_name,
        "items": items,
        "prices": prices,
        "discount_percent": discount,
        "discount_amount": round(discount_amount, 2),
        "subtotal_ht": round(subtotal_ht, 2),
        "tva_percent": tva,
        "tva_amount": round(tva_amount, 2),
        "total_ttc": round(total_ttc, 2)
    }


@tool("clarify_input", args_schema=ClarifyInputSchema)
def clarify_input(ambiguous_request: str, options: list[str]) -> dict:
    """
    Pose une question de clarification à l'utilisateur.
    À utiliser quand la demande est ambiguë et nécessite plus d'informations.
    Ne poser qu'une seule question à la fois.
    """
    question = f"Précision nécessaire : {ambiguous_request}"
    if options:
        question += f" ({', '.join(options)})"

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
    ambiguities = []
    request_lower = request.lower()

    # Détection devis
    if any(word in request_lower for word in ["devis", "facture", "prix"]):
        if not any(word in request_lower for word in ["euro", "€", "fcfa", "franc", "000"]):
            ambiguities.append("Prix unitaire manquant")
        if not any(word in request_lower for word in ["article", "produit", "service", "item"]):
            ambiguities.append("Article ou service non spécifié")

    # Détection email
    if any(word in request_lower for word in ["email", "mail", "envoie", "envoyer"]):
        if "@" not in request:
            ambiguities.append("Adresse email du destinataire manquante")

    # Détection réunion
    if any(word in request_lower for word in ["réunion", "meeting", "rendez-vous", "rdv"]):
        if not any(word in request_lower for word in ["lundi", "mardi", "mercredi", "jeudi",
                                                        "vendredi", "samedi", "dimanche",
                                                        "janvier", "février", "mars",
                                                        "aujourd'hui", "demain"]):
            ambiguities.append("Date de la réunion manquante")
        if not any(char.isdigit() for char in request):
            ambiguities.append("Heure de la réunion manquante")

    is_ambiguous = len(ambiguities) > 0

    print(f"[AMBIGUITY CHECK] Ambigu : {is_ambiguous} | Problèmes : {ambiguities}")
    return {
        "is_ambiguous": is_ambiguous,
        "ambiguities": ambiguities,
        "confidence": 0.90 if not is_ambiguous else 0.40
    }


# ─── LISTE EXPORTÉE ─────────────────────────────────────────────────────────────
TOOLS = [
    send_email,
    schedule_meeting,
    generate_quote,
    clarify_input,
    check_for_ambiguity
]