"""
Tâches Celery — Notifications & Génération de documents PDF
Toutes les tâches sont asynchrones et journalisées dans le modèle Notification.
"""

import base64
import requests
from celery import shared_task
from django.conf import settings
from django.utils import timezone

from .models import Notification, TypeNotification, StatutNotification


# ─── Helper générique d'envoi (via API Brevo — HTTPS) ─────────────────────────

def _envoyer_email(destinataire, type_notif, sujet, corps_html, corps_texte="",
                    pieces_jointes=None, reference_type="", reference_id=None):
    """
    Crée un log Notification puis envoie l'email via l'API Brevo.
    pieces_jointes : liste de tuples (nom_fichier, contenu_bytes, mime_type)
    """
    notif = Notification.objects.create(
        destinataire=destinataire,
        type_notification=type_notif,
        sujet=sujet,
        corps_html=corps_html,
        corps_texte=corps_texte or corps_html,
        reference_type=reference_type,
        reference_id=reference_id,
    )

    try:
        payload = {
            "sender": {"name": "Gestion Cimetière", "email": settings.DEFAULT_FROM_EMAIL},
            "to": [{"email": destinataire.email}],
            "subject": sujet,
            "htmlContent": f"<pre>{corps_texte or corps_html}</pre>",
        }

        if pieces_jointes:
            payload["attachment"] = [
                {
                    "name": nom,
                    "content": base64.b64encode(contenu).decode("utf-8"),
                }
                for (nom, contenu, mime) in pieces_jointes
            ]

        response = requests.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={
                "api-key": settings.BREVO_API_KEY,
                "Content-Type": "application/json",
                "accept": "application/json",
            },
            json=payload,
            timeout=15,
        )

        if response.status_code >= 400:
            raise Exception(f"Échec envoi email Brevo: {response.status_code} - {response.text}")

        notif.statut = StatutNotification.ENVOYEE
        notif.date_envoi = timezone.now()
        notif.save(update_fields=["statut", "date_envoi"])

    except Exception as e:
        notif.statut = StatutNotification.ECHEC
        notif.erreur = str(e)
        notif.tentatives += 1
        notif.save(update_fields=["statut", "erreur", "tentatives"])
        raise

    return notif


# ─── Réservations ─────────────────────────────────────────────────────────────

@shared_task
def envoyer_notification_nouvelle_reservation(reservation_id):
    """Notifie les admins/secrétariat d'une nouvelle réservation à valider."""
    from apps.reservations.models import Reservation
    from apps.users.models import Utilisateur, RoleUtilisateur

    reservation = Reservation.objects.select_related(
        "client", "defunt", "caveau__bloc__zone__cimetiere"
    ).get(id=reservation_id)

    sujet = f"[Cimetière] Nouvelle réservation {reservation.numero_dossier} à valider"
    corps = f"""
Une nouvelle demande de réservation a été soumise.

Dossier : {reservation.numero_dossier}
Client : {reservation.client.nom_complet} ({reservation.client.email})
Caveau : {reservation.caveau.reference_complete}
Défunt : {reservation.defunt.prenom} {reservation.defunt.nom}
Date de décès : {reservation.defunt.date_deces}

Veuillez vous connecter au tableau de bord pour valider ou rejeter cette demande.
    """.strip()

    destinataires = Utilisateur.objects.filter(
        role__in=[RoleUtilisateur.ADMINISTRATEUR, RoleUtilisateur.SECRETARIAT],
        is_active=True
    )

    for admin in destinataires:
        _envoyer_email(
            admin, TypeNotification.NOUVELLE_RESERVATION,
            sujet, corps,
            reference_type="reservation", reference_id=reservation.id,
        )


@shared_task
def envoyer_confirmation_reservation(reservation_id, facture_id):
    """
    Envoie la confirmation de validation + facture PDF au client.
    """
    from apps.reservations.models import Reservation
    from apps.finance.models import Facture
    from .pdf_generators import generer_pdf_facture

    reservation = Reservation.objects.select_related(
        "client", "defunt", "caveau__bloc__zone__cimetiere"
    ).get(id=reservation_id)
    facture = Facture.objects.select_related("client").prefetch_related("lignes").get(id=facture_id)

    pdf_bytes = generer_pdf_facture(facture)

    sujet = f"[Cimetière] Réservation {reservation.numero_dossier} validée — Facture {facture.numero_facture}"
    corps = f"""
Bonjour {reservation.client.prenom},

Votre demande de réservation a été validée.

Dossier : {reservation.numero_dossier}
Caveau : {reservation.caveau.reference_complete}
Défunt : {reservation.defunt.prenom} {reservation.defunt.nom}

La facture {facture.numero_facture} d'un montant de {facture.montant_total:,.0f} FCFA
est jointe à cet email. Merci de procéder au règlement (Mobile Money, Airtel Money,
espèces ou virement) auprès de notre secrétariat.

Cordialement,
L'équipe de gestion du cimetière
    """.strip()

    _envoyer_email(
        reservation.client, TypeNotification.RESERVATION_VALIDEE,
        sujet, corps,
        pieces_jointes=[(f"{facture.numero_facture}.pdf", pdf_bytes, "application/pdf")],
        reference_type="reservation", reference_id=reservation.id,
    )


