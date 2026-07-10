"""
Services utilisateurs — MFA, JWT, Emails
"""

import jwt
from datetime import datetime, timedelta, timezone as dt_timezone
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

from .models import Utilisateur, CodeMFA


def generer_et_envoyer_code_mfa(user: Utilisateur) -> CodeMFA:
    """
    Génère un code MFA à 6 chiffres et l'envoie par email.
    Invalide les anciens codes non utilisés.
    """
    # Invalider les anciens codes
    CodeMFA.objects.filter(utilisateur=user, utilise=False).update(utilise=True)

    # Créer le nouveau code (auto-généré dans save())
    code_mfa = CodeMFA.objects.create(utilisateur=user)

    # Envoyer l'email
    _envoyer_email_mfa(user, code_mfa.code)

    return code_mfa


def _envoyer_email_mfa(user: Utilisateur, code: str):
    """Envoi du code MFA par email."""
    sujet = f"[Cimetière] Votre code de connexion : {code}"
    corps = f"""
Bonjour {user.prenom},

Votre code de vérification est : {code}

Ce code est valable 10 minutes et ne peut être utilisé qu'une seule fois.

Si vous n'avez pas tenté de vous connecter, ignorez cet email et changez votre mot de passe.

Cordialement,
L'équipe de gestion du cimetière
    """.strip()

    send_mail(
        subject=sujet,
        message=corps,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )


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
