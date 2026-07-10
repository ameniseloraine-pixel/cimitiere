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

import random
import string
from datetime import timedelta
from django.utils import timezone
from django.conf import settings

from .models import (
    TransactionMobileMoney, StatutTransactionMobile,
    Paiement, CanalPaiement,
)

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
    """
    from django.core.mail import send_mail

    operateur = "MTN Mobile Money" if transaction.canal == CanalPaiement.MOBILE_MONEY else "Airtel Money"

    sujet = f"[{operateur}] Confirmation de paiement requise"
    corps = f"""
Vous avez initié un paiement {operateur}.

Montant : {transaction.montant:,.0f} FCFA
Numéro : {transaction.telephone}
Référence : {transaction.reference}

Code de confirmation : {transaction.code_confirmation}

Ce code expire dans {DUREE_VALIDITE_MINUTES} minutes.
Si vous n'êtes pas à l'origine de cette demande, ignorez ce message.

(Ceci est une simulation à des fins de démonstration — aucune somme
réelle n'est débitée.)
    """.strip()

    try:
        send_mail(
            subject=sujet,
            message=corps,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@cimetiere.app"),
            recipient_list=[transaction.initiateur.email],
            fail_silently=True,
        )
    except Exception:
        pass  # La simulation continue même si l'email échoue en dev


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
