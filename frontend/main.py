"""
Application Flet — Gestion de Cimetière
Point d'entrée principal : navigation, menu latéral selon le rôle (RBAC)
Thèmes : clair (blanc) et sombre (noir) — basculable depuis le header

Lancement (Windows / Mac / Linux) :
    pip install flet requests
    flet run frontend/main.py             (mode desktop)
    flet run frontend/main.py --web        (mode navigateur)

Variable d'environnement optionnelle :
    CIMETIERE_API_URL=http://localhost:8000/api   (par défaut)
"""

import flet as ft

from api_client import APIClient
from config import COULEUR_PRIMAIRE, COULEUR_SECONDAIRE, COULEUR_FOND

from views.login_view import LoginView
from views.register_view import RegisterView
from views.dashboard_view import DashboardView
from views.terrain_view import TerrainView
from views.carte_view import CarteView
from views.reservation_form_view import ReservationFormView
from views.reservations_view import ReservationsView
from views.concessions_view import ConcessionsView
from views.finance_view import FinanceView


def main(page: ft.Page):
    page.title = "Gestion de Cimetière"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.bgcolor = COULEUR_FOND
    page.window.width = 1200
    page.window.height = 800
    page.window.min_width = 360
    page.padding = 0

    # ─── Thème clair / sombre ─────────────────────────────────────────────────
    page.theme = ft.Theme(
        color_scheme_seed=COULEUR_PRIMAIRE,
    )
    page.dark_theme = ft.Theme(
        color_scheme_seed=COULEUR_PRIMAIRE,
    )

    def basculer_theme(e):
        if page.theme_mode == ft.ThemeMode.LIGHT:
            page.theme_mode = ft.ThemeMode.DARK
            page.bgcolor = "#111827"
            btn_theme.icon = ft.icons.LIGHT_MODE
            btn_theme.tooltip = "Passer en mode clair"
        else:
            page.theme_mode = ft.ThemeMode.LIGHT
            page.bgcolor = COULEUR_FOND
            btn_theme.icon = ft.icons.DARK_MODE
            btn_theme.tooltip = "Passer en mode sombre"
        page.update()

    btn_theme = ft.IconButton(
        icon=ft.icons.DARK_MODE,
        tooltip="Passer en mode sombre",
        on_click=basculer_theme,
    )

    client = APIClient()

    # Zone de contenu principal (changée selon la navigation)
    body = ft.Container(expand=True)
    app_shell = ft.Container(visible=False, expand=True)

    # ─── Navigation interne ────────────────────────────────────────────────────

    def afficher_login():
        page.controls.clear()
        page.add(
            ft.Stack([
                ft.Container(
                    content=LoginView(page, client, on_login_success=afficher_app, on_go_register=afficher_register),
                    expand=True,
                ),
                ft.Container(
                    content=btn_theme,
                    right=10, top=10,
                ),
            ], expand=True)
        )
        page.update()

    def afficher_register():
        page.controls.clear()
        page.add(
            ft.Stack([
                ft.Container(
                    content=RegisterView(page, client, on_register_success=afficher_login, on_go_login=afficher_login),
                    expand=True,
                ),
                ft.Container(
                    content=btn_theme,
                    right=10, top=10,
                ),
            ], expand=True)
        )
        page.update()

    def afficher_app():
        page.controls.clear()
        construire_app_shell()
        page.add(app_shell)
        # La route de démarrage doit correspondre au premier item du menu
        # de ce rôle (le Client n'a pas de Tableau de bord, par exemple).
        route_depart = "carte" if client.role == "CLIENT" else "dashboard"
        naviguer(route_depart)
        page.update()

    def deconnexion(e=None):
        client.logout()
        afficher_login()

    # ─── Construction du shell applicatif (menu + contenu) ──────────────────────

    nav_rail_ref = {"control": None}

    def construire_app_shell():
        user = client.user

        # Items de menu selon le rôle (RBAC)
        # Le Dashboard (stats globales, finances, occupation) n'a de sens
        # que pour Admin / Agent terrain / Secrétariat.
        # Le Client ne voit que ce qui le concerne : Carte, ses Réservations,
        # ses Concessions, ses Factures.
        if client.role == "CLIENT":
            items = [
                ft.NavigationRailDestination(icon=ft.icons.MAP_OUTLINED, selected_icon=ft.icons.MAP, label="Carte"),
                ft.NavigationRailDestination(icon=ft.icons.ASSIGNMENT_OUTLINED, selected_icon=ft.icons.ASSIGNMENT, label="Mes réservations"),
                ft.NavigationRailDestination(icon=ft.icons.DESCRIPTION_OUTLINED, selected_icon=ft.icons.DESCRIPTION, label="Mes concessions"),
                ft.NavigationRailDestination(icon=ft.icons.RECEIPT_LONG_OUTLINED, selected_icon=ft.icons.RECEIPT_LONG, label="Mes factures"),
            ]
            routes = ["carte", "reservations", "concessions", "finance"]
        elif client.role == "AGENT":
            # Agent terrain : tableau de bord + terrain + carte + réservations/concessions
            items = [
                ft.NavigationRailDestination(icon=ft.icons.DASHBOARD_OUTLINED, selected_icon=ft.icons.DASHBOARD, label="Tableau de bord"),
                ft.NavigationRailDestination(icon=ft.icons.TERRAIN_OUTLINED, selected_icon=ft.icons.TERRAIN, label="Terrain"),
                ft.NavigationRailDestination(icon=ft.icons.MAP_OUTLINED, selected_icon=ft.icons.MAP, label="Carte"),
                ft.NavigationRailDestination(icon=ft.icons.ASSIGNMENT_OUTLINED, selected_icon=ft.icons.ASSIGNMENT, label="Réservations"),
                ft.NavigationRailDestination(icon=ft.icons.DESCRIPTION_OUTLINED, selected_icon=ft.icons.DESCRIPTION, label="Concessions"),
            ]
            routes = ["dashboard", "terrain", "carte", "reservations", "concessions"]
        else:
            # Admin / Secrétariat : accès complet + gestion terrain
            items = [
                ft.NavigationRailDestination(icon=ft.icons.DASHBOARD_OUTLINED, selected_icon=ft.icons.DASHBOARD, label="Tableau de bord"),
                ft.NavigationRailDestination(icon=ft.icons.TERRAIN_OUTLINED, selected_icon=ft.icons.TERRAIN, label="Terrain"),
                ft.NavigationRailDestination(icon=ft.icons.MAP_OUTLINED, selected_icon=ft.icons.MAP, label="Carte"),
                ft.NavigationRailDestination(icon=ft.icons.ASSIGNMENT_OUTLINED, selected_icon=ft.icons.ASSIGNMENT, label="Réservations"),
                ft.NavigationRailDestination(icon=ft.icons.DESCRIPTION_OUTLINED, selected_icon=ft.icons.DESCRIPTION, label="Concessions"),
                ft.NavigationRailDestination(icon=ft.icons.RECEIPT_LONG_OUTLINED, selected_icon=ft.icons.RECEIPT_LONG, label="Finance"),
            ]
            routes = ["dashboard", "terrain", "carte", "reservations", "concessions", "finance"]

        def on_nav_change(e):
            idx = e.control.selected_index
            naviguer(routes[idx])

        nav_rail = ft.NavigationRail(
            selected_index=0,
            label_type=ft.NavigationRailLabelType.ALL,
            min_width=90,
            min_extended_width=180,
            bgcolor="white",
            destinations=items,
            on_change=on_nav_change,
        )
        nav_rail_ref["control"] = nav_rail

        header = ft.Container(
            content=ft.Row([
                ft.Row([
                    ft.Icon(ft.icons.LOCATION_CITY, color=COULEUR_PRIMAIRE, size=26),
                    ft.Text("Gestion de Cimetière", size=18, weight=ft.FontWeight.BOLD, color=COULEUR_SECONDAIRE),
                ], spacing=8),
                ft.Container(expand=True),
                ft.Row([
                    ft.Icon(ft.icons.ACCOUNT_CIRCLE, color="#6b7280"),
                    ft.Column([
                        ft.Text(user["prenom"] + " " + user["nom"], size=13, weight=ft.FontWeight.W_600),
                        ft.Text(_libelle_role(user["role"]), size=11, color="#6b7280"),
                    ], spacing=0),
                    btn_theme,
                    ft.IconButton(ft.icons.LOGOUT, tooltip="Déconnexion", on_click=deconnexion),
                ], spacing=8),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            bgcolor="white",
            padding=ft.padding.symmetric(horizontal=20, vertical=12),
            border=ft.border.only(bottom=ft.border.BorderSide(1, "#e5e7eb")),
        )

        app_shell.content = ft.Column([
            header,
            ft.Row([
                nav_rail,
                ft.VerticalDivider(width=1),
                body,
            ], expand=True),
        ], spacing=0, expand=True)
        app_shell.visible = True

    def _libelle_role(role: str) -> str:
        return {
            "ADMIN": "Administrateur",
            "AGENT": "Agent de terrain",
            "SECR": "Secrétariat",
            "CLIENT": "Client",
        }.get(role, role)

    # ─── Routeur de contenu ────────────────────────────────────────────────────

    def naviguer(route: str):
        if route == "dashboard":
            body.content = DashboardView(page, client)
        elif route == "terrain":
            body.content = TerrainView(page, client)
        elif route == "carte":
            body.content = CarteView(page, client, on_reserver_caveau=ouvrir_formulaire_reservation)
        elif route == "reservations":
            body.content = ReservationsView(page, client)
        elif route == "concessions":
            body.content = ConcessionsView(page, client)
        elif route == "finance":
            body.content = FinanceView(page, client)
        elif route == "reservation_form":
            pass  # géré par ouvrir_formulaire_reservation
        page.update()

    def ouvrir_formulaire_reservation(caveau: dict):
        # Index du menu selon le rôle :
        # CLIENT  : [Carte=0, Réservations=1, Concessions=2, Factures=3]
        # AGENT   : [Dashboard=0, Terrain=1, Carte=2, Réservations=3, Concessions=4]
        # ADMIN/SECR: [Dashboard=0, Terrain=1, Carte=2, Réservations=3, Concessions=4, Finance=5]
        if client.role == "CLIENT":
            index_carte, index_reservations = 0, 1
        else:
            index_carte, index_reservations = 2, 3

        def on_submitted(reservation):
            naviguer("reservations")
            if nav_rail_ref["control"]:
                nav_rail_ref["control"].selected_index = index_reservations
                page.update()

        def on_cancel():
            naviguer("carte")
            if nav_rail_ref["control"]:
                nav_rail_ref["control"].selected_index = index_carte
                page.update()

        body.content = ReservationFormView(page, client, caveau, on_submitted=on_submitted, on_cancel=on_cancel)
        page.update()

    # ─── Démarrage ────────────────────────────────────────────────────────────────
    afficher_login()


if __name__ == "__main__":
    ft.app(target=main)
