"""
Module Finance — Facturation, paiements multi-canaux, suivi des soldes
Canaux : Mobile Money, Airtel Money, Espèces, Virement

SIMULATION MOBILE MONEY / AIRTEL MONEY :
N'étant pas une entreprise enregistrée auprès des opérateurs (MTN/Airtel),
ce projet simule le flux de paiement mobile via une API de test interne
(TransactionMobileMoney). Le flux reproduit fidèlement le comportement
réel : push de paiement -> code de confirmation -> validation/échec.
Voir apps/finance/services.py pour le moteur de simulation.
"""

from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator
from decimal import Decimal
from simple_history.models import HistoricalRecords
from apps.users.models import Utilisateur
from apps.reservations.models import Reservation


class CanalPaiement(models.TextChoices):
    MOBILE_MONEY = "MOBILE_MONEY", "Mobile Money (MTN)"
    AIRTEL_MONEY = "AIRTEL_MONEY", "Airtel Money"
    ESPECES = "ESPECES", "Espèces"
    VIREMENT = "VIREMENT", "Virement bancaire"
    CHEQUE = "CHEQUE", "Chèque"


CANAUX_MOBILE = [CanalPaiement.MOBILE_MONEY, CanalPaiement.AIRTEL_MONEY]


class StatutFacture(models.TextChoices):
    BROUILLON = "BROUILLON", "Brouillon"
    EMISE = "EMISE", "Émise"
    PARTIELLEMENT_PAYEE = "PARTIEL", "Partiellement payée"
    PAYEE = "PAYEE", "Payée"
    ANNULEE = "ANNULEE", "Annulée"
    EN_RETARD = "RETARD", "En retard"


class TypeTarif(models.TextChoices):
    CONCESSION_TEMP_5 = "TEMP_5", "Concession temporaire 5 ans"
    CONCESSION_TEMP_10 = "TEMP_10", "Concession temporaire 10 ans"
    CONCESSION_TEMP_15 = "TEMP_15", "Concession temporaire 15 ans"
    CONCESSION_PERP = "PERP", "Concession perpétuelle"
    CONCESSION_FAM = "FAM", "Concession familiale"
    RENOUVELLEMENT = "RENOUV", "Renouvellement"
    EXHUMATION = "EXHUM", "Autorisation d'exhumation"
    FRAIS_DOSSIER = "DOSSIER", "Frais de dossier"
    ENTRETIEN = "ENTRET", "Entretien"


