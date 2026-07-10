"""
Module Terrain — Gestion spatiale du cimetière
Superficie, zones, blocs, allées, calcul automatique des places
"""

from django.db import models
from django.core.validators import MinValueValidator
from simple_history.models import HistoricalRecords
from apps.users.models import Utilisateur


class Cimetiere(models.Model):
    """
    Entité principale représentant le cimetière.
    Un seul enregistrement en pratique (singleton).
    """
    nom = models.CharField(max_length=200, verbose_name="Nom du cimetière")
    adresse = models.TextField(verbose_name="Adresse complète")
    ville = models.CharField(max_length=100)
    superficie_totale_m2 = models.DecimalField(
        max_digits=12, decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name="Superficie totale (m²)"
    )
    # Taille standard d'un tombeau (configurable)
    tombeau_longueur_m = models.DecimalField(
        max_digits=5, decimal_places=2,
        default=2.50,
        verbose_name="Longueur standard tombeau (m)"
    )
    tombeau_largeur_m = models.DecimalField(
        max_digits=5, decimal_places=2,
        default=1.20,
        verbose_name="Largeur standard tombeau (m)"
    )
    # Surface réservée aux chemins et zones non exploitables (%)
    pourcentage_chemins = models.DecimalField(
        max_digits=5, decimal_places=2,
        default=20.00,
        verbose_name="% surface chemins/non exploitable"
    )
    telephone = models.CharField(max_length=20, blank=True)
    email_contact = models.EmailField(blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Cimetière"
        verbose_name_plural = "Cimetières"

    def __str__(self):
        return self.nom

    @property
    def superficie_zones_non_exploitables_m2(self):
        """
        Somme réelle des superficies des zones marquées comme non
        exploitables ou chemins/allées (déduction faite faite à partir
        des zones effectivement créées par l'admin, conformément au
        cahier des charges §2.2).
        """
        from django.db.models import Sum
        total = self.zones.filter(
            type_zone__in=[Zone.TypeZone.NON_EXPLOITABLE, Zone.TypeZone.CHEMIN]
        ).aggregate(total=Sum("superficie_m2"))["total"]
        return float(total) if total else 0.0

    @property
    def superficie_zones_exploitables_m2(self):
        """Somme réelle des superficies des zones marquées exploitables."""
        from django.db.models import Sum
        total = self.zones.filter(
            type_zone=Zone.TypeZone.EXPLOITABLE
        ).aggregate(total=Sum("superficie_m2"))["total"]
        return float(total) if total else 0.0

    @property
    def surface_exploitable_m2(self):
        """
        Surface nette exploitable, déduction faite des zones non
        exploitables et des chemins (cahier des charges §2.2).

        Calcul prioritaire : somme réelle des superficies des zones
        exploitables effectivement créées par l'admin.

        Fallback : tant qu'aucune zone n'a encore été créée (configuration
        initiale du cimetière), on retombe sur une estimation basée sur le
        pourcentage forfaitaire `pourcentage_chemins`, pour ne pas afficher
        une capacité de 0 avant le découpage en zones.
        """
        if self.zones.exists():
            return self.superficie_zones_exploitables_m2
        ratio = 1 - (self.pourcentage_chemins / 100)
        return float(self.superficie_totale_m2) * float(ratio)

    @property
    def surface_tombeau_m2(self):
        return float(self.tombeau_longueur_m) * float(self.tombeau_largeur_m)

    @property
    def capacite_theorique_totale(self):
        """Nombre maximum théorique de tombeaux."""
        if self.surface_tombeau_m2 == 0:
            return 0
        return int(self.surface_exploitable_m2 / self.surface_tombeau_m2)


class Zone(models.Model):
    """
    Division principale du cimetière (ex: Zone A, Zone B, Zone Musulmane...).
    """
    class TypeZone(models.TextChoices):
        EXPLOITABLE = "EXPLOIT", "Exploitable"
        CHEMIN = "CHEMIN", "Chemin / Allée"
        TECHNIQUE = "TECH", "Zone technique"
        ADMINISTRATIVE = "ADMIN", "Zone administrative"
        NON_EXPLOITABLE = "NON_EXP", "Non exploitable"

    cimetiere = models.ForeignKey(
        Cimetiere, on_delete=models.CASCADE, related_name="zones"
    )
    nom = models.CharField(max_length=100, verbose_name="Nom de la zone")
    code = models.CharField(max_length=10, verbose_name="Code zone (ex: A, B, C)")
    type_zone = models.CharField(
        max_length=10,
        choices=TypeZone.choices,
        default=TypeZone.EXPLOITABLE
    )
    superficie_m2 = models.DecimalField(
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    description = models.TextField(blank=True)
    ordre_affichage = models.PositiveIntegerField(default=0)
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Zone"
        verbose_name_plural = "Zones"
        ordering = ["ordre_affichage", "code"]
        unique_together = [["cimetiere", "code"]]

    def __str__(self):
        return f"{self.cimetiere.nom} — Zone {self.code} ({self.nom})"


class Bloc(models.Model):
    """
    Subdivision d'une zone (ex: Bloc A1, A2...).
    """
    zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name="blocs")
    nom = models.CharField(max_length=100)
    code = models.CharField(max_length=10)
    nombre_rangees = models.PositiveIntegerField(default=1)
    nombre_colonnes = models.PositiveIntegerField(default=1)
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Bloc"
        verbose_name_plural = "Blocs"
        ordering = ["code"]
        unique_together = [["zone", "code"]]

    def __str__(self):
        return f"Bloc {self.code} — {self.zone}"

    @property
    def capacite_theorique(self):
        return self.nombre_rangees * self.nombre_colonnes
