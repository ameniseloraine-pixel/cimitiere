"""
Composants réutilisables — identité "premium" (or antique / anthracite),
entièrement compatibles mode clair / mode sombre, et responsive par défaut.
"""

import flet as ft
from config import COULEURS_STATUT, LIBELLES_STATUT, couleurs
from responsive import largeur_contenu, largeur_dispo


# ─── Ombres & rayons — vocabulaire visuel premium ─────────────────────────────

def _ombre_douce(page: ft.Page) -> ft.BoxShadow:
    return ft.BoxShadow(
        spread_radius=0, blur_radius=18,
        color=couleurs(page)["ombre"],
        offset=ft.Offset(0, 6),
    )


def _ombre_legere(page: ft.Page) -> ft.BoxShadow:
    return ft.BoxShadow(
        spread_radius=0, blur_radius=8,
        color=couleurs(page)["ombre"],
        offset=ft.Offset(0, 2),
    )


# ─── Badges de statut ──────────────────────────────────────────────────────────

def badge_statut(statut: str) -> ft.Container:
    couleur = COULEURS_STATUT.get(statut, "#9ca3af")
    libelle = LIBELLES_STATUT.get(statut, statut)
    return badge_generique(libelle, couleur)


def badge_generique(texte: str, couleur: str = "#6b7280") -> ft.Container:
    """Badge pilule coloré, teinte pastel + point plein pour lisibilité en mode sombre."""
    return ft.Container(
        content=ft.Row([
            ft.Container(width=7, height=7, bgcolor=couleur, border_radius=99),
            ft.Text(texte, color=couleur, size=12, weight=ft.FontWeight.W_600),
        ], spacing=6, tight=True),
        bgcolor=ft.colors.with_opacity(0.14, couleur),
        padding=ft.padding.symmetric(horizontal=12, vertical=6),
        border_radius=99,
        border=ft.border.all(1, ft.colors.with_opacity(0.30, couleur)),
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


# ─── Cartes ─────────────────────────────────────────────────────────────────

def carte_premium(page: ft.Page, content, padding: int = 20, expand=None) -> ft.Container:
    """Carte élevée de base : surface thème + bordure fine + ombre douce."""
    t = couleurs(page)
    return ft.Container(
        content=content,
        bgcolor=t["surface"],
        padding=padding,
        border_radius=16,
        border=ft.border.all(1, t["bordure"]),
        shadow=_ombre_legere(page),
        expand=expand,
        animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
    )


def carte_stat(page: ft.Page, titre: str, valeur, icone: str, couleur: str = None, tendance: str = None) -> ft.Container:
    """Carte de statistique premium pour le dashboard — accent or par défaut."""
    t = couleurs(page)
    couleur = couleur or t["accent"]
    contenu = [
        ft.Row([
            ft.Container(
                content=ft.Icon(icone, color=couleur, size=22),
                bgcolor=ft.colors.with_opacity(0.14, couleur),
                padding=10,
                border_radius=12,
            ),
            ft.Container(expand=True),
            *([ft.Text(tendance, size=12, color=couleur, weight=ft.FontWeight.W_600)] if tendance else []),
        ]),
        ft.Text(str(valeur), size=28, weight=ft.FontWeight.BOLD, color=t["texte"]),
        ft.Text(titre, size=13, color=t["texte_att"]),
    ]
    return carte_premium(page, ft.Column(contenu, spacing=8), expand=True)


# ─── Notifications ─────────────────────────────────────────────────────────────

def afficher_snackbar(page: ft.Page, message: str, succes: bool = True):
    page.open(
        ft.SnackBar(
            content=ft.Text(message, color="white"),
            bgcolor="#22c55e" if succes else "#ef4444",
            duration=4000,
            shape=ft.RoundedRectangleBorder(radius=10),
        )
    )


# ─── Champs & boutons ───────────────────────────────────────────────────────────

def champ_texte(label: str, **kwargs) -> ft.TextField:
    """TextField premium. N'impose plus de largeur fixe par défaut : le champ
    remplit son parent (utiliser conteneur_formulaire() pour plafonner la
    largeur sur grand écran). Si un width= explicite est passé, il est
    respecté (rétro-compatibilité), mais préférez laisser vide + stretch.
    """
    return ft.TextField(
        label=label,
        border_color=ft.colors.OUTLINE,
        focused_border_color=ft.colors.PRIMARY,
        border_radius=10,
        cursor_color=ft.colors.PRIMARY,
        expand=kwargs.pop("expand", True) if "width" not in kwargs else None,
        **kwargs,
    )


def bouton_principal(texte: str, on_click=None, icone: str = None, **kwargs) -> ft.ElevatedButton:
    """Bouton principal — dégradé or subtil, thème-aware."""
    return ft.ElevatedButton(
        text=texte,
        icon=icone,
        on_click=on_click,
        style=ft.ButtonStyle(
            bgcolor={
                ft.ControlState.DEFAULT: ft.colors.PRIMARY,
                ft.ControlState.HOVERED: ft.colors.PRIMARY,
            },
            color=ft.colors.ON_PRIMARY,
            shape=ft.RoundedRectangleBorder(radius=10),
            padding=ft.padding.symmetric(horizontal=22, vertical=16),
            elevation={ft.ControlState.DEFAULT: 0, ft.ControlState.HOVERED: 4},
            animation_duration=150,
        ),
        **kwargs,
    )


def bouton_secondaire(texte: str, on_click=None, icone: str = None, **kwargs) -> ft.OutlinedButton:
    return ft.OutlinedButton(
        text=texte,
        icon=icone,
        on_click=on_click,
        style=ft.ButtonStyle(
            side=ft.BorderSide(1, ft.colors.OUTLINE),
            shape=ft.RoundedRectangleBorder(radius=10),
            padding=ft.padding.symmetric(horizontal=22, vertical=16),
        ),
        **kwargs,
    )


# ─── Mise en page responsive de formulaires ────────────────────────────────────

def conteneur_formulaire(page: ft.Page, controls: list, largeur_max: int = 420, spacing: int = 14) -> ft.Container:
    """Enveloppe standard pour tout formulaire (login, réservation, etc.) :
    - plafonne la largeur sur grand écran (largeur_max)
    - occupe toute la largeur dispo sur mobile (jamais de débordement)
    - étire les champs enfants (STRETCH) pour qu'ils n'aient plus besoin
      d'un width= codé en dur.
    """
    return ft.Container(
        content=ft.Column(
            controls,
            spacing=spacing,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        ),
        width=largeur_contenu(page, largeur_max),
    )


# ─── États ──────────────────────────────────────────────────────────────────────

def chargement(message: str = "Chargement...") -> ft.Container:
    return ft.Container(
        content=ft.Column([
            ft.ProgressRing(color=ft.colors.PRIMARY, stroke_width=3),
            ft.Text(message, color=ft.colors.ON_SURFACE_VARIANT),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=12),
        alignment=ft.alignment.center,
        expand=True,
        padding=40,
    )


def etat_vide(message: str, icone: str = ft.icons.INBOX) -> ft.Container:
    return ft.Container(
        content=ft.Column([
            ft.Icon(icone, size=44, color=ft.colors.OUTLINE),
            ft.Text(message, color=ft.colors.ON_SURFACE_VARIANT, size=14, text_align=ft.TextAlign.CENTER),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=12),
        alignment=ft.alignment.center,
        padding=40,
    )
