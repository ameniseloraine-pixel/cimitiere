"""
Commande de gestion : initialise la grille tarifaire par défaut.
Usage : python manage.py init_tarifs
"""

from django.core.management.base import BaseCommand
from apps.finance.services import initialiser_tarifs_par_defaut


class Command(BaseCommand):
    help = "Initialise la grille tarifaire par défaut (concessions, exhumations, frais de dossier...)"

    def handle(self, *args, **options):
        initialiser_tarifs_par_defaut()
        self.stdout.write(self.style.SUCCESS("Grille tarifaire initialisée avec succès."))
