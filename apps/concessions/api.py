"""
API Concessions & Exhumations
Contrats de concession : attribution, renouvellement, résiliation
Procédures d'exhumation : demande → instruction → autorisation → réalisation
"""

from typing import List, Optional
from datetime import date
from ninja import Router, Schema
from django.shortcuts import get_object_or_404
from django.utils import timezone

from apps.users.api import auth
from apps.users.models import RoleUtilisateur
from .models import (
    Concession, TypeConcession, StatutConcession,
    Exhumation, StatutExhumation
)

router = Router()


# ─── Schemas Concessions ─────────────────────────────────────────────────────

class ConcessionCreateSchema(Schema):
    reservation_id: int
    type_concession: str
    date_debut: date

class ConcessionOutSchema(Schema):
    id: int
    numero_contrat: str
    reservation_id: int
    titulaire_nom: str
    titulaire_email: str
    type_concession: str
    type_concession_libelle: str
    statut: str
    statut_libelle: str
    date_debut: str
    date_fin: Optional[str]
    est_perpetuelle: bool
    jours_avant_expiration: Optional[int]
    necessite_alerte: bool
    caveau_reference: str

class RenouvellementSchema(Schema):
    nouveau_type: Optional[str] = None

class ResiliationSchema(Schema):
    motif: str

# ─── Schemas Exhumations ─────────────────────────────────────────────────────

class ExhumationCreateSchema(Schema):
    concession_id: int
    motif: str
    destination_restes: str = ""

class ExhumationOutSchema(Schema):
    id: int
    numero_demande: str
    concession_id: int
    concession_numero: str
    demandeur_nom: str
    statut: str
    statut_libelle: str
    motif: str
    destination_restes: str
    date_demande: str
    date_autorisation: Optional[str]
    date_realisation: Optional[str]
    autorisee_par: Optional[str]
    motif_refus: str

class AutoriserRefuserSchema(Schema):
    motif_refus: str = ""

class ErrorSchema(Schema):
    detail: str

class MessageSchema(Schema):
    message: str


def _build_concession_out(c: Concession) -> ConcessionOutSchema:
    return ConcessionOutSchema(
        id=c.id,
        numero_contrat=c.numero_contrat,
        reservation_id=c.reservation_id,
        titulaire_nom=c.titulaire.nom_complet,
        titulaire_email=c.titulaire.email,
        type_concession=c.type_concession,
        type_concession_libelle=c.get_type_concession_display(),
        statut=c.statut,
        statut_libelle=c.get_statut_display(),
        date_debut=str(c.date_debut),
        date_fin=str(c.date_fin) if c.date_fin else None,
        est_perpetuelle=c.est_perpetuelle,
        jours_avant_expiration=c.jours_avant_expiration,
        necessite_alerte=c.necessite_alerte,
        caveau_reference=c.reservation.caveau.reference_complete,
    )


def _build_exhumation_out(e: Exhumation) -> ExhumationOutSchema:
    return ExhumationOutSchema(
        id=e.id,
        numero_demande=e.numero_demande,
        concession_id=e.concession_id,
        concession_numero=e.concession.numero_contrat,
        demandeur_nom=e.demandeur.nom_complet,
        statut=e.statut,
        statut_libelle=e.get_statut_display(),
        motif=e.motif,
        destination_restes=e.destination_restes,
        date_demande=e.date_demande.isoformat(),
        date_autorisation=e.date_autorisation.isoformat() if e.date_autorisation else None,
        date_realisation=str(e.date_realisation) if e.date_realisation else None,
        autorisee_par=e.autorisee_par.nom_complet if e.autorisee_par else None,
        motif_refus=e.motif_refus,
    )


# ─── Concessions : routes spécifiques (SANS paramètre) — en premier ──────────

@router.post("/", response={201: ConcessionOutSchema, 400: ErrorSchema, 403: ErrorSchema, 404: ErrorSchema}, auth=auth)
def creer_concession(request, data: ConcessionCreateSchema):
    """
    Attribuer une concession suite à une réservation validée (Admin/Secrétariat).
    """
    if not request.auth.peut_valider_reservations:
        return 403, {"detail": "Permission insuffisante pour créer une concession."}

    from apps.reservations.models import Reservation, StatutReservation
    reservation = get_object_or_404(Reservation, id=data.reservation_id)

    if reservation.statut != StatutReservation.VALIDEE:
        return 400, {"detail": "La réservation doit être validée pour créer une concession."}

    if hasattr(reservation, "concession"):
        return 400, {"detail": "Une concession existe déjà pour cette réservation."}

    c = Concession.objects.create(
        reservation=reservation,
        titulaire=reservation.client,
        type_concession=data.type_concession,
        date_debut=data.date_debut,
    )

    # Générer le contrat PDF (async)
    try:
        from apps.notifications.tasks import generer_contrat_concession
        generer_contrat_concession.delay(c.id)
    except Exception:
        pass

    return 201, _build_concession_out(c)


