"""
Configuration de l'application Flet
Identité visuelle "premium" — marbre anthracite + or antique,
déclinée en mode clair et mode sombre.
"""

import os
import flet as ft

# URL de base de l'API Django Ninja
API_BASE_URL = os.environ.get("CIMETIERE_API_URL", "http://localhost:8000/api")

# ─────────────────────────────────────────────────────────────────────────────
# Couleurs FONCTIONNELLES — imposées par le cahier des charges (carte SIG).
# Ne jamais les changer : elles portent un sens métier (dispo / réservé / etc.)
# et doivent rester identiques en clair comme en sombre pour ne jamais être
# ambiguës avec la couleur d'accent "or" de l'identité visuelle.
# ─────────────────────────────────────────────────────────────────────────────
COULEUR_DISPONIBLE = "#22c55e"       # Vert
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

# ─────────────────────────────────────────────────────────────────────────────
# Identité visuelle "premium" — Or antique sur anthracite / ivoire.
# ─────────────────────────────────────────────────────────────────────────────
OR_ANTIQUE = "#B8923C"        # Accent principal — mode clair
OR_METAL = "#D4AF37"          # Accent principal — mode sombre (plus lumineux)
ANTHRACITE = "#1C1F26"        # Texte / structure sombre
ANTHRACITE_PROFOND = "#12131A"

# Rétro-compatibilité avec le code existant qui importe encore ces noms :
COULEUR_PRIMAIRE = OR_ANTIQUE
COULEUR_SECONDAIRE = ANTHRACITE
COULEUR_FOND = "#FAF8F4"

# ─── Palette complète par mode ────────────────────────────────────────────────
THEME = {
    "light": {
        "fond": "#FAF8F4",              # ivoire chaud
        "surface": "#FFFFFF",
        "surface_alt": "#F3F0E9",       # cartes secondaires / hover
        "accent": OR_ANTIQUE,
        "accent_container": "#F3E7C9",
        "on_accent": "#FFFFFF",
        "texte": ANTHRACITE,
        "texte_att": "#5B5747",         # texte atténué
        "bordure": "#E7E1D3",
        "ombre": "#00000022",
    },
    "dark": {
        "fond": ANTHRACITE_PROFOND,
        "surface": "#1B1D24",
        "surface_alt": "#22242C",
        "accent": OR_METAL,
        "accent_container": "#3A2F0E",
        "on_accent": "#1C1500",
        "texte": "#EDEBE4",
        "texte_att": "#A6A296",
        "bordure": "#33353E",
        "ombre": "#00000066",
    },
}


def couleurs(page: ft.Page) -> dict:
    """Retourne la palette active (clair/sombre) pour la page donnée."""
    mode = "dark" if page.theme_mode == ft.ThemeMode.DARK else "light"
    return THEME[mode]


def construire_theme(mode: str) -> ft.Theme:
    """Construit un ft.Theme Material avec le ColorScheme premium pour le mode donné."""
    t = THEME[mode]
    if mode == "light":
        scheme = ft.ColorScheme(
            primary=t["accent"], on_primary=t["on_accent"],
            primary_container=t["accent_container"], on_primary_container="#4A3A0A",
            secondary=ANTHRACITE, on_secondary="#FFFFFF",
            surface=t["surface"], on_surface=t["texte"],
            background=t["fond"], on_background=t["texte"],
            outline=t["bordure"],
            error="#DC2626", on_error="#FFFFFF",
        )
    else:
        scheme = ft.ColorScheme(
            primary=t["accent"], on_primary=t["on_accent"],
            primary_container=t["accent_container"], on_primary_container=t["accent_container"],
            secondary="#C9C6BE", on_secondary=ANTHRACITE_PROFOND,
            surface=t["surface"], on_surface=t["texte"],
            background=t["fond"], on_background=t["texte"],
            outline=t["bordure"],
            error="#F87171", on_error="#450A0A",
        )
    return ft.Theme(color_scheme=scheme, font_family="Inter, Segoe UI, Roboto")


# ─── Typographie ──────────────────────────────────────────────────────────────
POLICE_TITRE = "Playfair Display, Georgia, serif"   # touche élégante pour les grands titres
POLICE_TEXTE = "Inter, Segoe UI, Roboto, sans-serif"