@shared_task
def envoyer_notification_rejet(reservation_id, motif):
    """Notifie le client du rejet de sa réservation."""
    from apps.reservations.models import Reservation

    reservation = Reservation.objects.select_related("client", "defunt", "caveau").get(id=reservation_id)

    sujet = f"[Cimetière] Réservation {reservation.numero_dossier} — Décision"
    corps = f"""
Bonjour {reservation.client.prenom},

Nous vous informons que votre demande de réservation {reservation.numero_dossier}
n'a pas pu être validée.

Motif : {motif or "Non spécifié"}

Le caveau concerné a été remis à disposition. Vous pouvez soumettre une nouvelle
demande pour un autre emplacement disponible.

Pour toute question, contactez notre secrétariat.

Cordialement,
L'équipe de gestion du cimetière
    """.strip()

    _envoyer_email(
        reservation.client, TypeNotification.RESERVATION_REJETEE,
        sujet, corps,
        reference_type="reservation", reference_id=reservation.id,
    )


# ─── Factures & Paiements ─────────────────────────────────────────────────────

@shared_task
def envoyer_facture_par_email(facture_id):
    """Envoie une facture PDF au client par email."""
    from apps.finance.models import Facture
    from .pdf_generators import generer_pdf_facture

    facture = Facture.objects.select_related("client").prefetch_related("lignes").get(id=facture_id)
    pdf_bytes = generer_pdf_facture(facture)

    sujet = f"[Cimetière] Facture {facture.numero_facture}"
    corps = f"""
Bonjour {facture.client.prenom},

Veuillez trouver ci-joint votre facture {facture.numero_facture}
d'un montant de {facture.montant_total:,.0f} FCFA.

Échéance : {facture.date_echeance.strftime('%d/%m/%Y') if facture.date_echeance else 'Non spécifiée'}

Moyens de paiement acceptés : Mobile Money, Airtel Money, espèces, virement bancaire.

Cordialement,
L'équipe de gestion du cimetière
    """.strip()

    _envoyer_email(
        facture.client, TypeNotification.FACTURE_EMISE,
        sujet, corps,
        pieces_jointes=[(f"{facture.numero_facture}.pdf", pdf_bytes, "application/pdf")],
        reference_type="facture", reference_id=facture.id,
    )


@shared_task
def envoyer_confirmation_paiement(facture_id):
    """Envoie une confirmation de paiement intégral."""
    from apps.finance.models import Facture

    facture = Facture.objects.select_related("client").get(id=facture_id)

    sujet = f"[Cimetière] Facture {facture.numero_facture} — Paiement reçu"
    corps = f"""
Bonjour {facture.client.prenom},

Nous confirmons la réception du paiement intégral pour la facture {facture.numero_facture}
d'un montant total de {facture.montant_total:,.0f} FCFA.

Merci pour votre confiance.

Cordialement,
L'équipe de gestion du cimetière
    """.strip()

    _envoyer_email(
        facture.client, TypeNotification.FACTURE_EMISE,
        sujet, corps,
        reference_type="facture", reference_id=facture.id,
    )


@shared_task
def verifier_retards_paiement():
    """
    Tâche planifiée (quotidienne) : détecte les factures en retard
    et notifie clients + admins.
    """
    from apps.finance.models import Facture, StatutFacture
    from apps.users.models import Utilisateur, RoleUtilisateur

    factures_retard = Facture.objects.filter(
        statut__in=[StatutFacture.EMISE, StatutFacture.PARTIELLEMENT_PAYEE],
        date_echeance__lt=timezone.now().date(),
    ).select_related("client")

    admins = Utilisateur.objects.filter(
        role__in=[RoleUtilisateur.ADMINISTRATEUR, RoleUtilisateur.SECRETARIAT],
        is_active=True
    )

    for facture in factures_retard:
        if facture.statut != StatutFacture.EN_RETARD:
            facture.statut = StatutFacture.EN_RETARD
            facture.save(update_fields=["statut"])

        sujet = f"[Cimetière] Rappel — Facture {facture.numero_facture} en retard"
        corps = f"""
Bonjour {facture.client.prenom},

Votre facture {facture.numero_facture} d'un montant restant de
{facture.solde_restant:,.0f} FCFA est en retard de paiement
(échéance dépassée le {facture.date_echeance.strftime('%d/%m/%Y')}).

Merci de régulariser votre situation au plus vite auprès de notre secrétariat.

Cordialement,
L'équipe de gestion du cimetière
        """.strip()
        _envoyer_email(
            facture.client, TypeNotification.RETARD_PAIEMENT,
            sujet, corps,
            reference_type="facture", reference_id=facture.id,
        )

        for admin in admins:
            sujet_admin = f"[Cimetière] Retard de paiement — {facture.numero_facture}"
            corps_admin = f"""
Le client {facture.client.nom_complet} ({facture.client.email}) a un retard
de paiement sur la facture {facture.numero_facture}.

Solde restant : {facture.solde_restant:,.0f} FCFA
Échéance dépassée le : {facture.date_echeance.strftime('%d/%m/%Y')}
            """.strip()
            _envoyer_email(
                admin, TypeNotification.RETARD_PAIEMENT,
                sujet_admin, corps_admin,
                reference_type="facture", reference_id=facture.id,
            )


