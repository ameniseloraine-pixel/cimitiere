"""
API Réservations — Workflow complet de réservation
Client soumet → Admin valide/rejette → Facture auto générée → Email envoyé
"""

from typing import List, Optional
from datetime import date
from ninja import Router, Schema
from django.shortcuts import get_object_or_404
from django.utils import timezone

from apps.users.api import auth
from apps.users.models import RoleUtilisateur
from apps.cartographie.models import Caveau, StatutCaveau, JournalModificationCaveau
from .models import Reservation, Defunt, StatutReservation

router = Router()


# ─── Schemas ─────────────────────────────────────────────────────────────────

class DefuntSchema(Schema):
    nom: str
    prenom: str
    date_naissance: Optional[date] = None
    date_deces: date
    lieu_deces: str = ""
    nationalite: str = ""
    acte_deces_numero: str = ""

class ReservationCreateSchema(Schema):
    caveau_id: int
    defunt: DefuntSchema
    date_inhumation_souhaitee: Optional[date] = None
    notes_admin: str = ""

class ReservationOutSchema(Schema):
    id: int
    numero_dossier: str
    statut: str
    statut_libelle: str
    caveau_reference: str
    caveau_id: int
    client_nom: str
    client_email: str
    defunt_nom_complet: str
    defunt_date_deces: str
    date_soumission: str
    date_inhumation_souhaitee: Optional[str]
    date_validation: Optional[str]
    validee_par: Optional[str]
    motif_rejet: str

class ValiderRejetSchema(Schema):
    motif: str = ""

class ErrorSchema(Schema):
    detail: str

class MessageSchema(Schema):
    message: str


def _build_reservation_out(r: Reservation) -> ReservationOutSchema:
    return ReservationOutSchema(
        id=r.id,
        numero_dossier=r.numero_dossier,
        statut=r.statut,
        statut_libelle=r.get_statut_display(),
        caveau_reference=r.caveau.reference_complete,
        caveau_id=r.caveau_id,
        client_nom=r.client.nom_complet,
        client_email=r.client.email,
        defunt_nom_complet=f"{r.defunt.prenom} {r.defunt.nom}",
        defunt_date_deces=str(r.defunt.date_deces),
        date_soumission=r.date_soumission.isoformat(),
        date_inhumation_souhaitee=str(r.date_inhumation_souhaitee) if r.date_inhumation_souhaitee else None,
        date_validation=r.date_validation.isoformat() if r.date_validation else None,
        validee_par=r.validee_par.nom_complet if r.validee_par else None,
        motif_rejet=r.motif_rejet,
    )


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.post("/", response={201: ReservationOutSchema, 400: ErrorSchema, 404: ErrorSchema}, auth=auth)
def soumettre_reservation(request, data: ReservationCreateSchema):
    """
    Soumettre une demande de réservation de caveau.
    Accessible à tous les utilisateurs connectés.
    Le caveau passe en Orange (Réservé — En attente).
    """
    # Récupérer et vérifier le caveau
    caveau = get_object_or_404(Caveau, id=data.caveau_id)

    if caveau.statut != StatutCaveau.DISPONIBLE:
        return 400, {"detail": f"Ce caveau n'est pas disponible (statut : {caveau.get_statut_display()})."}

    # Créer le défunt
    defunt = Defunt.objects.create(**data.defunt.dict())

    # Créer la réservation
    reservation = Reservation.objects.create(
        client=request.auth,
        caveau=caveau,
        defunt=defunt,
        date_inhumation_souhaitee=data.date_inhumation_souhaitee,
        notes_admin=data.notes_admin,
        statut=StatutReservation.EN_ATTENTE,
    )

    # Passer le caveau en Orange
    ancien_statut = caveau.statut
    caveau.changer_statut(
        StatutCaveau.RESERVE,
        utilisateur=request.auth,
        raison=f"Réservation {reservation.numero_dossier} soumise"
    )
    JournalModificationCaveau.objects.create(
        caveau=caveau,
        utilisateur=request.auth,
        ancien_statut=ancien_statut,
        nouveau_statut=StatutCaveau.RESERVE,
        raison=f"Réservation {reservation.numero_dossier} soumise",
        ip_address=request.META.get("REMOTE_ADDR"),
    )

    # Notifier l'admin (tâche async)
    _notifier_nouvelle_reservation(reservation)

    return 201, _build_reservation_out(reservation)


@router.get("/", response=List[ReservationOutSchema], auth=auth)
def liste_reservations(request, statut: Optional[str] = None):
    """
    Liste les réservations.
    - Client : voit uniquement les siennes.
    - Admin/Secrétariat/Agent : voit toutes.
    """
    if request.auth.role == RoleUtilisateur.CLIENT:
        qs = Reservation.objects.filter(client=request.auth)
    else:
        qs = Reservation.objects.all()

    if statut:
        qs = qs.filter(statut=statut)

    qs = qs.select_related("client", "defunt", "caveau__bloc__zone__cimetiere", "validee_par")
    return [_build_reservation_out(r) for r in qs.order_by("-date_soumission")]


@router.get("/{reservation_id}", response={200: ReservationOutSchema, 403: ErrorSchema, 404: ErrorSchema}, auth=auth)
def detail_reservation(request, reservation_id: int):
    """Détail d'une réservation. Client ne voit que les siennes."""
    r = get_object_or_404(
        Reservation.objects.select_related("client", "defunt", "caveau__bloc__zone__cimetiere", "validee_par"),
        id=reservation_id
    )
    if request.auth.role == RoleUtilisateur.CLIENT and r.client != request.auth:
        return 403, {"detail": "Accès refusé."}
    return 200, _build_reservation_out(r)


