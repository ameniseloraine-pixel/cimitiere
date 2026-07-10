"""
Services Finance — Création automatique de factures
"""

from decimal import Decimal
from django.utils import timezone
from datetime import timedelta

from .models import Facture, LigneFacture, Tarif, TypeTarif, StatutFacture
from apps.concessions.models import TypeConcession


# Mapping type de concession (par défaut, modifiable via TypeConcession) → TypeTarif
MAPPING_TYPE_CONCESSION_TARIF = {
    "TEMP_5": TypeTarif.CONCESSION_TEMP_5,
    "TEMP_10": TypeTarif.CONCESSION_TEMP_10,
    "TEMP_15": TypeTarif.CONCESSION_TEMP_15,
    "PERP": TypeTarif.CONCESSION_PERP,
    "FAM": TypeTarif.CONCESSION_FAM,
}


def _get_tarif(type_tarif: str) -> Decimal:
    """Récupère le montant d'un tarif actif, ou 0 si non configuré."""
    tarif = Tarif.objects.filter(type_tarif=type_tarif, actif=True).first()
    return tarif.montant_fcfa if tarif else Decimal("0")


def creer_facture_pour_reservation(reservation, type_concession_defaut="TEMP_10"):
    """
    Crée automatiquement une facture (statut EMISE) après validation
    d'une réservation. Inclut :
    - Frais de dossier
    - Tarif de concession (par défaut TEMP_10, ajustable plus tard)

    Retourne l'objet Facture créé.
    """
    facture = Facture.objects.create(
        reservation=reservation,
        client=reservation.client,
        statut=StatutFacture.BROUILLON,
        tva_pct=Decimal("0"),  # TVA configurable si applicable
        date_echeance=timezone.now().date() + timedelta(days=30),
    )

    # Ligne 1 : Frais de dossier
    montant_dossier = _get_tarif(TypeTarif.FRAIS_DOSSIER)
    LigneFacture.objects.create(
        facture=facture,
        description="Frais de dossier — Traitement de la demande de réservation",
        type_tarif=TypeTarif.FRAIS_DOSSIER,
        quantite=1,
        prix_unitaire=montant_dossier,
    )

    # Ligne 2 : Concession funéraire
    type_tarif_concession = MAPPING_TYPE_CONCESSION_TARIF.get(
        type_concession_defaut, TypeTarif.CONCESSION_TEMP_10
    )
    montant_concession = _get_tarif(type_tarif_concession)
    LigneFacture.objects.create(
        facture=facture,
        description=(
            f"Concession funéraire — {reservation.caveau.reference_complete} "
            f"({dict(TypeConcession.choices).get(type_concession_defaut, type_concession_defaut)})"
        ),
        type_tarif=type_tarif_concession,
        quantite=1,
        prix_unitaire=montant_concession,
    )

    # Calculer les totaux
    facture.calculer_totaux()
    facture.refresh_from_db()

    # Émettre directement (workflow : validation = facturation immédiate)
    facture.statut = StatutFacture.EMISE
    facture.save(update_fields=["statut"])

    return facture


def initialiser_tarifs_par_defaut():
    """
    Crée la grille tarifaire par défaut si elle n'existe pas.
    À exécuter via une migration de données ou une commande management.
    """
    tarifs_defaut = {
        TypeTarif.CONCESSION_TEMP_5: Decimal("150000"),
        TypeTarif.CONCESSION_TEMP_10: Decimal("250000"),
        TypeTarif.CONCESSION_TEMP_15: Decimal("350000"),
        TypeTarif.CONCESSION_PERP: Decimal("1000000"),
        TypeTarif.CONCESSION_FAM: Decimal("1500000"),
        TypeTarif.RENOUVELLEMENT: Decimal("100000"),
        TypeTarif.EXHUMATION: Decimal("75000"),
        TypeTarif.FRAIS_DOSSIER: Decimal("15000"),
        TypeTarif.ENTRETIEN: Decimal("25000"),
    }

    for type_tarif, montant in tarifs_defaut.items():
        Tarif.objects.get_or_create(
            type_tarif=type_tarif,
            defaults={"montant_fcfa": montant, "actif": True}
        )
