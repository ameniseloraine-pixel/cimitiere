"""
Commande de démarrage : crée/synchronise LE super admin désigné, et peut
désactiver (sans jamais supprimer) les autres comptes admin/superuser —
utile pour nettoyer les comptes de test avant une remise, sans risquer de
perdre des données de façon irréversible.

Variables d'environnement :
  ADMIN_EMAIL             (obligatoire) — ex: mvibundulugaetan1@gmail.com
  ADMIN_PASSWORD          (obligatoire)
  ADMIN_NOM               (optionnel, défaut "Admin")
  ADMIN_PRENOM            (optionnel, défaut "Site")
  DESACTIVER_AUTRES_ADMINS (optionnel, "true" pour désactiver les autres
                             comptes ADMIN/superuser — is_active=False,
                             ils ne sont JAMAIS supprimés de la base)

Idempotente et sûre à relancer à chaque déploiement.
"""

from decouple import config
from django.core.management.base import BaseCommand
from apps.users.models import Utilisateur, RoleUtilisateur


class Command(BaseCommand):
    help = "Crée/synchronise le super admin désigné à partir des variables d'environnement."

    def handle(self, *args, **options):
        email = config("ADMIN_EMAIL", default="").strip()
        password = config("ADMIN_PASSWORD", default="").strip()
        nom = config("ADMIN_NOM", default="Admin").strip()
        prenom = config("ADMIN_PRENOM", default="Site").strip()
        desactiver_autres = config("DESACTIVER_AUTRES_ADMINS", default="").strip().lower() == "true"

        if not email or not password:
            self.stdout.write(self.style.WARNING(
                "ADMIN_EMAIL / ADMIN_PASSWORD non définies — aucune action."
            ))
            return

        user, cree = Utilisateur.objects.get_or_create(
            email=email,
            defaults={
                "nom": nom, "prenom": prenom,
                "role": RoleUtilisateur.ADMINISTRATEUR,
                "is_staff": True, "is_superuser": True,
                # CORRECTIF : le MFA reste obligatoire, y compris pour ce
                # compte — sinon on recrée la faille identifiée plus tôt
                # (bypass MFA via create_superuser / Django admin).
                "is_active": True, "mfa_activee": True,
            },
        )
        user.set_password(password)
        user.nom = nom
        user.prenom = prenom
        user.role = RoleUtilisateur.ADMINISTRATEUR
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.mfa_activee = True
        user.save()

        action = "créé" if cree else "mis à jour"
        self.stdout.write(self.style.SUCCESS(f"Super admin {action} : {email}"))

        if desactiver_autres:
            autres = Utilisateur.objects.filter(
                is_superuser=True
            ).exclude(email=email)
            nb = autres.count()
            autres.update(is_active=False)
            self.stdout.write(self.style.SUCCESS(
                f"{nb} autre(s) compte(s) admin/superuser désactivé(s) (pas supprimés — is_active=False)."
            ))
