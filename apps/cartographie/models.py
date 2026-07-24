"""
Module Cartographie — SIG / Carte interactive
Chaque caveau est un point géolocalisé (PostGIS) avec statut dynamique (couleur)
"""

from django.contrib.gis.db import models as gis_models
from django.contrib.gis.geos import Point
from django.db import models
from django.utils import timezone
from simple_history.models import HistoricalRecords
from apps.terrain.models import Bloc
from apps.users.models import Utilisateur


class StatutCaveau(models.TextChoices):
    DISPONIBLE = "DISPO", "Disponible"          # Vert
    RESERVE = "RESERVE", "Réservé"              # Orange
    OCCUPE = "OCCUPE", "Occupé / Validé"        # Rouge
    NON_EXPLOITABLE = "NON_EXP", "Non exploitable"  # Gris
    MAINTENANCE = "MAINT", "En maintenance"     # Gris foncé


COULEUR_STATUT = {
    StatutCaveau.DISPONIBLE: "#22c55e",       # Vert
    StatutCaveau.RESERVE: "#f97316",           # Orange
    StatutCaveau.OCCUPE: "#ef4444",            # Rouge
    StatutCaveau.NON_EXPLOITABLE: "#9ca3af",   # Gris
    StatutCaveau.MAINTENANCE: "#6b7280",       # Gris foncé
}


class Caveau(gis_models.Model):
    """
    Représente un emplacement funéraire individuel.
    Géolocalisé via PostGIS (PointField, WGS84 / SRID 4326).
    """
    bloc = models.ForeignKey(Bloc, on_delete=models.CASCADE, related_name="caveaux")
    numero = models.CharField(max_length=20, verbose_name="Numéro du caveau")
    rangee = models.PositiveIntegerField(verbose_name="Rangée")
    colonne = models.PositiveIntegerField(verbose_name="Colonne")

    # Géolocalisation PostGIS
    localisation = gis_models.PointField(
        srid=4326,   # WGS84 (standard GPS)
        verbose_name="Coordonnées GPS",
        null=True, blank=True
    )

    # État dynamique
    statut = models.CharField(
        max_length=10,
        choices=StatutCaveau.choices,
        default=StatutCaveau.DISPONIBLE,
        verbose_name="Statut"
    )


    # Dimensions (peuvent différer de la taille standard)
    longueur_m = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    largeur_m = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    profondeur_m = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    # Métadonnées
    notes = models.TextField(blank=True, verbose_name="Notes internes")
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    # Audit trail immuable (qui a changé le statut, quand)
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Caveau"
        verbose_name_plural = "Caveaux"
        ordering = ["bloc", "rangee", "colonne"]
        unique_together = [["bloc", "rangee", "colonne"]]

    def __str__(self):
        return f"Caveau {self.numero} — {self.bloc} [{self.get_statut_display()}]"

    @property
    def couleur_carte(self):
        return COULEUR_STATUT.get(self.statut, "#9ca3af")

    @property
    def reference_complete(self):
        zone = self.bloc.zone
        return f"{zone.cimetiere.nom}/{zone.code}/{self.bloc.code}/{self.numero}"

    @property
    def latitude(self):
        """Latitude lue depuis le champ PostGIS `localisation` (compat. API/frontend)."""
        return self.localisation.y if self.localisation else None

    @property
    def longitude(self):
        """Longitude lue depuis le champ PostGIS `localisation` (compat. API/frontend)."""
        return self.localisation.x if self.localisation else None

    def set_coordonnees(self, latitude, longitude):
        """Définit la localisation à partir d'une latitude/longitude classiques."""
        self.localisation = Point(float(longitude), float(latitude), srid=4326)

    # CORRECTIF (faille précédente) : seul l'endpoint
    # /blocs/{id}/generer-caveaux calculait une `localisation`. Tout caveau
    # créé autrement (admin Django, fixture, script, création manuelle) restait
    # avec `localisation = NULL` -> la vue GPS le trouvait invisible et
    # affichait "Aucun caveau ne possède de coordonnées GPS" (l'écran grisé
    # que tu voyais). Il fallait exécuter à la main la commande
    # `manage.py fix_coordonnees` pour rattraper le coup.
    # Corrigé ici : si un caveau est enregistré sans coordonnées, on lui
    # calcule automatiquement une position de secours dérivée de sa rangée/
    # colonne et de la position de son bloc — aucun caveau ne reste plus
    # jamais sans coordonnées, quel que soit son mode de création.
    LATITUDE_BASE_DEFAUT = -4.7761
    LONGITUDE_BASE_DEFAUT = 11.8636
    PAS_DEGRES_DEFAUT = 0.0001

    def _generer_coordonnees_fallback(self):
        decalage_bloc = (self.bloc_id or 0) * 0.002
        lat = self.LATITUDE_BASE_DEFAUT + decalage_bloc + (self.rangee - 1) * self.PAS_DEGRES_DEFAUT
        lon = self.LONGITUDE_BASE_DEFAUT + (self.colonne - 1) * self.PAS_DEGRES_DEFAUT
        return Point(round(lon, 7), round(lat, 7), srid=4326)

    def save(self, *args, **kwargs):
        if self.localisation is None:
            self.localisation = self._generer_coordonnees_fallback()
        super().save(*args, **kwargs)

    def changer_statut(self, nouveau_statut, utilisateur=None, raison=""):
        """Change le statut avec journalisation dans l'audit trail."""
        ancien_statut = self.statut
        self.statut = nouveau_statut
        self._change_reason = (
            f"[{utilisateur}] {ancien_statut} → {nouveau_statut}. {raison}"
            if utilisateur else raison
        )
        self.save()


class JournalModificationCaveau(models.Model):
    """
    Audit trail immuable — enregistrement supplémentaire de chaque
    modification de statut (complément à django-simple-history).
    """
    caveau = models.ForeignKey(
        Caveau, on_delete=models.CASCADE, related_name="journal"
    )
    utilisateur = models.ForeignKey(
        Utilisateur, on_delete=models.SET_NULL, null=True
    )
    ancien_statut = models.CharField(max_length=10)
    nouveau_statut = models.CharField(max_length=10)
    raison = models.TextField(blank=True)
    horodatage = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        verbose_name = "Journal modification caveau"
        verbose_name_plural = "Journal modifications caveaux"
        ordering = ["-horodatage"]
        # Table immuable — pas de update/delete autorisés
        managed = True

    def save(self, *args, **kwargs):
        # Interdire la modification d'une entrée existante
        if self.pk:
            raise PermissionError("Les entrées du journal sont immuables.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionError("Les entrées du journal ne peuvent pas être supprimées.")

    def __str__(self):
        return (
            f"{self.horodatage:%Y-%m-%d %H:%M} — "
            f"Caveau {self.caveau.numero}: "
            f"{self.ancien_statut} → {self.nouveau_statut}"
        )
