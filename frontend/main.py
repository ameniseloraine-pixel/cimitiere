import os
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
from views.utilisateurs_view import UtilisateursView  # NOUVEAU

# Seuil (en pixels) sous lequel on bascule vers le layout mobile
SEUIL_MOBILE = 700


def main(page: ft.Page):
    page.title = "Gestion de Cimetière"

    # ─── Icône / favicon ──────────────────────────────────────────────────────
    # Le chemin est relatif au dossier "assets" déclaré dans ft.app(assets_dir=...)
    # tout en bas du fichier. Ne PAS préfixer par "assets/".
    page.window.icon = "icone.ico"   # icône de la fenêtre (mode desktop)
    page.favicon = "icone.ico"       # icône de l'onglet navigateur (mode --web)

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
            page.bgcolor = "#161a23"
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

    # Garde l'état de navigation courant pour pouvoir reconstruire le shell
    # (au resize) sans perdre la position sélectionnée.
    etat_nav = {"route_index": 0}

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
        etat_nav["route_index"] = 0
        naviguer(route_depart)
        page.update()

    def deconnexion(e=None):
        client.logout()
        app_shell.visible = False
        afficher_login()

    # ─── Construction du shell applicatif (menu + contenu) ──────────────────────

    nav_rail_ref = {"rail": None, "bar": None, "routes": []}

    def construire_app_shell():
        user = client.user
        if user is None:
            # Garde-fou : ne doit normalement jamais arriver, mais si l'état
            # devient incohérent (session expirée, etc.), on renvoie proprement
            # vers le login au lieu de planter sur user["prenom"].
            app_shell.visible = False
            afficher_login()
            return
        est_mobile = page.width is not None and page.width < SEUIL_MOBILE

        # Items de menu selon le rôle (RBAC)
        # Le Dashboard (stats globales, finances, occupation) n'a de sens
        # que pour Admin / Agent terrain / Secrétariat.
        # Le Client ne voit que ce qui le concerne : Carte, ses Réservations,
        # ses Concessions, ses Factures.
        if client.role == "CLIENT":
            items = [
                ("carte", ft.icons.MAP_OUTLINED, ft.icons.MAP, "Carte"),
                ("reservations", ft.icons.ASSIGNMENT_OUTLINED, ft.icons.ASSIGNMENT, "Mes réservations"),
                ("concessions", ft.icons.DESCRIPTION_OUTLINED, ft.icons.DESCRIPTION, "Mes concessions"),
                ("finance", ft.icons.RECEIPT_LONG_OUTLINED, ft.icons.RECEIPT_LONG, "Mes factures"),
            ]
        elif client.role == "AGENT":
            # Agent terrain : tableau de bord + terrain + carte + réservations/concessions
            items = [
                ("dashboard", ft.icons.DASHBOARD_OUTLINED, ft.icons.DASHBOARD, "Tableau de bord"),
                ("terrain", ft.icons.TERRAIN_OUTLINED, ft.icons.TERRAIN, "Terrain"),
                ("carte", ft.icons.MAP_OUTLINED, ft.icons.MAP, "Carte"),
                ("reservations", ft.icons.ASSIGNMENT_OUTLINED, ft.icons.ASSIGNMENT, "Réservations"),
                ("concessions", ft.icons.DESCRIPTION_OUTLINED, ft.icons.DESCRIPTION, "Concessions"),
            ]
        else:
            # Admin / Secrétariat : accès complet + gestion terrain + utilisateurs
            items = [
                ("dashboard", ft.icons.DASHBOARD_OUTLINED, ft.icons.DASHBOARD, "Tableau de bord"),
                ("terrain", ft.icons.TERRAIN_OUTLINED, ft.icons.TERRAIN, "Terrain"),
                ("carte", ft.icons.MAP_OUTLINED, ft.icons.MAP, "Carte"),
                ("reservations", ft.icons.ASSIGNMENT_OUTLINED, ft.icons.ASSIGNMENT, "Réservations"),
                ("concessions", ft.icons.DESCRIPTION_OUTLINED, ft.icons.DESCRIPTION, "Concessions"),
                ("finance", ft.icons.RECEIPT_LONG_OUTLINED, ft.icons.RECEIPT_LONG, "Finance"),
                ("utilisateurs", ft.icons.PEOPLE_OUTLINED, ft.icons.PEOPLE, "Utilisateurs"),  # NOUVEAU
            ]

        routes = [it[0] for it in items]
        nav_rail_ref["routes"] = routes

        def on_nav_change(e):
            idx = e.control.selected_index
            etat_nav["route_index"] = idx
            naviguer(routes[idx])

        # Index sélectionné borné (au cas où le nombre d'items change selon le rôle)
        index_selectionne = min(etat_nav["route_index"], len(routes) - 1)

        # ── Layout large : NavigationRail sur le côté ──────────────────────────
        nav_rail = ft.NavigationRail(
            selected_index=index_selectionne,
            label_type=ft.NavigationRailLabelType.ALL,
            min_width=90,
            min_extended_width=180,
            bgcolor=ft.colors.SURFACE,
            destinations=[
                ft.NavigationRailDestination(icon=icon, selected_icon=sel_icon, label=label)
                for (_, icon, sel_icon, label) in items
            ],
            on_change=on_nav_change,
        )

        # ── Layout étroit (mobile) : NavigationBar en bas ──────────────────────
        nav_bar = ft.NavigationBar(
            selected_index=index_selectionne,
            destinations=[
                ft.NavigationBarDestination(icon=icon, selected_icon=sel_icon, label=label)
                for (_, icon, sel_icon, label) in items
            ],
            on_change=on_nav_change,
        )

        nav_rail_ref["rail"] = nav_rail
        nav_rail_ref["bar"] = nav_bar

        # ── Menu burger (mobile) : tiroir avec libellés toujours visibles ──────
        def on_drawer_change(e):
            idx = e.control.selected_index
            if idx is None:
                return
            etat_nav["route_index"] = idx
            naviguer(routes[idx])
            page.update()

        menu_drawer = ft.NavigationDrawer(
            selected_index=index_selectionne,
            on_change=on_drawer_change,
            controls=[
                ft.Container(
                    padding=ft.padding.symmetric(horizontal=16, vertical=16),
                    content=ft.Row([
                        ft.Icon(ft.icons.ACCOUNT_CIRCLE, color="#6b7280", size=32),
                        ft.Column([
                            ft.Text(user["prenom"] + " " + user["nom"], size=14, weight=ft.FontWeight.W_600),
                            ft.Text(_libelle_role(user["role"]), size=12, color="#6b7280"),
                        ], spacing=0),
                    ], spacing=10),
                ),
                ft.Divider(height=1),
                *[
                    ft.NavigationDrawerDestination(icon=icon, selected_icon=sel_icon, label=label)
                    for (_, icon, sel_icon, label) in items
                ],
            ],
        )
        page.drawer = menu_drawer

        def ouvrir_menu(e=None):
            page.drawer.open = True
            page.update()

        header = ft.Container(
            content=ft.Row([
                ft.Row([
                    # Bouton burger : uniquement utile en mobile (le rail
                    # latéral suffit sur desktop, donc il reste caché).
                    ft.IconButton(
                        icon=ft.icons.MENU,
                        tooltip="Menu",
                        on_click=ouvrir_menu,
                        visible=est_mobile,
                    ) if est_mobile else ft.Container(width=0),
                    ft.Icon(ft.icons.LOCATION_CITY, color=COULEUR_PRIMAIRE, size=26),
                    ft.Text(
                        "Gestion de Cimetière" if not est_mobile else "Cimetière",
                        size=18 if not est_mobile else 15,
                        weight=ft.FontWeight.BOLD,
                        color=COULEUR_SECONDAIRE,
                    ),
                ], spacing=8),
                ft.Container(expand=True),
                ft.Row([
                    ft.Icon(ft.icons.ACCOUNT_CIRCLE, color="#6b7280", visible=not est_mobile),
                    ft.Column([
                        ft.Text(user["prenom"] + " " + user["nom"], size=13, weight=ft.FontWeight.W_600),
                        ft.Text(_libelle_role(user["role"]), size=11, color="#6b7280"),
                    ], spacing=0, visible=not est_mobile),
                    btn_theme,
                    ft.IconButton(ft.icons.LOGOUT, tooltip="Déconnexion", on_click=deconnexion),
                ], spacing=8),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            bgcolor=ft.colors.SURFACE,
            padding=ft.padding.symmetric(horizontal=20 if not est_mobile else 12, vertical=12),
            border=ft.border.only(bottom=ft.border.BorderSide(1, "#e5e7eb")),
        )

        if est_mobile:
            # Mobile : pas de rail latéral, contenu en pleine largeur.
            # La navigation se fait via le menu burger (tiroir), donc pas
            # besoin de dupliquer les mêmes liens dans une barre du bas.
            app_shell.content = ft.Column(
                [
                    header,
                    ft.Container(content=body, expand=True),
                ],
                spacing=0,
                expand=True,
            )
        else:
            # Bureau / tablette large : rail latéral classique.
            app_shell.content = ft.Column(
                [
                    header,
                    ft.Row([
                        nav_rail,
                        ft.VerticalDivider(width=1),
                        ft.Container(content=body, expand=True),
                    ], expand=True),
                ],
                spacing=0,
                expand=True,
            )

        app_shell.visible = True

    def _libelle_role(role: str) -> str:
        return {
            "ADMIN": "Administrateur",
            "AGENT": "Agent de terrain",
            "SECR": "Secrétariat",
            "CLIENT": "Client",
        }.get(role, role)

    # ─── Redimensionnement : reconstruit le shell si on franchit le seuil ───────

    etat_resize = {"etait_mobile": None}

    def on_resize(e):
        if not app_shell.visible:
            return
        est_mobile_maintenant = page.width is not None and page.width < SEUIL_MOBILE
        # On ne reconstruit que si on a effectivement changé de mode,
        # pour éviter de re-render à chaque pixel de redimensionnement.
        if est_mobile_maintenant != etat_resize["etait_mobile"]:
            etat_resize["etait_mobile"] = est_mobile_maintenant
            route_courante = nav_rail_ref["routes"][etat_nav["route_index"]] if nav_rail_ref["routes"] else None
            construire_app_shell()
            if route_courante:
                naviguer(route_courante)
            page.update()

    page.on_resize = on_resize

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
        elif route == "utilisateurs":  # NOUVEAU
            body.content = UtilisateursView(page, client)
        elif route == "reservation_form":
            pass  # géré par ouvrir_formulaire_reservation
        page.update()

    def ouvrir_formulaire_reservation(caveau: dict):
        routes = nav_rail_ref["routes"]
        index_carte = routes.index("carte") if "carte" in routes else 0
        index_reservations = routes.index("reservations") if "reservations" in routes else 0

        def _selectionner(index):
            etat_nav["route_index"] = index
            if nav_rail_ref["rail"]:
                nav_rail_ref["rail"].selected_index = index
            if nav_rail_ref["bar"]:
                nav_rail_ref["bar"].selected_index = index

        def on_submitted(reservation):
            naviguer("reservations")
            _selectionner(index_reservations)
            page.update()

        def on_cancel():
            naviguer("carte")
            _selectionner(index_carte)
            page.update()

        body.content = ReservationFormView(page, client, caveau, on_submitted=on_submitted, on_cancel=on_cancel)
        page.update()

    # ─── Démarrage ────────────────────────────────────────────────────────────────
    etat_resize["etait_mobile"] = page.width is not None and page.width < SEUIL_MOBILE
    afficher_login()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8550))
    ft.app(target=main, assets_dir="assets", view=ft.AppView.WEB_BROWSER, port=port)
