"""
Utilitaires de mise en page responsive.
Trois paliers : mobile (<700px), tablette (700-1100px), desktop (>1100px).
"""

import flet as ft

SEUIL_MOBILE = 700
SEUIL_TABLETTE = 1100


def est_mobile(page: ft.Page) -> bool:
    """True si l'écran est en dessous du seuil mobile.

    page.width peut être None très brièvement avant le premier rendu ;
    dans ce cas on considère par défaut qu'on n'est PAS en mobile pour
    éviter un flash de layout mobile sur desktop au premier chargement.
    """
    return page.width is not None and page.width < SEUIL_MOBILE


def est_tablette(page: ft.Page) -> bool:
    return page.width is not None and SEUIL_MOBILE <= page.width < SEUIL_TABLETTE


def largeur_dispo(page: ft.Page, marge: int = 32) -> int:
    """Largeur utile de l'écran, avec une marge de sécurité (jamais < 280)."""
    if page.width is None:
        return 1000
    return max(280, int(page.width) - marge)


def largeur_contenu(page: ft.Page, largeur_max: int = 420, marge: int = 32) -> int:
    """Largeur idéale pour une carte / un formulaire : la valeur souhaitée,
    plafonnée par la largeur réelle de l'écran (moins la marge). Ne déborde
    donc jamais, quel que soit l'appareil.
    """
    return min(largeur_max, largeur_dispo(page, marge))


def colonnes_grille(page: ft.Page) -> int:
    """Nombre de colonnes conseillé pour une grille de cartes selon la largeur."""
    if est_mobile(page):
        return 1
    if est_tablette(page):
        return 2
    if page.width and page.width < 1500:
        return 3
    return 4
