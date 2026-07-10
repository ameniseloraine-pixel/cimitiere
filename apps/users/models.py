"""
Module Users — Gestion des utilisateurs et RBAC
Rôles : Administrateur, Agent terrain, Secrétariat, Client
MFA obligatoire par email
"""

import random
import string
from datetime import timedelta

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone
from simple_history.models import HistoricalRecords


class RoleUtilisateur(models.TextChoices):
    ADMINISTRATEUR = "ADMIN", "Administrateur"
    AGENT_TERRAIN = "AGENT", "Agent de terrain"
    SECRETARIAT = "SECR", "Secrétariat"
    CLIENT = "CLIENT", "Client (citoyen)"


class UtilisateurManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("L'email est obligatoire")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("role", RoleUtilisateur.ADMINISTRATEUR)
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("mfa_activee", False)  # superuser bypass en dev
        return self.create_user(email, password, **extra_fields)


class Utilisateur(AbstractBaseUser, PermissionsMixin):
    """
    Utilisateur personnalisé avec RBAC et MFA obligatoire.
    L'email est l'identifiant principal (pas le username).
    """
    email = models.EmailField(unique=True, verbose_name="Email")
    nom = models.CharField(max_length=100, verbose_name="Nom")
    prenom = models.CharField(max_length=100, verbose_name="Prénom")
    telephone = models.CharField(max_length=20, blank=True, verbose_name="Téléphone")
    role = models.CharField(
        max_length=10,
        choices=RoleUtilisateur.choices,
        default=RoleUtilisateur.CLIENT,
        verbose_name="Rôle"
    )

    # Statuts
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    # MFA
    mfa_activee = models.BooleanField(default=True, verbose_name="MFA activée")

    # Métadonnées
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    derniere_connexion_ip = models.GenericIPAddressField(null=True, blank=True)

    # Audit trail
    history = HistoricalRecords()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["nom", "prenom"]

    objects = UtilisateurManager()

    class Meta:
        verbose_name = "Utilisateur"
        verbose_name_plural = "Utilisateurs"
        ordering = ["-date_creation"]

    def __str__(self):
        return f"{self.prenom} {self.nom} ({self.get_role_display()})"

    @property
    def nom_complet(self):
        return f"{self.prenom} {self.nom}"

    # ── Permissions par rôle ──────────────────────────────────────────────────
    @property
    def est_admin(self):
        return self.role == RoleUtilisateur.ADMINISTRATEUR

    @property
    def peut_voir_finances(self):
        return self.role in [RoleUtilisateur.ADMINISTRATEUR, RoleUtilisateur.SECRETARIAT]

    @property
    def peut_modifier_carte(self):
        return self.role in [RoleUtilisateur.ADMINISTRATEUR, RoleUtilisateur.AGENT_TERRAIN]

    @property
    def peut_valider_reservations(self):
        return self.role in [RoleUtilisateur.ADMINISTRATEUR, RoleUtilisateur.SECRETARIAT]


class CodeMFA(models.Model):
    """
    Code OTP à 6 chiffres envoyé par email pour la MFA.
    Valide 10 minutes, usage unique.
    """
    utilisateur = models.ForeignKey(
        Utilisateur,
        on_delete=models.CASCADE,
        related_name="codes_mfa"
    )
    code = models.CharField(max_length=6, verbose_name="Code OTP")
    cree_le = models.DateTimeField(auto_now_add=True)
    expire_le = models.DateTimeField()
    utilise = models.BooleanField(default=False)
    tentatives = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "Code MFA"
        verbose_name_plural = "Codes MFA"
        ordering = ["-cree_le"]

    def save(self, *args, **kwargs):
        if not self.pk:
            # Générer code 6 chiffres
            self.code = "".join(random.choices(string.digits, k=6))
            # Expiration dans 10 minutes
            from django.conf import settings
            minutes = getattr(settings, "MFA_CODE_VALIDITY_MINUTES", 10)
            self.expire_le = timezone.now() + timedelta(minutes=minutes)
        super().save(*args, **kwargs)

    @property
    def est_valide(self):
        return (
            not self.utilise
            and timezone.now() < self.expire_le
            and self.tentatives < 3
        )

    def marquer_utilise(self):
        self.utilise = True
        self.save(update_fields=["utilise"])

    def __str__(self):
        return f"MFA {self.utilisateur.email} — {self.cree_le.strftime('%H:%M')}"


class SessionUtilisateur(models.Model):
    """
    Suivi des sessions actives pour l'audit trail.
    """
    utilisateur = models.ForeignKey(
        Utilisateur,
        on_delete=models.CASCADE,
        related_name="sessions"
    )
    token_jti = models.CharField(max_length=255, unique=True)  # JWT ID
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)
    expire_le = models.DateTimeField()
    revoquee = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Session"
        verbose_name_plural = "Sessions"
        ordering = ["-cree_le"]

    @property
    def est_active(self):
        return not self.revoquee and timezone.now() < self.expire_le

    def __str__(self):
        return f"Session {self.utilisateur.email} — {self.ip_address}"