@router.post("/{reservation_id}/valider", response={200: ReservationOutSchema, 403: ErrorSchema, 404: ErrorSchema, 400: ErrorSchema}, auth=auth)
def valider_reservation(request, reservation_id: int):
    """
    Valider une réservation (Admin/Secrétariat uniquement).
    Le caveau passe en Rouge. Une facture PDF est générée et envoyée par email.
    """
    if not request.auth.peut_valider_reservations:
        return 403, {"detail": "Seuls les administrateurs et le secrétariat peuvent valider les réservations."}

    r = get_object_or_404(
        Reservation.objects.select_related("client", "defunt", "caveau__bloc__zone__cimetiere"),
        id=reservation_id
    )

    if r.statut != StatutReservation.EN_ATTENTE:
        return 400, {"detail": f"Impossible de valider une réservation avec le statut '{r.get_statut_display()}'."}

    # Journaliser avant validation
    ancien_statut = r.caveau.statut

    # Valider la réservation (passe caveau en OCCUPE)
    r.valider(request.auth)

    JournalModificationCaveau.objects.create(
        caveau=r.caveau,
        utilisateur=request.auth,
        ancien_statut=ancien_statut,
        nouveau_statut=StatutCaveau.OCCUPE,
        raison=f"Réservation {r.numero_dossier} validée par {request.auth.nom_complet}",
        ip_address=request.META.get("REMOTE_ADDR"),
    )

    # Générer facture + envoyer email (async)
    _generer_facture_et_notifier(r)

    return 200, _build_reservation_out(r)


@router.post("/{reservation_id}/rejeter", response={200: ReservationOutSchema, 403: ErrorSchema, 404: ErrorSchema, 400: ErrorSchema}, auth=auth)
def rejeter_reservation(request, reservation_id: int, data: ValiderRejetSchema):
    """
    Rejeter une réservation (Admin/Secrétariat).
    Le caveau repasse en Vert (Disponible). Le client est notifié par email.
    """
    if not request.auth.peut_valider_reservations:
        return 403, {"detail": "Permission insuffisante."}

    r = get_object_or_404(
        Reservation.objects.select_related("client", "caveau__bloc__zone"),
        id=reservation_id
    )

    if r.statut != StatutReservation.EN_ATTENTE:
        return 400, {"detail": f"Impossible de rejeter une réservation avec le statut '{r.get_statut_display()}'."}

    ancien_statut = r.caveau.statut
    r.rejeter(request.auth, motif=data.motif)

    JournalModificationCaveau.objects.create(
        caveau=r.caveau,
        utilisateur=request.auth,
        ancien_statut=ancien_statut,
        nouveau_statut=StatutCaveau.DISPONIBLE,
        raison=f"Réservation {r.numero_dossier} rejetée. Motif : {data.motif}",
        ip_address=request.META.get("REMOTE_ADDR"),
    )

    # Notifier le client
    _notifier_rejet(r, data.motif)

    return 200, _build_reservation_out(r)


@router.delete("/{reservation_id}", response={200: MessageSchema, 403: ErrorSchema, 404: ErrorSchema, 400: ErrorSchema}, auth=auth)
def annuler_reservation(request, reservation_id: int):
    """
    Annuler une réservation (Client = ses propres réservations EN_ATTENTE seulement).
    """
    r = get_object_or_404(Reservation, id=reservation_id)

    if request.auth.role == RoleUtilisateur.CLIENT and r.client != request.auth:
        return 403, {"detail": "Vous ne pouvez annuler que vos propres réservations."}

    if r.statut != StatutReservation.EN_ATTENTE:
        return 400, {"detail": "Seules les réservations en attente peuvent être annulées."}

    ancien_statut = r.caveau.statut
    r.statut = StatutReservation.ANNULEE
    r.save()

    r.caveau.changer_statut(StatutCaveau.DISPONIBLE, utilisateur=request.auth, raison="Réservation annulée par le client")
    JournalModificationCaveau.objects.create(
        caveau=r.caveau,
        utilisateur=request.auth,
        ancien_statut=ancien_statut,
        nouveau_statut=StatutCaveau.DISPONIBLE,
        raison=f"Réservation {r.numero_dossier} annulée",
        ip_address=request.META.get("REMOTE_ADDR"),
    )

    return 200, {"message": f"Réservation {r.numero_dossier} annulée. Le caveau est de nouveau disponible."}


# ─── Helpers (appels Celery ou synchrones en dev) ────────────────────────────

def _notifier_nouvelle_reservation(reservation: Reservation):
    """Notifie les admins d'une nouvelle réservation."""
    try:
        from apps.notifications.tasks import envoyer_notification_nouvelle_reservation
        envoyer_notification_nouvelle_reservation.delay(reservation.id)
    except Exception:
        pass  # Celery optionnel en dev


def _generer_facture_et_notifier(reservation: Reservation):
    """Génère la facture PDF et envoie les emails de confirmation."""
    try:
        from apps.finance.services import creer_facture_pour_reservation
        from apps.notifications.tasks import envoyer_confirmation_reservation
        facture = creer_facture_pour_reservation(reservation)
        envoyer_confirmation_reservation.delay(reservation.id, facture.id)
    except Exception:
        pass


def _notifier_rejet(reservation: Reservation, motif: str):
    """Notifie le client du rejet de sa réservation."""
    try:
        from apps.notifications.tasks import envoyer_notification_rejet
        envoyer_notification_rejet.delay(reservation.id, motif)
    except Exception:
        pass
