"""
Module Réservations — Workflow de réservation et validation
Client → Soumission → Admin Validation → Facturation automatique
"""

from django.db import models
from django.utils import timezone
from simple_history.models import HistoricalRecords
from apps.users.models import Utilisateur
from apps.cartographie.models import Caveau


class StatutReservation(models.TextChoices):
    EN_ATTENTE = "ATTENTE", "En attente de validation"   # Orange
    VALIDEE = "VALIDEE", "Validée"                        # Rouge (caveau occupé)
    REJETEE = "REJETEE", "Rejetée"
    ANNULEE = "ANNULEE", "Annulée"


class Defunt(models.Model):
    """Informations sur le défunt (liées à la réservation)."""
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    date_naissance = models.DateField(null=True, blank=True)
    date_deces = models.DateField()
    lieu_deces = models.CharField(max_length=200, blank=True)
    nationalite = models.CharField(max_length=100, blank=True)
    acte_deces_numero = models.CharField(max_length=100, blank=True, verbose_name="N° acte de décès")
    acte_deces_fichier = models.FileField(
        upload_to="documents/actes_deces/",
        null=True, blank=True,
        verbose_name="Acte de décès (scan)"
    )

    class Meta:
        verbose_name = "Défunt"
        verbose_name_plural = "Défunts"
        ordering = ["-date_deces"]

    def __str__(self):
        return f"{self.prenom} {self.nom} (†{self.date_deces})"

    @property
    def age_au_deces(self):
        if self.date_naissance:
            delta = self.date_deces - self.date_naissance
            return delta.days // 365
        return None


class Reservation(models.Model):
    """
    Demande de réservation d'un caveau.
    Workflow : ATTENTE → VALIDEE (Admin) ou REJETEE
    """
    # Références
    numero_dossier = models.CharField(
        max_length=20, unique=True, verbose_name="N° dossier"
    )
    client = models.ForeignKey(
        Utilisateur, on_delete=models.PROTECT,
        related_name="reservations",
        limit_choices_to={"role": "CLIENT"}
    )
    caveau = models.ForeignKey(
        Caveau, on_delete=models.PROTECT, related_name="reservations"
    )
    defunt = models.OneToOneField(
        Defunt, on_delete=models.PROTECT,
        related_name="reservation"
    )

    # Statut & workflow
    statut = models.CharField(
        max_length=10,
        choices=StatutReservation.choices,
        default=StatutReservation.EN_ATTENTE
    )

    # Dates
    date_soumission = models.DateTimeField(auto_now_add=True)
    date_inhumation_souhaitee = models.DateField(
        null=True, blank=True,
        verbose_name="Date d'inhumation souhaitée"
    )
    date_validation = models.DateTimeField(null=True, blank=True)

    # Traitement admin
    validee_par = models.ForeignKey(
        Utilisateur, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="reservations_validees"
    )
    motif_rejet = models.TextField(blank=True)
    notes_admin = models.TextField(blank=True)

    # Audit
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Réservation"
        verbose_name_plural = "Réservations"
        ordering = ["-date_soumission"]

    def __str__(self):
        return f"Dossier {self.numero_dossier} — {self.defunt} [{self.get_statut_display()}]"

    def save(self, *args, **kwargs):
        # Générer numéro de dossier automatiquement
        if not self.numero_dossier:
            annee = timezone.now().year
            count = Reservation.objects.filter(
                date_soumission__year=annee
            ).count() + 1
            self.numero_dossier = f"RES-{annee}-{count:04d}"
        super().save(*args, **kwargs)

    def valider(self, admin_user):
        """Valide la réservation et met à jour le statut du caveau."""
        from apps.cartographie.models import StatutCaveau
        self.statut = StatutReservation.VALIDEE
        self.validee_par = admin_user
        self.date_validation = timezone.now()
        self.save()
        # Changer le caveau en Rouge (Occupé)
        self.caveau.changer_statut(
            StatutCaveau.OCCUPE,
            utilisateur=admin_user,
            raison=f"Réservation {self.numero_dossier} validée"
        )

    def rejeter(self, admin_user, motif=""):
        """Rejette la réservation et libère le caveau."""
        from apps.cartographie.models import StatutCaveau
        self.statut = StatutReservation.REJETEE
        self.validee_par = admin_user
        self.motif_rejet = motif
        self.save()
        # Remettre le caveau en Vert (Disponible)
        self.caveau.changer_statut(
            StatutCaveau.DISPONIBLE,
            utilisateur=admin_user,
            raison=f"Réservation {self.numero_dossier} rejetée"
        )
