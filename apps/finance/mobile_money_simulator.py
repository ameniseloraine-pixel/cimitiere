"""
Simulateur Mobile Money / Airtel Money — API de test interne

Reproduit le comportement fonctionnel d'un agrégateur de paiement mobile
réel (push de paiement, code de confirmation, validation/échec/expiration),
sans dépendre d'un compte marchand MTN/Airtel réel (qui nécessite un
enregistrement d'entreprise).

Flux simulé :
1. initier_transaction()   -> crée la transaction, génère un code à 6
                               chiffres, "pousse" une notification (email)
2. confirmer_transaction() -> vérifie le code saisi par le client
3. en cas de succès        -> crée automatiquement le Paiement associé
                               et met à jour la facture
"""

import logging
import random
import string
from datetime import timedelta
from django.utils import timezone
from django.conf import settings

from .models import (
    TransactionMobileMoney, StatutTransactionMobile,
    Paiement, CanalPaiement,
)

logger = logging.getLogger(__name__)

DUREE_VALIDITE_MINUTES = 5
TAUX_ECHEC_SIMULE_PCT = 0  


MOTIFS_ECHEC_SIMULES = [
    "Solde Mobile Money insuffisant.",
    "Transaction refusée par l'opérateur.",
    "Numéro non enregistré pour les paiements Mobile Money.",
    "Délai d'attente de l'opérateur dépassé.",
]


def initier_transaction(facture, initiateur, canal, telephone, montant) -> TransactionMobileMoney:
    """
    Étape 1 : initie une transaction Mobile Money / Airtel Money.
    Génère un code de confirmation à 6 chiffres et "pousse" la notification
    (envoyée par email, faisant office de notification push opérateur).
    """
    if canal not in (CanalPaiement.MOBILE_MONEY, CanalPaiement.AIRTEL_MONEY):
        raise ValueError("Canal invalide pour une transaction mobile.")

    code = "".join(random.choices(string.digits, k=6))

    transaction = TransactionMobileMoney.objects.create(
        facture=facture,
        initiateur=initiateur,
        canal=canal,
        telephone=telephone,
        montant=montant,
        statut=StatutTransactionMobile.EN_ATTENTE_CONFIRMATION,
        code_confirmation=code,
        date_expiration=timezone.now() + timedelta(minutes=DUREE_VALIDITE_MINUTES),
    )

    _envoyer_notification_push_simulee(transaction)

    return transaction


def _envoyer_notification_push_simulee(transaction: TransactionMobileMoney):
    """
    Simule la notification push USSD que l'opérateur enverrait normalement
    au téléphone du client. Envoyée par email pour ce projet de test.

    CORRECTIF (faille précédente) : cette fonction utilisait
    `django.core.mail.send_mail`, qui passe par le backend SMTP par
    défaut de Django (localhost:25). Aucun serveur SMTP n'existe sur
    Render, et l'appel était protégé par `fail_silently=True` : le
    code de confirmation n'était donc JAMAIS envoyé, sans la moindre
    erreur visible nulle part.

    Corrigé ici en appelant directement l'API HTTPS de Brevo — exactement
    comme le fait déjà `apps/users/services.py::_envoyer_email_mfa` pour
    le code MFA de connexion, et `apps/notifications/tasks.py` pour les
    factures. Toute erreur d'envoi est maintenant journalisée au lieu
    d'être avalée en silence.
    """
    import requests

    operateur = "MTN Mobile Money" if transaction.canal == CanalPaiement.MOBILE_MONEY else "Airtel Money"

    sujet = f"[{operateur}] Confirmation de paiement requise"
    corps_html = f"""
    <p>Vous avez initié un paiement {operateur}.</p>
    <p>
        Montant : <strong>{transaction.montant:,.0f} FCFA</strong><br>
        Numéro : {transaction.telephone}<br>
        Référence : {transaction.reference}
    </p>
    <p>Code de confirmation : <strong style="font-size:20px">{transaction.code_confirmation}</strong></p>
    <p>Ce code expire dans {DUREE_VALIDITE_MINUTES} minutes.
    Si vous n'êtes pas à l'origine de cette demande, ignorez ce message.</p>
    <p><em>(Ceci est une simulation à des fins de démonstration — aucune somme
    réelle n'est débitée.)</em></p>
    """

    try:
        response = requests.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={
                "api-key": settings.BREVO_API_KEY,
                "Content-Type": "application/json",
                "accept": "application/json",
            },
            json={
                "sender": {"name": "Gestion Cimetière", "email": settings.DEFAULT_FROM_EMAIL},
                "to": [{"email": transaction.initiateur.email}],
                "subject": sujet,
                "htmlContent": corps_html,
            },
            timeout=10,
        )
        if response.status_code >= 400:
            raise Exception(f"Échec envoi email Brevo: {response.status_code} - {response.text}")
    except Exception:
        # La transaction reste utilisable (le client peut toujours saisir
        # le code s'il le connaît / le redemander), mais on journalise
        # l'échec au lieu de l'avaler silencieusement.
        logger.exception(
            "Échec de l'envoi du code de confirmation Mobile Money à %s (transaction %s)",
            transaction.initiateur.email, transaction.reference,
        )