# ─── Concessions ───────────────────────────────────────────────────────────────

@shared_task
def generer_contrat_concession(concession_id):
    """Génère le PDF du contrat de concession et le sauvegarde."""
    from apps.concessions.models import Concession
    from .pdf_generators import generer_pdf_contrat_concession
    from django.core.files.base import ContentFile

    concession = Concession.objects.select_related(
        "titulaire", "reservation__caveau__bloc__zone__cimetiere"
    ).get(id=concession_id)

    pdf_bytes = generer_pdf_contrat_concession(concession)
    concession.contrat_pdf.save(
        f"{concession.numero_contrat}.pdf",
        ContentFile(pdf_bytes),
        save=True
    )

    sujet = f"[Cimetière] Contrat de concession {concession.numero_contrat}"
    corps = f"""
Bonjour {concession.titulaire.prenom},

Votre contrat de concession funéraire {concession.numero_contrat} est
disponible en pièce jointe.

Caveau : {concession.reservation.caveau.reference_complete}
Type : {concession.get_type_concession_display()}
Date de début : {concession.date_debut.strftime('%d/%m/%Y')}
Date de fin : {concession.date_fin.strftime('%d/%m/%Y') if concession.date_fin else 'Perpétuelle'}

Cordialement,
L'équipe de gestion du cimetière
    """.strip()

    _envoyer_email(
        concession.titulaire, TypeNotification.CONFIRMATION_RESERVATION,
        sujet, corps,
        pieces_jointes=[(f"{concession.numero_contrat}.pdf", pdf_bytes, "application/pdf")],
        reference_type="concession", reference_id=concession.id,
    )


@shared_task
def verifier_concessions_expirantes():
    """
    Tâche planifiée (quotidienne) : alerte les titulaires et l'admin
    pour les concessions expirant dans moins de 90 jours.
    """
    from apps.concessions.models import Concession, StatutConcession
    from apps.users.models import Utilisateur, RoleUtilisateur

    concessions = Concession.objects.filter(
        statut=StatutConcession.ACTIVE,
        date_fin__isnull=False
    ).select_related("titulaire", "reservation__caveau__bloc__zone")

    admins = Utilisateur.objects.filter(
        role=RoleUtilisateur.ADMINISTRATEUR, is_active=True
    )

    for concession in concessions:
        if not concession.necessite_alerte:
            continue

        jours = concession.jours_avant_expiration

        if concession.statut != StatutConcession.EN_ALERTE:
            concession.statut = StatutConcession.EN_ALERTE
            concession.save(update_fields=["statut"])

        sujet = f"[Cimetière] Votre concession {concession.numero_contrat} expire dans {jours} jours"
        corps = f"""
Bonjour {concession.titulaire.prenom},

Votre concession funéraire {concession.numero_contrat}
(Caveau : {concession.reservation.caveau.reference_complete})
arrive à échéance le {concession.date_fin.strftime('%d/%m/%Y')} (dans {jours} jours).

Veuillez contacter notre secrétariat pour procéder au renouvellement
si vous souhaitez conserver cet emplacement.

Cordialement,
L'équipe de gestion du cimetière
        """.strip()
        _envoyer_email(
            concession.titulaire, TypeNotification.ALERTE_EXPIRATION,
            sujet, corps,
            reference_type="concession", reference_id=concession.id,
        )

        for admin in admins:
            sujet_admin = f"[Cimetière] Concession {concession.numero_contrat} expire dans {jours} jours"
            corps_admin = f"""
La concession {concession.numero_contrat} de {concession.titulaire.nom_complet}
expire dans {jours} jours ({concession.date_fin.strftime('%d/%m/%Y')}).
            """.strip()
            _envoyer_email(
                admin, TypeNotification.ALERTE_EXPIRATION,
                sujet_admin, corps_admin,
                reference_type="concession", reference_id=concession.id,
            )


