"""
API Finance — Factures, Paiements multi-canal, Tarifs
Gestion des paiements partiels et historique des transactions
"""

from typing import List, Optional
from decimal import Decimal
from ninja import Router, Schema
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.http import HttpResponse

from apps.users.api import auth
from apps.users.models import RoleUtilisateur
from .models import (
    Facture, LigneFacture, Paiement, Tarif,
    StatutFacture, CanalPaiement, TypeTarif,
    TransactionMobileMoney, StatutTransactionMobile,
)
from . import mobile_money_simulator

router = Router()


# ─── Schemas ─────────────────────────────────────────────────────────────────

class TarifOutSchema(Schema):
    id: int
    type_tarif: str
    type_tarif_libelle: str
    montant_fcfa: float
    description: str
    actif: bool

class TarifUpdateSchema(Schema):
    montant_fcfa: float
    description: str = ""
    actif: bool = True

class LigneFactureOutSchema(Schema):
    id: int
    description: str
    type_tarif: str
    quantite: int
    prix_unitaire: float
    montant_total: float

class LigneFactureCreateSchema(Schema):
    description: str
    type_tarif: str = ""
    quantite: int = 1
    prix_unitaire: float

class PaiementOutSchema(Schema):
    id: int
    canal: str
    canal_libelle: str
    montant: float
    reference_transaction: str
    telephone_paiement: str
    date_paiement: str
    enregistre_par: str
    notes: str

class PaiementCreateSchema(Schema):
    canal: str
    montant: float
    reference_transaction: str = ""
    telephone_paiement: str = ""
    notes: str = ""

class FactureOutSchema(Schema):
    id: int
    numero_facture: str
    statut: str
    statut_libelle: str
    client_nom: str
    client_email: str
    reservation_numero: Optional[str]
    sous_total: float
    tva_pct: float
    montant_tva: float
    montant_total: float
    montant_paye: float
    solde_restant: float
    date_emission: str
    date_echeance: Optional[str]
    est_soldee: bool
    est_en_retard: bool
    lignes: List[LigneFactureOutSchema]
    paiements: List[PaiementOutSchema]

class ErrorSchema(Schema):
    detail: str

class MessageSchema(Schema):
    message: str


def _build_facture_out(f: Facture) -> FactureOutSchema:
    lignes = [
        LigneFactureOutSchema(
            id=l.id, description=l.description, type_tarif=l.type_tarif,
            quantite=l.quantite, prix_unitaire=float(l.prix_unitaire),
            montant_total=float(l.montant_total),
        )
        for l in f.lignes.all()
    ]
    paiements = [
        PaiementOutSchema(
            id=p.id, canal=p.canal,
            canal_libelle=p.get_canal_display(),
            montant=float(p.montant),
            reference_transaction=p.reference_transaction,
            telephone_paiement=p.telephone_paiement,
            date_paiement=p.date_paiement.isoformat(),
            enregistre_par=p.enregistre_par.nom_complet if p.enregistre_par else "",
            notes=p.notes,
        )
        for p in f.paiements.all()
    ]
    return FactureOutSchema(
        id=f.id, numero_facture=f.numero_facture,
        statut=f.statut, statut_libelle=f.get_statut_display(),
        client_nom=f.client.nom_complet, client_email=f.client.email,
        reservation_numero=f.reservation.numero_dossier if f.reservation else None,
        sous_total=float(f.sous_total), tva_pct=float(f.tva_pct),
        montant_tva=float(f.montant_tva), montant_total=float(f.montant_total),
        montant_paye=float(f.montant_paye), solde_restant=float(f.solde_restant),
        date_emission=f.date_emission.isoformat(),
        date_echeance=str(f.date_echeance) if f.date_echeance else None,
        est_soldee=f.est_soldee, est_en_retard=f.est_en_retard,
        lignes=lignes, paiements=paiements,
    )


# ─── Tarifs ──────────────────────────────────────────────────────────────────