@router.get("/", response=List[ConcessionOutSchema], auth=auth)
def liste_concessions(request, statut: Optional[str] = None, alerte_seulement: bool = False):
    """
    Liste les concessions.
    - Client : ses concessions uniquement.
    - Admin/Secrétariat : toutes avec filtres optionnels.
    """
    if request.auth.role == RoleUtilisateur.CLIENT:
        qs = Concession.objects.filter(titulaire=request.auth)
    else:
        qs = Concession.objects.all()

    if statut:
        qs = qs.filter(statut=statut)

    qs = qs.select_related("titulaire", "reservation__caveau__bloc__zone__cimetiere")

    result = [_build_concession_out(c) for c in qs.order_by("-date_debut")]

    if alerte_seulement:
        result = [c for c in result if c.necessite_alerte]

    return result


@router.get("/alertes", response=List[ConcessionOutSchema], auth=auth)
def concessions_en_alerte(request):
    """
    Concessions qui expirent dans moins de 90 jours.
    Utilisé pour le tableau de bord admin.
    """
    if not request.auth.peut_voir_finances:
        return 403, {"detail": "Permission insuffisante."}

    toutes = Concession.objects.filter(
        statut=StatutConcession.ACTIVE,
        date_fin__isnull=False
    ).select_related("titulaire", "reservation__caveau__bloc__zone__cimetiere")

    return [_build_concession_out(c) for c in toutes if c.necessite_alerte]


# ─── Exhumations : routes spécifiques SANS paramètre — AVANT /{concession_id} ─
# IMPORTANT : ces routes doivent être déclarées avant /{concession_id}...
# sinon Django Ninja tente de parser "exhumations" comme un entier.

@router.post("/exhumations", response={201: ExhumationOutSchema, 400: ErrorSchema, 404: ErrorSchema}, auth=auth)
def soumettre_exhumation(request, data: ExhumationCreateSchema):
    """Soumettre une demande d'exhumation."""
    concession = get_object_or_404(Concession, id=data.concession_id)

    # Seul le titulaire ou un admin peut soumettre
    if request.auth.role == RoleUtilisateur.CLIENT and concession.titulaire != request.auth:
        return 400, {"detail": "Vous n'êtes pas titulaire de cette concession."}

    e = Exhumation.objects.create(
        concession=concession,
        demandeur=request.auth,
        motif=data.motif,
        destination_restes=data.destination_restes,
    )

    # Notifier les admins
    try:
        from apps.notifications.tasks import notifier_demande_exhumation
        notifier_demande_exhumation.delay(e.id)
    except Exception:
        pass

    return 201, _build_exhumation_out(e)


@router.get("/exhumations", response=List[ExhumationOutSchema], auth=auth)
def liste_exhumations(request, statut: Optional[str] = None):
    """Liste les demandes d'exhumation."""
    if request.auth.role == RoleUtilisateur.CLIENT:
        qs = Exhumation.objects.filter(demandeur=request.auth)
    else:
        qs = Exhumation.objects.all()

    if statut:
        qs = qs.filter(statut=statut)

    qs = qs.select_related("concession", "demandeur", "autorisee_par")
    return [_build_exhumation_out(e) for e in qs.order_by("-date_demande")]


@router.post("/exhumations/{exhumation_id}/autoriser", response={200: ExhumationOutSchema, 403: ErrorSchema, 404: ErrorSchema, 400: ErrorSchema}, auth=auth)
def autoriser_exhumation(request, exhumation_id: int):
    """
    Autoriser une exhumation (Admin uniquement).
    Génère l'autorisation PDF et le PV associé.
    """
    if not request.auth.est_admin:
        return 403, {"detail": "Seul un administrateur peut autoriser une exhumation."}

    e = get_object_or_404(Exhumation, id=exhumation_id)

    if e.statut not in [StatutExhumation.DEMANDE, StatutExhumation.EN_INSTRUCTION]:
        return 400, {"detail": f"Impossible d'autoriser avec le statut '{e.get_statut_display()}'."}

    e.statut = StatutExhumation.AUTORISEE
    e.autorisee_par = request.auth
    e.date_autorisation = timezone.now()
    e._change_reason = f"Autorisée par {request.auth.nom_complet}"
    e.save()

    # Générer le PDF d'autorisation (async)
    try:
        from apps.notifications.tasks import generer_autorisation_exhumation
        generer_autorisation_exhumation.delay(e.id)
    except Exception:
        pass

    return 200, _build_exhumation_out(e)


