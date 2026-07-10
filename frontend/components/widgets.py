"""
Composants réutilisables — Badges de statut, cartes, notifications
"""

import flet as ft
from config import COULEURS_STATUT, LIBELLES_STATUT, COULEUR_PRIMAIRE


def badge_statut(statut: str) -> ft.Container:
    """Badge coloré affichant un statut de caveau."""
    couleur = COULEURS_STATUT.get(statut, "#9ca3af")
    libelle = LIBELLES_STATUT.get(statut, statut)
    return ft.Container(
        content=ft.Text(libelle, color="white", size=12, weight=ft.FontWeight.W_600),
        bgcolor=couleur,
        padding=ft.padding.symmetric(horizontal=10, vertical=4),
        border_radius=12,
    )


def badge_generique(texte: str, couleur: str = "#6b7280") -> ft.Container:
    """Badge générique pour statuts de réservation/facture/concession."""
    return ft.Container(
        content=ft.Text(texte, color="white", size=12, weight=ft.FontWeight.W_600),
        bgcolor=couleur,
        padding=ft.padding.symmetric(horizontal=10, vertical=4),
        border_radius=12,
    )


COULEURS_STATUT_RESERVATION = {
    "ATTENTE": "#f97316",
    "VALIDEE": "#22c55e",
    "REJETEE": "#ef4444",
    "ANNULEE": "#9ca3af",
}

COULEURS_STATUT_FACTURE = {
    "BROUILLON": "#9ca3af",
    "EMISE": "#3b82f6",
    "PARTIEL": "#f97316",
    "PAYEE": "#22c55e",
    "RETARD": "#ef4444",
    "ANNULEE": "#6b7280",
}

COULEURS_STATUT_CONCESSION = {
    "ACTIVE": "#22c55e",
    "ALERTE": "#f97316",
    "EXPIREE": "#ef4444",
    "RESILIEE": "#6b7280",
    "RENOUVELEE": "#3b82f6",
}

COULEURS_STATUT_EXHUMATION = {
    "DEMANDE": "#f97316",
    "INSTRUCT": "#3b82f6",
    "AUTORISEE": "#22c55e",
    "REALISEE": "#6b7280",
    "REFUSEE": "#ef4444",
}


def carte_stat(titre: str, valeur, icone: str, couleur: str = COULEUR_PRIMAIRE) -> ft.Container:
    """Carte de statistique pour le dashboard."""
    return ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Icon(icone, color=couleur, size=28),
                ft.Text(str(valeur), size=26, weight=ft.FontWeight.BOLD),
            ], spacing=10),
            ft.Text(titre, size=13, color="#6b7280"),
        ], spacing=6),
        bgcolor=ft.colors.SURFACE,
        padding=16,
        border_radius=12,
        border=ft.border.all(1, "#e5e7eb"),
        expand=True,
    )


def afficher_snackbar(page: ft.Page, message: str, succes: bool = True):
    """Affiche une notification toast en bas de l'écran."""
    page.open(
        ft.SnackBar(
            content=ft.Text(message, color="white"),
            bgcolor="#22c55e" if succes else "#ef4444",
            duration=4000,
        )
    )


def champ_texte(label: str, **kwargs) -> ft.TextField:
    """TextField stylé cohérent avec l'identité visuelle."""
    return ft.TextField(
        label=label,
        border_color="#d1d5db",
        focused_border_color=COULEUR_PRIMAIRE,
        border_radius=8,
        **kwargs,
    )


def bouton_principal(texte: str, on_click=None, icone: str = None, **kwargs) -> ft.ElevatedButton:
    """Bouton principal stylé avec la couleur de l'application."""
    return ft.ElevatedButton(
        text=texte,
        icon=icone,
        on_click=on_click,
        style=ft.ButtonStyle(
            bgcolor=COULEUR_PRIMAIRE,
            color="white",
            shape=ft.RoundedRectangleBorder(radius=8),
            padding=ft.padding.symmetric(horizontal=20, vertical=14),
        ),
        **kwargs,
    )


def chargement(message: str = "Chargement...") -> ft.Container:
    """Indicateur de chargement centré."""
    return ft.Container(
        content=ft.Column([
            ft.ProgressRing(color=COULEUR_PRIMAIRE),
            ft.Text(message, color="#6b7280"),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=12),
        alignment=ft.alignment.center,
        expand=True,
        padding=40,
    )


def etat_vide(message: str, icone: str = ft.icons.INBOX) -> ft.Container:
    """Affichage d'un état vide (aucune donnée)."""
    return ft.Container(
        content=ft.Column([
            ft.Icon(icone, size=48, color="#d1d5db"),
            ft.Text(message, color="#9ca3af", size=14),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=12),
        alignment=ft.alignment.center,
        padding=40,
    )