@router.get("/tarifs", response=List[TarifOutSchema], auth=auth)
def liste_tarifs(request):
    """Liste la grille tarifaire en vigueur."""
    return [
        TarifOutSchema(
            id=t.id, type_tarif=t.type_tarif,
            type_tarif_libelle=t.get_type_tarif_display(),
            montant_fcfa=float(t.montant_fcfa),
            description=t.description, actif=t.actif,
        )
        for t in Tarif.objects.filter(actif=True).order_by("type_tarif")
    ]


@router.put("/tarifs/{tarif_id}", response={200: TarifOutSchema, 403: ErrorSchema, 404: ErrorSchema}, auth=auth)
def modifier_tarif(request, tarif_id: int, data: TarifUpdateSchema):
    """Modifier un tarif (Admin uniquement)."""
    if not request.auth.est_admin:
        return 403, {"detail": "Seul un administrateur peut modifier les tarifs."}
    t = get_object_or_404(Tarif, id=tarif_id)
    t.montant_fcfa = Decimal(str(data.montant_fcfa))
    t.description = data.description
    t.actif = data.actif
    t.modifie_par = request.auth
    t.save()
    return 200, TarifOutSchema(
        id=t.id, type_tarif=t.type_tarif,
        type_tarif_libelle=t.get_type_tarif_display(),
        montant_fcfa=float(t.montant_fcfa),
        description=t.description, actif=t.actif,
    )


# ─── Factures ────────────────────────────────────────────────────────────────

@router.get("/factures", response=List[FactureOutSchema], auth=auth)
def liste_factures(request, statut: Optional[str] = None):
    """
    Liste les factures.
    - Client : ses factures uniquement.
    - Admin/Secrétariat : toutes.
    """
    if request.auth.role == RoleUtilisateur.CLIENT:
        qs = Facture.objects.filter(client=request.auth)
    else:
        if not request.auth.peut_voir_finances:
            return []
        qs = Facture.objects.all()

    if statut:
        qs = qs.filter(statut=statut)

    qs = qs.select_related("client", "reservation").prefetch_related("lignes", "paiements__enregistre_par")
    return [_build_facture_out(f) for f in qs.order_by("-date_emission")]


@router.get("/factures/{facture_id}", response={200: FactureOutSchema, 403: ErrorSchema, 404: ErrorSchema}, auth=auth)
def detail_facture(request, facture_id: int):
    """Détail d'une facture avec toutes ses lignes et paiements."""
    f = get_object_or_404(
        Facture.objects.select_related("client", "reservation")
        .prefetch_related("lignes", "paiements__enregistre_par"),
        id=facture_id
    )
    if request.auth.role == RoleUtilisateur.CLIENT and f.client != request.auth:
        return 403, {"detail": "Accès refusé."}
    return 200, _build_facture_out(f)


# NOUVEAU : téléchargement du PDF de la facture
@router.get("/factures/{facture_id}/pdf", auth=auth)
def telecharger_facture_pdf(request, facture_id: int):
    """Génère et retourne le PDF de la facture pour téléchargement."""
    f = get_object_or_404(
        Facture.objects.select_related("client").prefetch_related("lignes"),
        id=facture_id
    )
    if request.auth.role == RoleUtilisateur.CLIENT and f.client != request.auth:
        return HttpResponse(status=403)

    from apps.notifications.pdf_generators import generer_pdf_facture
    pdf_bytes = generer_pdf_facture(f)

    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{f.numero_facture}.pdf"'
    return response


@router.post("/factures/{facture_id}/lignes", response={201: FactureOutSchema, 403: ErrorSchema, 404: ErrorSchema}, auth=auth)
def ajouter_ligne_facture(request, facture_id: int, data: LigneFactureCreateSchema):
    """Ajouter une ligne à une facture (Admin/Secrétariat)."""
    if not request.auth.peut_voir_finances:
        return 403, {"detail": "Permission insuffisante."}
    f = get_object_or_404(Facture.objects.prefetch_related("lignes", "paiements__enregistre_par"), id=facture_id)
    if f.statut == StatutFacture.PAYEE:
        return 403, {"detail": "Impossible de modifier une facture déjà payée."}
    LigneFacture.objects.create(
        facture=f,
        description=data.description,
        type_tarif=data.type_tarif,
        quantite=data.quantite,
        prix_unitaire=Decimal(str(data.prix_unitaire)),
    )
    f.calculer_totaux()
    f.refresh_from_db()
    return 201, _build_facture_out(f)


