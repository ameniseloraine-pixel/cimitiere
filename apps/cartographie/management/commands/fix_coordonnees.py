"""
Commande de correction : attribue des coordonnees GPS realistes
a tous les caveaux existants, sans toucher a aucune autre donnee.
"""

from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point
from apps.cartographie.models import Caveau

LATITUDE_BASE = -4.7761
LONGITUDE_BASE = 11.8636
PAS_DEGRES = 0.0001


class Command(BaseCommand):
    help = "Corrige les coordonnees GPS (latitude/longitude) de tous les caveaux."

    def handle(self, *args, **options):
        caveaux = Caveau.objects.select_related("bloc__zone").order_by(
            "bloc__zone__code", "bloc__code", "numero"
        )
        total = caveaux.count()

        if total == 0:
            self.stdout.write(self.style.WARNING("Aucun caveau trouve."))
            return

        compteur = 0
        for index, caveau in enumerate(caveaux):
            colonnes = 15
            ligne = index // colonnes
            colonne = index % colonnes

            lat = LATITUDE_BASE + (ligne * PAS_DEGRES)
            lon = LONGITUDE_BASE + (colonne * PAS_DEGRES)
            caveau.localisation = Point(lon, lat, srid=4326)
            caveau.save(update_fields=["localisation"])
            compteur += 1

        self.stdout.write(
            self.style.SUCCESS(f"{compteur}/{total} caveaux mis a jour avec des coordonnees GPS valides.")
        )