def confirmer_transaction(transaction: TransactionMobileMoney, code_saisi: str, enregistre_par=None) -> dict:
    """
    Étape 2 : confirme une transaction avec le code reçu.

    Retourne un dict {"succes": bool, "transaction": ..., "detail": str}.
    En cas de succès, crée automatiquement le Paiement et met à jour la facture.
    """
    if transaction.statut != StatutTransactionMobile.EN_ATTENTE_CONFIRMATION:
        return {
            "succes": False,
            "transaction": transaction,
            "detail": f"Transaction déjà traitée (statut : {transaction.get_statut_display()}).",
        }

    if transaction.est_expiree:
        transaction.statut = StatutTransactionMobile.EXPIREE
        transaction.motif_echec = "Code de confirmation expiré."
        transaction.save(update_fields=["statut", "motif_echec"])
        return {
            "succes": False,
            "transaction": transaction,
            "detail": "Le code a expiré. Veuillez relancer le paiement.",
        }

    transaction.tentatives += 1

    if transaction.tentatives > 3:
        transaction.statut = StatutTransactionMobile.ECHOUEE
        transaction.motif_echec = "Trop de tentatives incorrectes."
        transaction.save(update_fields=["statut", "tentatives", "motif_echec"])
        return {
            "succes": False,
            "transaction": transaction,
            "detail": "Trop de tentatives. Transaction annulée.",
        }

    if transaction.code_confirmation != code_saisi:
        transaction.save(update_fields=["tentatives"])
        return {
            "succes": False,
            "transaction": transaction,
            "detail": f"Code incorrect. {3 - transaction.tentatives} tentative(s) restante(s).",
        }

    # Code correct : simuler une issue réaliste (succès ou échec opérateur)
    echec_simule = random.randint(1, 100) <= TAUX_ECHEC_SIMULE_PCT

    if echec_simule:
        transaction.statut = StatutTransactionMobile.ECHOUEE
        transaction.motif_echec = random.choice(MOTIFS_ECHEC_SIMULES)
        transaction.save(update_fields=["statut", "tentatives", "motif_echec"])
        return {
            "succes": False,
            "transaction": transaction,
            "detail": f"Paiement refusé par l'opérateur : {transaction.motif_echec}",
        }

    # Succès : créer le paiement réel et mettre à jour la transaction
    paiement = Paiement.objects.create(
        facture=transaction.facture,
        canal=transaction.canal,
        montant=transaction.montant,
        reference_transaction=transaction.reference,
        telephone_paiement=transaction.telephone,
        enregistre_par=enregistre_par or transaction.initiateur,
        notes="Paiement confirmé via simulation Mobile Money.",
    )

    transaction.statut = StatutTransactionMobile.CONFIRMEE
    transaction.date_confirmation = timezone.now()
    transaction.paiement_resultant = paiement
    transaction.save(update_fields=["statut", "date_confirmation", "paiement_resultant", "tentatives"])

    return {
        "succes": True,
        "transaction": transaction,
        "paiement": paiement,
        "detail": "Paiement confirmé avec succès.",
    }


def annuler_transaction(transaction: TransactionMobileMoney) -> TransactionMobileMoney:
    """Annule une transaction en attente (à l'initiative du client)."""
    if transaction.statut == StatutTransactionMobile.EN_ATTENTE_CONFIRMATION:
        transaction.statut = StatutTransactionMobile.ANNULEE
        transaction.save(update_fields=["statut"])
    return transaction
