"""
Services utilisateurs — MFA, JWT, Emails
"""

import jwt
import requests
from datetime import datetime, timedelta, timezone as dt_timezone
from django.conf import settings

from .models import Utilisateur, CodeMFA


def generer_et_envoyer_code_mfa(user: Utilisateur) -> CodeMFA:
    """
    Génère un code MFA à 6 chiffres et l'envoie par email.
    Invalide les anciens codes non utilisés.
    """
    CodeMFA.objects.filter(utilisateur=user, utilise=False).update(utilise=True)
    code_mfa = CodeMFA.objects.create(utilisateur=user)
    _envoyer_email_mfa(user, code_mfa.code)
    return code_mfa


def _envoyer_email_mfa(user: Utilisateur, code: str):
    """Envoi du code MFA par email via l'API Brevo (HTTPS, pas SMTP)."""
    sujet = f"[Cimetière] Votre code de connexion : {code}"
    corps_html = f"""
    <p>Bonjour {user.prenom},</p>
    <p>Votre code de vérification est : <strong style="font-size:20px">{code}</strong></p>
    <p>Ce code est valable 10 minutes et ne peut être utilisé qu'une seule fois.</p>
    <p>Si vous n'avez pas tenté de vous connecter, ignorez cet email et changez votre mot de passe.</p>
    <p>Cordialement,<br>L'équipe de gestion du cimetière</p>
    """

    response = requests.post(
        "https://api.brevo.com/v3/smtp/email",
        headers={
            "api-key": settings.BREVO_API_KEY,
            "Content-Type": "application/json",
            "accept": "application/json",
        },
        json={
            "sender": {"name": "Gestion Cimetière", "email": settings.DEFAULT_FROM_EMAIL},
            "to": [{"email": user.email}],
            "subject": sujet,
            "htmlContent": corps_html,
        },
        timeout=10,
    )

    if response.status_code >= 400:
        raise Exception(f"Échec envoi email Brevo: {response.status_code} - {response.text}")


def creer_tokens_jwt(user: Utilisateur) -> dict:
    """Génère les tokens JWT access + refresh."""
    now = datetime.now(dt_timezone.utc)

    access_payload = {
        "user_id": user.id,
        "email": user.email,
        "role": user.role,
        "type": "access",
        "iat": now,
        "exp": now + settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"],
    }

    refresh_payload = {
        "user_id": user.id,
        "type": "refresh",
        "iat": now,
        "exp": now + settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"],
    }

    access_token = jwt.encode(access_payload, settings.SECRET_KEY, algorithm="HS256")
    refresh_token = jwt.encode(refresh_payload, settings.SECRET_KEY, algorithm="HS256")

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


def verifier_token_jwt(token: str, token_type: str = "access") -> dict | None:
    """Vérifie et décode un token JWT. Retourne le payload ou None."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        if payload.get("type") != token_type:
            return None
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
