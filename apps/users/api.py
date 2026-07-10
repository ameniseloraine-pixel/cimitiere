"""
API Authentification — Login, MFA, Refresh, Logout, CRUD Utilisateurs
"""

from datetime import timedelta
from typing import Optional

from django.contrib.auth import authenticate
from django.utils import timezone
from ninja import Router, Schema
from ninja.security import HttpBearer
import jwt
from django.conf import settings

from .models import Utilisateur, CodeMFA, RoleUtilisateur
from .services import (
    generer_et_envoyer_code_mfa,
    creer_tokens_jwt,
    verifier_token_jwt,
)

router = Router()


# ─── Schemas (Pydantic via Ninja) ─────────────────────────────────────────────

class LoginSchema(Schema):
    email: str
    password: str

class VerifyMFASchema(Schema):
    email: str
    code: str

class TokenSchema(Schema):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class MFARequiredSchema(Schema):
    message: str
    email: str
    mfa_requis: bool = True

class UtilisateurCreateSchema(Schema):
    email: str
    password: str
    nom: str
    prenom: str
    telephone: Optional[str] = ""
    role: str = RoleUtilisateur.CLIENT

class UtilisateurCreateAdminSchema(Schema):
    email: str
    password: str
    nom: str
    prenom: str
    telephone: Optional[str] = ""
    role: str

class UtilisateurOutSchema(Schema):
    id: int
    email: str
    nom: str
    prenom: str
    role: str
    is_active: bool
    date_creation: str

    @staticmethod
    def from_orm(user):
        return UtilisateurOutSchema(
            id=user.id,
            email=user.email,
            nom=user.nom,
            prenom=user.prenom,
            role=user.role,
            is_active=user.is_active,
            date_creation=user.date_creation.isoformat(),
        )

class MessageSchema(Schema):
    message: str

class ErrorSchema(Schema):
    detail: str


# ─── Auth Bearer ──────────────────────────────────────────────────────────────

class AuthBearer(HttpBearer):
    def authenticate(self, request, token: str):
        payload = verifier_token_jwt(token)
        if payload:
            try:
                return Utilisateur.objects.get(id=payload["user_id"])
            except Utilisateur.DoesNotExist:
                return None
        return None

auth = AuthBearer()


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/login", response={200: MFARequiredSchema, 401: ErrorSchema}, auth=None)
def login(request, data: LoginSchema):
    """
    Étape 1 : Login avec email/password.
    Envoie un code MFA par email si les credentials sont valides.
    """
    user = authenticate(request, username=data.email, password=data.password)
    if not user:
        return 401, {"detail": "Email ou mot de passe incorrect."}
    if not user.is_active:
        return 401, {"detail": "Compte désactivé. Contactez l'administration."}

    # Envoyer le code MFA
    generer_et_envoyer_code_mfa(user)

    return 200, {
        "message": f"Code MFA envoyé à {user.email}. Valide 10 minutes.",
        "email": user.email,
        "mfa_requis": True,
    }


@router.post("/verify-mfa", response={200: TokenSchema, 401: ErrorSchema, 429: ErrorSchema}, auth=None)
def verify_mfa(request, data: VerifyMFASchema):
    """
    Étape 2 : Vérification du code MFA.
    Retourne les tokens JWT si le code est valide.
    """
    try:
        user = Utilisateur.objects.get(email=data.email)
    except Utilisateur.DoesNotExist:
        return 401, {"detail": "Utilisateur introuvable."}

    # Récupérer le dernier code valide
    code_mfa = (
        CodeMFA.objects.filter(utilisateur=user, utilise=False)
        .order_by("-cree_le")
        .first()
    )

    if not code_mfa or not code_mfa.est_valide:
        return 401, {"detail": "Code expiré ou invalide. Reconnectez-vous."}

    # Vérifier le code
    code_mfa.tentatives += 1
    code_mfa.save(update_fields=["tentatives"])

    if code_mfa.tentatives > 3:
        return 429, {"detail": "Trop de tentatives. Reconnectez-vous."}

    if code_mfa.code != data.code:
        return 401, {"detail": f"Code incorrect. {3 - code_mfa.tentatives} tentative(s) restante(s)."}

    # Code valide → marquer utilisé
    code_mfa.marquer_utilise()

    # Générer les tokens JWT
    tokens = creer_tokens_jwt(user)
    return 200, tokens


@router.post("/refresh", response={200: TokenSchema, 401: ErrorSchema}, auth=None)
def refresh_token(request, refresh_token: str):
    """Renouvelle le token d'accès via le refresh token."""
    payload = verifier_token_jwt(refresh_token, token_type="refresh")
    if not payload:
        return 401, {"detail": "Refresh token invalide ou expiré."}
    try:
        user = Utilisateur.objects.get(id=payload["user_id"])
        tokens = creer_tokens_jwt(user)
        return 200, tokens
    except Utilisateur.DoesNotExist:
        return 401, {"detail": "Utilisateur introuvable."}


@router.get("/me", response={200: UtilisateurOutSchema}, auth=auth)
def get_profile(request):
    """Retourne le profil de l'utilisateur connecté."""
    return 200, UtilisateurOutSchema.from_orm(request.auth)


@router.post("/register", response={201: UtilisateurOutSchema, 400: ErrorSchema}, auth=None)
def register(request, data: UtilisateurCreateSchema):
    """Création d'un compte client (auto-inscription)."""
    if Utilisateur.objects.filter(email=data.email).exists():
        return 400, {"detail": "Un compte existe déjà avec cet email."}
    user = Utilisateur.objects.create_user(
        email=data.email,
        password=data.password,
        nom=data.nom,
        prenom=data.prenom,
        telephone=data.telephone or "",
        role=RoleUtilisateur.CLIENT,  # Toujours CLIENT à l'auto-inscription
    )
    return 201, UtilisateurOutSchema.from_orm(user)


@router.post("/utilisateurs", response={201: UtilisateurOutSchema, 403: ErrorSchema, 400: ErrorSchema}, auth=auth)
def creer_utilisateur(request, data: UtilisateurCreateAdminSchema):
    """Création d'un compte par un admin, avec choix du rôle (Agent, Secrétariat, Admin, Client)."""
    if not request.auth.est_admin:
        return 403, {"detail": "Seul un administrateur peut créer un utilisateur."}
    if Utilisateur.objects.filter(email=data.email).exists():
        return 400, {"detail": "Un compte existe déjà avec cet email."}
    roles_valides = (
        RoleUtilisateur.ADMINISTRATEUR,
        RoleUtilisateur.AGENT_TERRAIN,
        RoleUtilisateur.SECRETARIAT,
        RoleUtilisateur.CLIENT,
    )
    if data.role not in roles_valides:
        return 400, {"detail": "Rôle invalide."}
    user = Utilisateur.objects.create_user(
        email=data.email,
        password=data.password,
        nom=data.nom,
        prenom=data.prenom,
        telephone=data.telephone or "",
        role=data.role,
    )
    return 201, UtilisateurOutSchema.from_orm(user)


@router.get("/utilisateurs", response=list[UtilisateurOutSchema], auth=auth)
def liste_utilisateurs(request):
    """Liste tous les utilisateurs (Admin seulement)."""
    if not request.auth.est_admin:
        return []  # 403 géré par middleware
    users = Utilisateur.objects.all().order_by("nom")
    return [UtilisateurOutSchema.from_orm(u) for u in users]