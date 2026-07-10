"""
Module Concessions & Exhumations
Contrats de concession funéraire : temporaire / perpétuelle
Alertes d'échéance automatiques, procédures d'exhumation
"""

from django.db import models
from django.utils import timezone
from datetime import timedelta
from simple_history.models import HistoricalRecords
from apps.users.models import Utilisateur
from apps.reservations.models import Reservation


class TypeConcession(models.TextChoices):
    TEMPORAIRE_5 = "TEMP_5", "Temporaire — 5 ans"
    TEMPORAIRE_10 = "TEMP_10", "Temporaire — 10 ans"
    TEMPORAIRE_15 = "TEMP_15", "Temporaire — 15 ans"
    PERPETUELLE = "PERP", "Perpétuelle"
    FAMILIALE = "FAM", "Familiale"


DUREE_CONCESSION_ANNEES = {
    TypeConcession.TEMPORAIRE_5: 5,
    TypeConcession.TEMPORAIRE_10: 10,
    TypeConcession.TEMPORAIRE_15: 15,
    TypeConcession.PERPETUELLE: None,   # Pas d'expiration
    TypeConcession.FAMILIALE: None,
}


class StatutConcession(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    EXPIREE = "EXPIREE", "Expirée"
    RESILIEE = "RESILIEE", "Résiliée"
    RENOUVELEE = "RENOUVELEE", "Renouvelée"
    EN_ALERTE = "ALERTE", "En alerte d'expiration"


class Concession(models.Model):
    """
    Contrat de concession funéraire lié à une réservation validée.
    """
    numero_contrat = models.CharField(max_length=20, unique=True)
    reservation = models.OneToOneField(
        Reservation, on_delete=models.PROTECT, related_name="concession"
    )
    titulaire = models.ForeignKey(
        Utilisateur, on_delete=models.PROTECT, related_name="concessions"
    )
    type_concession = models.CharField(
        max_length=10, choices=TypeConcession.choices
    )
    statut = models.CharField(
        max_length=10, choices=StatutConcession.choices,
        default=StatutConcession.ACTIVE
    )

    # Dates
    date_debut = models.DateField()
    date_fin = models.DateField(null=True, blank=True)  # Null = perpétuelle
    date_signature = models.DateTimeField(auto_now_add=True)

    # Renouvellement
    date_dernier_renouvellement = models.DateField(null=True, blank=True)
    concession_precedente = models.ForeignKey(
        "self", on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="renouvellements"
    )

    # Documents
    contrat_pdf = models.FileField(
        upload_to="documents/contrats/", null=True, blank=True
    )
    notes = models.TextField(blank=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Concession"
        verbose_name_plural = "Concessions"
        ordering = ["-date_debut"]

    def __str__(self):
        return f"Concession {self.numero_contrat} — {self.titulaire.nom_complet}"

    def save(self, *args, **kwargs):
        if not self.numero_contrat:
            annee = timezone.now().year
            count = Concession.objects.filter(
                date_signature__year=annee
            ).count() + 1
            self.numero_contrat = f"CON-{annee}-{count:04d}"
        # Calculer la date de fin automatiquement
        if not self.date_fin:
            duree = DUREE_CONCESSION_ANNEES.get(self.type_concession)
            if duree:
                from dateutil.relativedelta import relativedelta
                self.date_fin = self.date_debut + relativedelta(years=duree)
        super().save(*args, **kwargs)

    @property
    def est_perpetuelle(self):
        return self.type_concession in [
            TypeConcession.PERPETUELLE, TypeConcession.FAMILIALE
        ]

    @property
    def jours_avant_expiration(self):
        if self.date_fin:
            delta = self.date_fin - timezone.now().date()
            return delta.days
        return None

    @property
    def necessite_alerte(self):
        """Déclenche une alerte si expiration dans moins de 90 jours."""
        j = self.jours_avant_expiration
        return j is not None and 0 < j <= 90

    def renouveler(self, nouveau_type=None):
        """Crée une nouvelle concession de renouvellement."""
        nouveau_type = nouveau_type or self.type_concession
        self.statut = StatutConcession.RENOUVELEE
        self.save()
        return Concession.objects.create(
            reservation=self.reservation,
            titulaire=self.titulaire,
            type_concession=nouveau_type,
            date_debut=self.date_fin or timezone.now().date(),
            concession_precedente=self,
        )


class StatutExhumation(models.TextChoices):
    DEMANDE = "DEMANDE", "Demande soumise"
    EN_INSTRUCTION = "INSTRUCT", "En instruction"
    AUTORISEE = "AUTORISEE", "Autorisée"
    REALISEE = "REALISEE", "Réalisée"
    REFUSEE = "REFUSEE", "Refusée"


class Exhumation(models.Model):
    """
    Procédure d'exhumation avec validation administrative et traçabilité.
    """
    numero_demande = models.CharField(max_length=20, unique=True)
    concession = models.ForeignKey(
        Concession, on_delete=models.PROTECT, related_name="exhumations"
    )
    demandeur = models.ForeignKey(
        Utilisateur, on_delete=models.PROTECT, related_name="demandes_exhumation"
    )
    statut = models.CharField(
        max_length=10, choices=StatutExhumation.choices,
        default=StatutExhumation.DEMANDE
    )

    # Motif
    motif = models.TextField(verbose_name="Motif de l'exhumation")
    destination_restes = models.TextField(
        blank=True, verbose_name="Destination des restes mortels"
    )

    # Dates
    date_demande = models.DateTimeField(auto_now_add=True)
    date_autorisation = models.DateTimeField(null=True, blank=True)
    date_realisation = models.DateField(null=True, blank=True)

    # Administration
    autorisee_par = models.ForeignKey(
        Utilisateur, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="exhumations_autorisees"
    )
    motif_refus = models.TextField(blank=True)

    # Documents légaux générés
    autorisation_pdf = models.FileField(
        upload_to="documents/exhumations/autorisations/",
        null=True, blank=True,
        verbose_name="Autorisation d'exhumation (PDF)"
    )
    proces_verbal_pdf = models.FileField(
        upload_to="documents/exhumations/pv/",
        null=True, blank=True,
        verbose_name="Procès-verbal (PDF)"
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = "Exhumation"
        verbose_name_plural = "Exhumations"
        ordering = ["-date_demande"]

    def __str__(self):
        return f"Exhumation {self.numero_demande} — {self.concession}"

    def save(self, *args, **kwargs):
        if not self.numero_demande:
            annee = timezone.now().year
            count = Exhumation.objects.filter(
                date_demande__year=annee
            ).count() + 1
            self.numero_demande = f"EXH-{annee}-{count:04d}"
        super().save(*args, **kwargs)