# ─── Exhumations ───────────────────────────────────────────────────────────────

@shared_task
def notifier_demande_exhumation(exhumation_id):
    """Notifie les admins d'une nouvelle demande d'exhumation."""
    from apps.concessions.models import Exhumation
    from apps.users.models import Utilisateur, RoleUtilisateur

    exhumation = Exhumation.objects.select_related(
        "concession__reservation__caveau", "demandeur"
    ).get(id=exhumation_id)

    sujet = f"[Cimetière] Nouvelle demande d'exhumation {exhumation.numero_demande}"
    corps = f"""
Une nouvelle demande d'exhumation a été soumise.

N° demande : {exhumation.numero_demande}
Demandeur : {exhumation.demandeur.nom_complet}
Concession : {exhumation.concession.numero_contrat}
Caveau : {exhumation.concession.reservation.caveau.reference_complete}
Motif : {exhumation.motif}

Veuillez instruire cette demande depuis le tableau de bord.
    """.strip()

    admins = Utilisateur.objects.filter(
        role=RoleUtilisateur.ADMINISTRATEUR, is_active=True
    )
    for admin in admins:
        _envoyer_email(
            admin, TypeNotification.DEMANDE_EXHUMATION,
            sujet, corps,
            reference_type="exhumation", reference_id=exhumation.id,
        )


@shared_task
def generer_autorisation_exhumation(exhumation_id):
    """Génère l'autorisation PDF + PV d'exhumation et notifie le demandeur."""
    from apps.concessions.models import Exhumation
    from .pdf_generators import generer_pdf_autorisation_exhumation, generer_pdf_pv_exhumation
    from django.core.files.base import ContentFile

    exhumation = Exhumation.objects.select_related(
        "concession__reservation__caveau__bloc__zone__cimetiere",
        "demandeur", "autorisee_par"
    ).get(id=exhumation_id)

    pdf_autorisation = generer_pdf_autorisation_exhumation(exhumation)
    exhumation.autorisation_pdf.save(
        f"{exhumation.numero_demande}_autorisation.pdf",
        ContentFile(pdf_autorisation), save=False
    )

    pdf_pv = generer_pdf_pv_exhumation(exhumation)
    exhumation.proces_verbal_pdf.save(
        f"{exhumation.numero_demande}_pv.pdf",
        ContentFile(pdf_pv), save=False
    )
    exhumation.save()

    sujet = f"[Cimetière] Exhumation {exhumation.numero_demande} autorisée"
    corps = f"""
Bonjour {exhumation.demandeur.prenom},

Votre demande d'exhumation {exhumation.numero_demande} a été autorisée.

Vous trouverez ci-joint l'autorisation officielle et le procès-verbal associé.

Cordialement,
L'équipe de gestion du cimetière
    """.strip()

    _envoyer_email(
        exhumation.demandeur, TypeNotification.EXHUMATION_AUTORISEE,
        sujet, corps,
        pieces_jointes=[
            (f"{exhumation.numero_demande}_autorisation.pdf", pdf_autorisation, "application/pdf"),
            (f"{exhumation.numero_demande}_pv.pdf", pdf_pv, "application/pdf"),
        ],
        reference_type="exhumation", reference_id=exhumation.id,
    )


# ─── Seuils critiques (Cartographie) ──────────────────────────────────────────

@shared_task
def verifier_seuil_places_critiques(seuil_pct=90):
    """
    Tâche planifiée : alerte les admins si le taux d'occupation
    dépasse le seuil critique (par défaut 90%).
    """
    from apps.cartographie.models import Caveau, StatutCaveau
    from apps.users.models import Utilisateur, RoleUtilisateur

    total = Caveau.objects.count()
    if total == 0:
        return

    occupes_ou_reserves = Caveau.objects.filter(
        statut__in=[StatutCaveau.OCCUPE, StatutCaveau.RESERVE]
    ).count()

    taux = occupes_ou_reserves / total * 100

    if taux >= seuil_pct:
        sujet = f"[Cimetière] ALERTE — Seuil critique d'occupation atteint ({taux:.1f}%)"
        corps = f"""
ALERTE AUTOMATIQUE

Le taux d'occupation global du cimetière a atteint {taux:.1f}%
(seuil critique configuré : {seuil_pct}%).

Caveaux occupés/réservés : {occupes_ou_reserves} / {total}

Il est recommandé d'anticiper l'extension des espaces disponibles
ou de revoir la politique d'attribution.
        """.strip()

        admins = Utilisateur.objects.filter(
            role=RoleUtilisateur.ADMINISTRATEUR, is_active=True
        )
        for admin in admins:
            _envoyer_email(
                admin, TypeNotification.SEUIL_CRITIQUE,
                sujet, corps,
            )