@router.post("/factures/{facture_id}/emettre", response={200: FactureOutSchema, 403: ErrorSchema, 404: ErrorSchema, 400: ErrorSchema}, auth=auth)
def emettre_facture(request, facture_id: int):
    """
    Émettre une facture (passer de BROUILLON à EMISE).
    Envoie la facture PDF par email au client.
    """
    if not request.auth.peut_voir_finances:
        return 403, {"detail": "Permission insuffisante."}
    f = get_object_or_404(Facture.objects.select_related("client").prefetch_related("lignes", "paiements__enregistre_par"), id=facture_id)
    if f.statut != StatutFacture.BROUILLON:
        return 400, {"detail": f"La facture est déjà en statut '{f.get_statut_display()}'."}
    if not f.lignes.exists():
        return 400, {"detail": "Impossible d'émettre une facture sans lignes."}
    f.statut = StatutFacture.EMISE
    f.save()
    # Envoyer le PDF par email
    try:
        from apps.notifications.tasks import envoyer_facture_par_email
        envoyer_facture_par_email.delay(f.id)
    except Exception:
        pass
    return 200, _build_facture_out(f)


# ─── Paiements ───────────────────────────────────────────────────────────────

@router.post("/factures/{facture_id}/paiements", response={201: FactureOutSchema, 400: ErrorSchema, 403: ErrorSchema, 404: ErrorSchema}, auth=auth)
def enregistrer_paiement(request, facture_id: int, data: PaiementCreateSchema):
    """
    Enregistrer un paiement sur une facture (Admin/Secrétariat).
    Supporte les paiements partiels : Mobile Money, Airtel Money, Espèces, Virement.
    """
    if not request.auth.peut_voir_finances:
        return 403, {"detail": "Permission insuffisante pour enregistrer un paiement."}

    f = get_object_or_404(
        Facture.objects.select_related("client")
        .prefetch_related("lignes", "paiements__enregistre_par"),
        id=facture_id
    )

    if f.statut == StatutFacture.PAYEE:
        return 400, {"detail": "Cette facture est déjà entièrement payée."}

    if f.statut == StatutFacture.ANNULEE:
        return 400, {"detail": "Impossible d'enregistrer un paiement sur une facture annulée."}

    montant = Decimal(str(data.montant))

    if montant <= 0:
        return 400, {"detail": "Le montant doit être supérieur à 0."}

    if montant > f.solde_restant:
        return 400, {
            "detail": f"Le montant ({montant:,.0f} FCFA) dépasse le solde restant ({f.solde_restant:,.0f} FCFA)."
        }

    Paiement.objects.create(
        facture=f,
        canal=data.canal,
        montant=montant,
        reference_transaction=data.reference_transaction,
        telephone_paiement=data.telephone_paiement,
        notes=data.notes,
        enregistre_par=request.auth,
    )
    # Le save() du Paiement met à jour automatiquement la facture

    # Recharger les données
    f.refresh_from_db()
    f_out = get_object_or_404(
        Facture.objects.select_related("client")
        .prefetch_related("lignes", "paiements__enregistre_par"),
        id=facture_id
    )

    # Si facture soldée, envoyer confirmation
    if f_out.est_soldee:
        try:
            from apps.notifications.tasks import envoyer_confirmation_paiement
            envoyer_confirmation_paiement.delay(f_out.id)
        except Exception:
            pass

    return 201, _build_facture_out(f_out)