class Tarif(models.Model):
    """Grille tarifaire configurable par l'admin."""
    type_tarif = models.CharField(
        max_length=10, choices=TypeTarif.choices, unique=True
    )
    montant_fcfa = models.DecimalField(
        max_digits=12, decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))]
    )
    description = models.TextField(blank=True)
    actif = models.BooleanField(default=True)
    date_modification = models.DateTimeField(auto_now=True)
    modifie_par = models.ForeignKey(
        Utilisateur, on_delete=models.SET_NULL, null=True, blank=True
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Tarif"
        verbose_name_plural = "Tarifs"

    def __str__(self):
        return f"{self.get_type_tarif_display()} — {self.montant_fcfa:,.0f} FCFA"


class Facture(models.Model):
    """
    Facture générée automatiquement après validation de réservation.
    Supporte les paiements partiels.
    """
    numero_facture = models.CharField(max_length=20, unique=True)
    reservation = models.ForeignKey(
        Reservation, on_delete=models.PROTECT,
        related_name="factures", null=True, blank=True
    )
    client = models.ForeignKey(
        Utilisateur, on_delete=models.PROTECT, related_name="factures"
    )
    statut = models.CharField(
        max_length=10,
        choices=StatutFacture.choices,
        default=StatutFacture.BROUILLON
    )

    # Montants
    sous_total = models.DecimalField(
        max_digits=12, decimal_places=2,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))]
    )
    tva_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0")
    )
    montant_tva = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0")
    )
    montant_total = models.DecimalField(
        max_digits=12, decimal_places=2,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))]
    )
    montant_paye = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0")
    )

    # Dates
    date_emission = models.DateTimeField(auto_now_add=True)
    date_echeance = models.DateField(null=True, blank=True)

    # PDF généré
    pdf_fichier = models.FileField(
        upload_to="documents/factures/", null=True, blank=True
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = "Facture"
        verbose_name_plural = "Factures"
        ordering = ["-date_emission"]

    def __str__(self):
        return f"Facture {self.numero_facture} — {self.client.nom_complet} ({self.montant_total:,.0f} FCFA)"

    def save(self, *args, **kwargs):
        if not self.numero_facture:
            annee = timezone.now().year
            mois = timezone.now().month
            count = Facture.objects.filter(
                date_emission__year=annee, date_emission__month=mois
            ).count() + 1
            self.numero_facture = f"FAC-{annee}{mois:02d}-{count:04d}"
        super().save(*args, **kwargs)

    @property
    def solde_restant(self):
        return self.montant_total - self.montant_paye

    @property
    def est_soldee(self):
        return self.montant_paye >= self.montant_total

    @property
    def est_en_retard(self):
        if self.date_echeance and not self.est_soldee:
            return timezone.now().date() > self.date_echeance
        return False

    def calculer_totaux(self):
        """Recalcule les totaux depuis les lignes de facture (requête fraîche,
        sans dépendre d'un éventuel cache prefetch_related)."""
        self.sous_total = LigneFacture.objects.filter(facture_id=self.pk).aggregate(
            total=models.Sum("montant_total")
        )["total"] or Decimal("0")
        self.montant_tva = self.sous_total * (self.tva_pct / 100)
        self.montant_total = self.sous_total + self.montant_tva
        self.save(update_fields=["sous_total", "montant_tva", "montant_total"])

    def mettre_a_jour_statut(self):
        """Met à jour le statut selon les paiements reçus."""
        if self.montant_paye == 0:
            self.statut = StatutFacture.EMISE
        elif self.montant_paye < self.montant_total:
            self.statut = StatutFacture.PARTIELLEMENT_PAYEE
        else:
            self.statut = StatutFacture.PAYEE
        if self.est_en_retard and self.statut != StatutFacture.PAYEE:
            self.statut = StatutFacture.EN_RETARD
        self.save(update_fields=["statut"])


class LigneFacture(models.Model):
    """Ligne détaillée d'une facture."""
    facture = models.ForeignKey(
        Facture, on_delete=models.CASCADE, related_name="lignes"
    )
    description = models.CharField(max_length=300)
    type_tarif = models.CharField(
        max_length=10, choices=TypeTarif.choices, blank=True
    )
    quantite = models.PositiveIntegerField(default=1)
    prix_unitaire = models.DecimalField(max_digits=12, decimal_places=2)
    montant_total = models.DecimalField(max_digits=12, decimal_places=2)

    def save(self, *args, **kwargs):
        self.montant_total = self.quantite * self.prix_unitaire
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Ligne de facture"

    def __str__(self):
        return f"{self.description} — {self.montant_total:,.0f} FCFA"


class Paiement(models.Model):
    """
    Transaction de paiement (partiel ou total) sur une facture.
    Multi-canal : Mobile Money, Airtel Money, Espèces, Virement.

    Pour les canaux mobiles, ce modèle est lié à une TransactionMobileMoney
    qui simule le cycle de vie réel d'un paiement opérateur.
    """
    facture = models.ForeignKey(
        Facture, on_delete=models.PROTECT, related_name="paiements"
    )
    canal = models.CharField(max_length=15, choices=CanalPaiement.choices)
    montant = models.DecimalField(
        max_digits=12, decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))]
    )
    # Référence transaction externe (Mobile Money, etc.)
    reference_transaction = models.CharField(max_length=100, blank=True)
    telephone_paiement = models.CharField(max_length=20, blank=True)

    date_paiement = models.DateTimeField(auto_now_add=True)
    enregistre_par = models.ForeignKey(
        Utilisateur, on_delete=models.SET_NULL, null=True
    )
    notes = models.TextField(blank=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Paiement"
        verbose_name_plural = "Paiements"
        ordering = ["-date_paiement"]

    def __str__(self):
        return (
            f"Paiement {self.montant:,.0f} FCFA "
            f"({self.get_canal_display()}) — {self.facture.numero_facture}"
        )

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Mettre à jour le montant payé sur la facture.
        # On utilise une requête fraîche (.filter().aggregate()) pour éviter
        # de lire un queryset prefetch_related mis en cache avant la
        # création de ce paiement.
        total_paye = Paiement.objects.filter(facture_id=self.facture_id).aggregate(
            total=models.Sum("montant")
        )["total"] or Decimal("0")
        Facture.objects.filter(pk=self.facture_id).update(montant_paye=total_paye)
        self.facture.refresh_from_db(fields=["montant_paye"])
        self.facture.mettre_a_jour_statut()


# ─── Simulation Mobile Money / Airtel Money ──────────────────────────────────

class StatutTransactionMobile(models.TextChoices):
    INITIEE = "INITIEE", "Initiée"
    EN_ATTENTE_CONFIRMATION = "ATTENTE", "En attente de confirmation"
    CONFIRMEE = "CONFIRMEE", "Confirmée"
    ECHOUEE = "ECHOUEE", "Échouée"
    EXPIREE = "EXPIREE", "Expirée"
    ANNULEE = "ANNULEE", "Annulée"


class TransactionMobileMoney(models.Model):
    """
    Simulation du cycle de vie d'une transaction Mobile Money / Airtel Money.

    Ce modèle reproduit le flux réel d'un agrégateur de paiement mobile :
    1. INITIEE : le client demande le paiement (push USSD simulé envoyé)
    2. ATTENTE : un code de confirmation à 6 chiffres est généré et envoyé
       par email (faisant office de notification push opérateur simulée)
    3. CONFIRMEE / ECHOUEE / EXPIREE : issue de la transaction selon que
       le client confirme avec le bon code dans le délai imparti

    En l'absence d'un compte marchand réel auprès de MTN MoMo ou Airtel
    Money (nécessitant un statut d'entreprise enregistrée), ce module fait
    office d'API de test interne avec un comportement fonctionnellement
    identique à celui d'un agrégateur réel.
    """
    reference = models.CharField(max_length=30, unique=True, verbose_name="Référence transaction")
    facture = models.ForeignKey(
        Facture, on_delete=models.PROTECT, related_name="transactions_mobile"
    )
    initiateur = models.ForeignKey(
        Utilisateur, on_delete=models.PROTECT, related_name="transactions_mobile"
    )
    canal = models.CharField(max_length=15, choices=CanalPaiement.choices)
    telephone = models.CharField(max_length=20, verbose_name="Numéro Mobile Money")
    montant = models.DecimalField(
        max_digits=12, decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))]
    )

    statut = models.CharField(
        max_length=10,
        choices=StatutTransactionMobile.choices,
        default=StatutTransactionMobile.INITIEE,
    )

    code_confirmation = models.CharField(max_length=6, blank=True)
    tentatives = models.PositiveSmallIntegerField(default=0)

    date_initiation = models.DateTimeField(auto_now_add=True)
    date_expiration = models.DateTimeField()
    date_confirmation = models.DateTimeField(null=True, blank=True)

    paiement_resultant = models.OneToOneField(
        Paiement, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="transaction_mobile"
    )

    motif_echec = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "Transaction Mobile Money (simulation)"
        verbose_name_plural = "Transactions Mobile Money (simulation)"
        ordering = ["-date_initiation"]

    def __str__(self):
        return f"{self.reference} — {self.get_canal_display()} — {self.montant:,.0f} FCFA [{self.get_statut_display()}]"

    def save(self, *args, **kwargs):
        if not self.reference:
            prefix = "MTN" if self.canal == CanalPaiement.MOBILE_MONEY else "AIRTEL"
            annee = timezone.now().year
            count = TransactionMobileMoney.objects.filter(
                date_initiation__year=annee
            ).count() + 1
            self.reference = f"{prefix}-{annee}-{count:06d}"
        super().save(*args, **kwargs)

    @property
    def est_expiree(self):
        return timezone.now() > self.date_expiration

    @property
    def est_en_attente_valide(self):
        return (
            self.statut == StatutTransactionMobile.EN_ATTENTE_CONFIRMATION
            and not self.est_expiree
            and self.tentatives < 3
        )