@router.post("/exhumations/{exhumation_id}/refuser", response={200: ExhumationOutSchema, 403: ErrorSchema, 404: ErrorSchema}, auth=auth)
def refuser_exhumation(request, exhumation_id: int, data: AutoriserRefuserSchema):
    """Refuser une demande d'exhumation (Admin uniquement)."""
    if not request.auth.est_admin:
        return 403, {"detail": "Seul un administrateur peut refuser une exhumation."}

    e = get_object_or_404(Exhumation, id=exhumation_id)
    e.statut = StatutExhumation.REFUSEE
    e.motif_refus = data.motif_refus
    e._change_reason = f"Refusée par {request.auth.nom_complet}"
    e.save()

    return 200, _build_exhumation_out(e)


@router.post("/exhumations/{exhumation_id}/realiser", response={200: ExhumationOutSchema, 403: ErrorSchema, 404: ErrorSchema, 400: ErrorSchema}, auth=auth)
def marquer_exhumation_realisee(request, exhumation_id: int, date_realisation: date = None):
    """
    Marquer une exhumation comme réalisée (Admin/Agent terrain).
    Le caveau redevient disponible.
    """
    if not request.auth.peut_modifier_carte:
        return 403, {"detail": "Permission insuffisante."}

    e = get_object_or_404(Exhumation.objects.select_related("concession__reservation__caveau"), id=exhumation_id)

    if e.statut != StatutExhumation.AUTORISEE:
        return 400, {"detail": "L'exhumation doit être autorisée avant d'être marquée comme réalisée."}

    e.statut = StatutExhumation.REALISEE
    e.date_realisation = date_realisation or timezone.now().date()
    e._change_reason = f"Réalisée par {request.auth.nom_complet}"
    e.save()

    # Libérer le caveau
    from apps.cartographie.models import StatutCaveau
    caveau = e.concession.reservation.caveau
    caveau.changer_statut(
        StatutCaveau.DISPONIBLE,
        utilisateur=request.auth,
        raison=f"Exhumation {e.numero_demande} réalisée — caveau libéré"
    )

    # Mettre la concession à jour
    e.concession.statut = StatutConcession.RESILIEE
    e.concession.save()

    return 200, _build_exhumation_out(e)


# ─── Concessions : routes avec paramètre {concession_id} — APRÈS exhumations ─

@router.get("/{concession_id}", response={200: ConcessionOutSchema, 403: ErrorSchema, 404: ErrorSchema}, auth=auth)
def detail_concession(request, concession_id: int):
    """Détail d'une concession."""
    c = get_object_or_404(
        Concession.objects.select_related("titulaire", "reservation__caveau__bloc__zone__cimetiere"),
        id=concession_id
    )
    if request.auth.role == RoleUtilisateur.CLIENT and c.titulaire != request.auth:
        return 403, {"detail": "Accès refusé."}
    return 200, _build_concession_out(c)


@router.post("/{concession_id}/renouveler", response={201: ConcessionOutSchema, 403: ErrorSchema, 404: ErrorSchema, 400: ErrorSchema}, auth=auth)
def renouveler_concession(request, concession_id: int, data: RenouvellementSchema):
    """
    Renouveler une concession (Admin/Secrétariat).
    Crée un nouveau contrat lié à l'ancien.
    """
    if not request.auth.peut_valider_reservations:
        return 403, {"detail": "Permission insuffisante."}

    c = get_object_or_404(Concession, id=concession_id)

    if c.est_perpetuelle:
        return 400, {"detail": "Une concession perpétuelle n'a pas besoin d'être renouvelée."}

    nouveau_type = data.nouveau_type or c.type_concession
    nouvelle_concession = c.renouveler(nouveau_type=nouveau_type)

    return 201, _build_concession_out(nouvelle_concession)


@router.post("/{concession_id}/resilier", response={200: ConcessionOutSchema, 403: ErrorSchema, 404: ErrorSchema, 400: ErrorSchema}, auth=auth)
def resilier_concession(request, concession_id: int, data: ResiliationSchema):
    """Résilier une concession active (Admin uniquement)."""
    if not request.auth.est_admin:
        return 403, {"detail": "Seul un administrateur peut résilier une concession."}

    c = get_object_or_404(Concession, id=concession_id)

    if c.statut != StatutConcession.ACTIVE:
        return 400, {"detail": f"Impossible de résilier une concession avec le statut '{c.get_statut_display()}'."}

    c.statut = StatutConcession.RESILIEE
    c._change_reason = f"Résiliation par {request.auth.nom_complet}. Motif : {data.motif}"
    c.save()

    # Libérer le caveau
    from apps.cartographie.models import StatutCaveau
    c.reservation.caveau.changer_statut(
        StatutCaveau.DISPONIBLE,
        utilisateur=request.auth,
        raison=f"Concession {c.numero_contrat} résiliée"
    )

    return 200, _build_concession_out(c)