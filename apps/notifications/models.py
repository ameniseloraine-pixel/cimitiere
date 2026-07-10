"""
Module Notifications — Alertes automatiques par email
Admin : nouvelles réservations, retards paiement, seuils critiques
Client : code MFA, confirmations, factures
"""

from django.db import models
from apps.users.models import Utilisateur


class TypeNotification(models.TextChoices):
    # MFA
    CODE_MFA = "MFA", "Code MFA"
    # Réservation
    NOUVELLE_RESERVATION = "NEW_RES", "Nouvelle réservation (admin)"
    CONFIRMATION_RESERVATION = "CONF_RES", "Confirmation réservation (client)"
    RESERVATION_VALIDEE = "VAL_RES", "Réservation validée (client)"
    RESERVATION_REJETEE = "REJ_RES", "Réservation rejetée (client)"
    # Finance
    FACTURE_EMISE = "FACT_EMISE", "Facture émise"
    RETARD_PAIEMENT = "RETARD", "Retard de paiement"
    # Concession
    ALERTE_EXPIRATION = "EXPIRE", "Alerte expiration concession"
    CONCESSION_EXPIREE = "EXPIREE", "Concession expirée"
    # Seuils
    SEUIL_CRITIQUE = "SEUIL", "Seuil places critiques"
    # Exhumation
    DEMANDE_EXHUMATION = "EXH_NEW", "Nouvelle demande exhumation"
    EXHUMATION_AUTORISEE = "EXH_OK", "Exhumation autorisée"


class StatutNotification(models.TextChoices):
    EN_ATTENTE = "PENDING", "En attente"
    ENVOYEE = "SENT", "Envoyée"
    ECHEC = "FAILED", "Échec"
    REESSAI = "RETRY", "Nouvelle tentative"


class Notification(models.Model):
    """
    Log de toutes les notifications envoyées.
    Géré par Celery pour l'envoi asynchrone.
    """
    destinataire = models.ForeignKey(
        Utilisateur, on_delete=models.CASCADE,
        related_name="notifications"
    )
    type_notification = models.CharField(
        max_length=15, choices=TypeNotification.choices
    )
    statut = models.CharField(
        max_length=10, choices=StatutNotification.choices,
        default=StatutNotification.EN_ATTENTE
    )
    sujet = models.CharField(max_length=255)
    corps_html = models.TextField()
    corps_texte = models.TextField(blank=True)

    # Métadonnées
    date_creation = models.DateTimeField(auto_now_add=True)
    date_envoi = models.DateTimeField(null=True, blank=True)
    tentatives = models.PositiveSmallIntegerField(default=0)
    erreur = models.TextField(blank=True)

    # Référence optionnelle à un objet métier
    reference_type = models.CharField(max_length=50, blank=True)
    reference_id = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        ordering = ["-date_creation"]
        indexes = [
            models.Index(fields=["statut", "date_creation"]),
            models.Index(fields=["destinataire", "type_notification"]),
        ]

    def __str__(self):
        return f"[{self.get_type_notification_display()}] → {self.destinataire.email} ({self.get_statut_display()})"