@router.get("/factures/{facture_id}/paiements", response=List[PaiementOutSchema], auth=auth)
def historique_paiements(request, facture_id: int):
    """Historique de tous les paiements d'une facture."""
    f = get_object_or_404(Facture, id=facture_id)
    if request.auth.role == RoleUtilisateur.CLIENT and f.client != request.auth:
        return 403, {"detail": "Accès refusé."}
    return [
        PaiementOutSchema(
            id=p.id, canal=p.canal, canal_libelle=p.get_canal_display(),
            montant=float(p.montant),
            reference_transaction=p.reference_transaction,
            telephone_paiement=p.telephone_paiement,
            date_paiement=p.date_paiement.isoformat(),
            enregistre_par=p.enregistre_par.nom_complet if p.enregistre_par else "",
            notes=p.notes,
        )
        for p in f.paiements.select_related("enregistre_par").order_by("-date_paiement")
    ]


@router.get("/retards", response=List[FactureOutSchema], auth=auth)
def factures_en_retard(request):
    """
    Factures en retard de paiement.
    Utilisé pour les alertes automatiques (Admin/Secrétariat).
    """
    if not request.auth.peut_voir_finances:
        return 403, {"detail": "Permission insuffisante."}

    factures = Facture.objects.filter(
        statut__in=[StatutFacture.EMISE, StatutFacture.PARTIELLEMENT_PAYEE],
        date_echeance__lt=timezone.now().date(),
    ).select_related("client", "reservation").prefetch_related("lignes", "paiements__enregistre_par")

    for f in factures:
        if f.statut != StatutFacture.EN_RETARD:
            f.statut = StatutFacture.EN_RETARD
            f.save(update_fields=["statut"])

    return [_build_facture_out(f) for f in factures]


# ─── Simulation Mobile Money / Airtel Money ──────────────────────────────────

class InitierTransactionSchema(Schema):
    canal: str
    telephone: str
    montant: float

class TransactionMobileOutSchema(Schema):
    id: int
    reference: str
    canal: str
    canal_libelle: str
    telephone: str
    montant: float
    statut: str
    statut_libelle: str
    date_initiation: str
    date_expiration: str
    secondes_restantes: int
    tentatives: int
    motif_echec: str

class ConfirmerTransactionSchema(Schema):
    code: str

class ConfirmationResultSchema(Schema):
    succes: bool
    detail: str
    transaction: TransactionMobileOutSchema
    facture: Optional[FactureOutSchema] = None


def _build_transaction_out(t: TransactionMobileMoney) -> TransactionMobileOutSchema:
    secondes_restantes = max(
        0, int((t.date_expiration - timezone.now()).total_seconds())
    )
    return TransactionMobileOutSchema(
        id=t.id,
        reference=t.reference,
        canal=t.canal,
        canal_libelle=t.get_canal_display(),
        telephone=t.telephone,
        montant=float(t.montant),
        statut=t.statut,
        statut_libelle=t.get_statut_display(),
        date_initiation=t.date_initiation.isoformat(),
        date_expiration=t.date_expiration.isoformat(),
        secondes_restantes=secondes_restantes,
        tentatives=t.tentatives,
        motif_echec=t.motif_echec,
    )


@router.post(
    "/factures/{facture_id}/paiement-mobile/initier",
    response={201: TransactionMobileOutSchema, 400: ErrorSchema, 403: ErrorSchema, 404: ErrorSchema},
    auth=auth,
)
def initier_paiement_mobile(request, facture_id: int, data: InitierTransactionSchema):
    """
    Initie un paiement Mobile Money / Airtel Money (simulation d'API de test).
    """
    facture = get_object_or_404(Facture, id=facture_id)

    if request.auth.role == RoleUtilisateur.CLIENT and facture.client != request.auth:
        return 403, {"detail": "Vous ne pouvez payer que vos propres factures."}

    if data.canal not in (CanalPaiement.MOBILE_MONEY, CanalPaiement.AIRTEL_MONEY):
        return 400, {"detail": "Canal invalide. Utilisez MOBILE_MONEY ou AIRTEL_MONEY."}

    if facture.statut in (StatutFacture.PAYEE, StatutFacture.ANNULEE):
        return 400, {"detail": f"Impossible de payer une facture au statut '{facture.get_statut_display()}'."}

    montant = Decimal(str(data.montant))
    if montant <= 0:
        return 400, {"detail": "Le montant doit être supérieur à 0."}
    if montant > facture.solde_restant:
        return 400, {
            "detail": f"Le montant ({montant:,.0f} FCFA) dépasse le solde restant ({facture.solde_restant:,.0f} FCFA)."
        }

    transaction_existante = TransactionMobileMoney.objects.filter(
        facture=facture, statut=StatutTransactionMobile.EN_ATTENTE_CONFIRMATION
    ).first()
    if transaction_existante and not transaction_existante.est_expiree:
        transaction_existante.statut = StatutTransactionMobile.ANNULEE
        transaction_existante.save(update_fields=["statut"])

    transaction = mobile_money_simulator.initier_transaction(
        facture=facture,
        initiateur=request.auth,
        canal=data.canal,
        telephone=data.telephone,
        montant=montant,
    )

    return 201, _build_transaction_out(transaction)


