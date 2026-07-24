"""
Configuration de l'application Flet
"""

import os

# URL de base de l'API Django Ninja
API_BASE_URL = os.environ.get("CIMETIERE_API_URL", "http://localhost:8000/api")

# Couleurs cohérentes avec le code couleur du cahier des charges
COULEUR_DISPONIBLE = "#22c55e"      # Vert
COULEUR_RESERVE = "#f97316"          # Orange
COULEUR_OCCUPE = "#ef4444"           # Rouge
COULEUR_NON_EXPLOITABLE = "#9ca3af"  # Gris
COULEUR_MAINTENANCE = "#6b7280"      # Gris foncé

COULEURS_STATUT = {
    "DISPO": COULEUR_DISPONIBLE,
    "RESERVE": COULEUR_RESERVE,
    "OCCUPE": COULEUR_OCCUPE,
    "NON_EXP": COULEUR_NON_EXPLOITABLE,
    "MAINT": COULEUR_MAINTENANCE,
}

LIBELLES_STATUT = {
    "DISPO": "Disponible",
    "RESERVE": "Réservé / En attente",
    "OCCUPE": "Occupé / Validé",
    "NON_EXP": "Non exploitable",
    "MAINT": "En maintenance",
}

# Couleur principale de l'application (identité visuelle)
COULEUR_PRIMAIRE = "#2d6a4f"
COULEUR_SECONDAIRE = "#1b4332"
COULEUR_FOND = "#f8fafc"