@router.post(
    "/paiement-mobile/{transaction_id}/confirmer",
    response={200: ConfirmationResultSchema, 403: ErrorSchema, 404: ErrorSchema},
    auth=auth,
)
def confirmer_paiement_mobile(request, transaction_id: int, data: ConfirmerTransactionSchema):
    """Confirme une transaction Mobile Money / Airtel Money avec le code reçu."""
    transaction = get_object_or_404(
        TransactionMobileMoney.objects.select_related("facture", "initiateur"),
        id=transaction_id,
    )

    if request.auth.role == RoleUtilisateur.CLIENT and transaction.initiateur != request.auth:
        return 403, {"detail": "Accès refusé."}

    resultat = mobile_money_simulator.confirmer_transaction(
        transaction, data.code.strip(), enregistre_par=request.auth
    )

    facture_out = None
    if resultat["succes"]:
        facture_fraiche = get_object_or_404(
            Facture.objects.select_related("client")
            .prefetch_related("lignes", "paiements__enregistre_par"),
            id=transaction.facture_id,
        )
        facture_out = _build_facture_out(facture_fraiche)

    return 200, ConfirmationResultSchema(
        succes=resultat["succes"],
        detail=resultat["detail"],
        transaction=_build_transaction_out(resultat["transaction"]),
        facture=facture_out,
    )


@router.post(
    "/paiement-mobile/{transaction_id}/annuler",
    response={200: TransactionMobileOutSchema, 403: ErrorSchema, 404: ErrorSchema},
    auth=auth,
)
def annuler_paiement_mobile(request, transaction_id: int):
    """Annule une transaction Mobile Money en attente."""
    transaction = get_object_or_404(TransactionMobileMoney, id=transaction_id)

    if request.auth.role == RoleUtilisateur.CLIENT and transaction.initiateur != request.auth:
        return 403, {"detail": "Accès refusé."}

    transaction = mobile_money_simulator.annuler_transaction(transaction)
    return 200, _build_transaction_out(transaction)


@router.get(
    "/paiement-mobile/{transaction_id}",
    response={200: TransactionMobileOutSchema, 403: ErrorSchema, 404: ErrorSchema},
    auth=auth,
)
def detail_transaction_mobile(request, transaction_id: int):
    """Détail d'une transaction Mobile Money (pour suivi/polling du statut)."""
    transaction = get_object_or_404(TransactionMobileMoney, id=transaction_id)

    if request.auth.role == RoleUtilisateur.CLIENT and transaction.initiateur != request.auth:
        return 403, {"detail": "Accès refusé."}

    return 200, _build_transaction_out(transaction)


@router.get("/factures/{facture_id}/paiement-mobile/historique", response=List[TransactionMobileOutSchema], auth=auth)
def historique_transactions_mobile(request, facture_id: int):
    """Historique de toutes les transactions Mobile Money tentées sur une facture."""
    facture = get_object_or_404(Facture, id=facture_id)

    if request.auth.role == RoleUtilisateur.CLIENT and facture.client != request.auth:
        return 403, {"detail": "Accès refusé."}

    transactions = facture.transactions_mobile.order_by("-date_initiation")
    return [_build_transaction_out(t) for t in transactions]