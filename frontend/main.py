import os
import flet as ft

from api_client import APIClient
from config import construire_theme, couleurs

from views.login_view import LoginView
from views.register_view import RegisterView
from views.dashboard_view import DashboardView
from views.terrain_view import TerrainView
from views.carte_view import CarteView
from views.reservation_form_view import ReservationFormView
from views.reservations_view import ReservationsView
from views.concessions_view import ConcessionsView
from views.finance_view import FinanceView
from views.utilisateurs_view import UtilisateursView

from responsive import SEUIL_MOBILE


def main(page: ft.Page):
    page.title = "Gestion de Cimetière"

    # ─── Icône / favicon ──────────────────────────────────────────────────────
    page.window.icon = "icone.ico"
    page.favicon = "icone.ico"

    page.theme_mode = ft.ThemeMode.LIGHT
    page.window.width = 1200
    page.window.height = 800
    page.window.min_width = 360
    page.padding = 0

    # ─── Thème premium — or antique / anthracite, clair & sombre ────────────────
    page.theme = construire_theme("light")
    page.dark_theme = construire_theme("dark")
    page.bgcolor = couleurs(page)["fond"]

    client = APIClient()

    body = ft.Container(expand=True)
    app_shell = ft.Container(visible=False, expand=True)
    etat_nav = {"route_index": 0}
    route_actuelle = {"nom": None}

    # ─── Bascule de thème ───────────────────────────────────────────────────────
    def basculer_theme(e):
        if page.theme_mode == ft.ThemeMode.LIGHT:
            page.theme_mode = ft.ThemeMode.DARK
            btn_theme.icon = ft.icons.LIGHT_MODE
            btn_theme.tooltip = "Passer en mode clair"
        else:
            page.theme_mode = ft.ThemeMode.LIGHT
            btn_theme.icon = ft.icons.DARK_MODE
            btn_theme.tooltip = "Passer en mode sombre"
        page.bgcolor = couleurs(page)["fond"]

        # Garde-fou : si la session a expiré (client.user devenu None) alors
        # que le shell est encore affiché, on ne tente pas de reconstruire
        # l'en-tête (qui a besoin de client.user) — on renvoie proprement
        # vers l'écran de connexion plutôt que de planter.
        if app_shell.visible and client.user is None:
            afficher_login()
            return

        # Les composants "premium" figent la couleur au moment de leur
        # construction (et non via des tokens de thème Flet en direct) afin
        # de garder un contrôle fin sur la palette. On reconstruit donc le
        # shell + la vue courante pour qu'ils reprennent la nouvelle palette.
        if app_shell.visible:
            construire_app_shell()
            if route_actuelle["nom"]:
                naviguer(route_actuelle["nom"])
        else:
            # Écran de login/inscription encore affiché : on le redessine.
            if route_actuelle["nom"] == "login":
                afficher_login()
            elif route_actuelle["nom"] == "register":
                afficher_register()
        page.update()

    btn_theme = ft.IconButton(
        icon=ft.icons.DARK_MODE,
        tooltip="Passer en mode sombre",
        on_click=basculer_theme,
    )

    # ─── Navigation interne ────────────────────────────────────────────────────

    def afficher_login():
        route_actuelle["nom"] = "login"
        page.controls.clear()
        page.add(
            ft.Stack([
                ft.Container(
                    content=LoginView(page, client, on_login_success=afficher_app, on_go_register=afficher_register),
                    expand=True,
                ),
                ft.Container(content=btn_theme, right=10, top=10),
            ], expand=True)
        )
        page.update()

    def afficher_register():
        route_actuelle["nom"] = "register"
        page.controls.clear()
        page.add(
            ft.Stack([
                ft.Container(
                    content=RegisterView(page, client, on_register_success=afficher_login, on_go_login=afficher_login),
                    expand=True,
                ),
                ft.Container(content=btn_theme, right=10, top=10),
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
        afficher_login()

    # ─── Construction du shell applicatif (menu + contenu) ──────────────────────

    nav_rail_ref = {"rail": None, "bar": None, "routes": []}

    def construire_app_shell():
        if client.user is None:
            # Session expirée / utilisateur non chargé : impossible de
            # construire l'en-tête (avatar, nom...). On évite le crash en
            # renvoyant proprement vers l'écran de connexion.
            afficher_login()
            return

        t = couleurs(page)
        user = client.user
        est_mobile = page.width is not None and page.width < SEUIL_MOBILE

        if client.role == "CLIENT":
            items = [
                ("carte", ft.icons.MAP_OUTLINED, ft.icons.MAP, "Carte"),
                ("reservations", ft.icons.ASSIGNMENT_OUTLINED, ft.icons.ASSIGNMENT, "Mes réservations"),
                ("concessions", ft.icons.DESCRIPTION_OUTLINED, ft.icons.DESCRIPTION, "Mes concessions"),
                ("finance", ft.icons.RECEIPT_LONG_OUTLINED, ft.icons.RECEIPT_LONG, "Mes factures"),
            ]
        elif client.role == "AGENT":
            items = [
                ("dashboard", ft.icons.DASHBOARD_OUTLINED, ft.icons.DASHBOARD, "Tableau de bord"),
                ("terrain", ft.icons.TERRAIN_OUTLINED, ft.icons.TERRAIN, "Terrain"),
                ("carte", ft.icons.MAP_OUTLINED, ft.icons.MAP, "Carte"),
                ("reservations", ft.icons.ASSIGNMENT_OUTLINED, ft.icons.ASSIGNMENT, "Réservations"),
                ("concessions", ft.icons.DESCRIPTION_OUTLINED, ft.icons.DESCRIPTION, "Concessions"),
            ]
        else:
            items = [
                ("dashboard", ft.icons.DASHBOARD_OUTLINED, ft.icons.DASHBOARD, "Tableau de bord"),
                ("terrain", ft.icons.TERRAIN_OUTLINED, ft.icons.TERRAIN, "Terrain"),
                ("carte", ft.icons.MAP_OUTLINED, ft.icons.MAP, "Carte"),
                ("reservations", ft.icons.ASSIGNMENT_OUTLINED, ft.icons.ASSIGNMENT, "Réservations"),
                ("concessions", ft.icons.DESCRIPTION_OUTLINED, ft.icons.DESCRIPTION, "Concessions"),
                ("finance", ft.icons.RECEIPT_LONG_OUTLINED, ft.icons.RECEIPT_LONG, "Finance"),
                ("utilisateurs", ft.icons.PEOPLE_OUTLINED, ft.icons.PEOPLE, "Utilisateurs"),
            ]

        routes = [it[0] for it in items]
        nav_rail_ref["routes"] = routes

        def on_nav_change(e):
            idx = e.control.selected_index
            etat_nav["route_index"] = idx
            naviguer(routes[idx])
            if isinstance(e.control, ft.NavigationDrawer):
                page.close(e.control)

        index_selectionne = min(etat_nav["route_index"], len(routes) - 1)

        # Style de sélection premium : pastille or translucide autour de
        # l'icône active, cohérent en clair comme en sombre.
        indicateur = ft.colors.with_opacity(0.16, t["accent"])

        nav_rail = ft.NavigationRail(
            selected_index=index_selectionne,
            label_type=ft.NavigationRailLabelType.ALL,
            min_width=90,
            min_extended_width=180,
            bgcolor=t["surface"],
            indicator_color=indicateur,
            destinations=[
                ft.NavigationRailDestination(icon=icon, selected_icon=sel_icon, label=label)
                for (_, icon, sel_icon, label) in items
            ],
            on_change=on_nav_change,
        )

        nav_bar = ft.NavigationBar(
            selected_index=index_selectionne,
            bgcolor=t["surface"],
            indicator_color=indicateur,
            destinations=[
                ft.NavigationBarDestination(icon=icon, selected_icon=sel_icon, label=label)
                for (_, icon, sel_icon, label) in items
            ],
            on_change=on_nav_change,
        )

        # ── Menu hamburger (mobile) — remplace la barre du bas, qui devenait
        #    illisible / incomplète dès que le rôle a plus de 3-4 destinations
        #    (ex. Admin : 7 items). Un tiroir latéral scrollable n'a pas cette
        #    limite et affiche toujours le libellé complet de chaque item.
        drawer = ft.NavigationDrawer(
            selected_index=index_selectionne,
            bgcolor=t["surface"],
            indicator_color=ft.colors.with_opacity(0.16, t["accent"]),
            controls=[
                ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.icons.LOCATION_CITY, color=t["accent"], size=22),
                        ft.Text(
                            "Gestion de Cimetière", size=15, weight=ft.FontWeight.BOLD,
                            font_family="Playfair Display, Georgia, serif", color=t["texte"],
                        ),
                    ], spacing=8),
                    padding=ft.padding.only(left=16, top=16, bottom=8),
                ),
                ft.Divider(color=t["bordure"]),
                *[
                    ft.NavigationDrawerDestination(icon=icon, selected_icon=sel_icon, label=label)
                    for (_, icon, sel_icon, label) in items
                ],
            ],
            on_change=on_nav_change,
        )

        def ouvrir_menu(e):
            page.open(drawer)

        nav_rail_ref["rail"] = nav_rail
        nav_rail_ref["bar"] = nav_bar
        nav_rail_ref["drawer"] = drawer

        header = ft.Container(
            content=ft.Row([
                ft.Row([
                    *([ft.IconButton(ft.icons.MENU, on_click=ouvrir_menu, tooltip="Menu")] if est_mobile else []),
                    ft.Icon(ft.icons.LOCATION_CITY, color=t["accent"], size=24),
                    ft.Text(
                        "Gestion de Cimetière",
                        size=17,
                        weight=ft.FontWeight.BOLD,
                        font_family="Playfair Display, Georgia, serif",
                        color=t["texte"],
                        visible=not est_mobile,
                    ),
                ], spacing=4 if est_mobile else 8),
                ft.Container(expand=True),
                ft.Row([
                    ft.CircleAvatar(
                        content=ft.Text((user["prenom"][:1] + user["nom"][:1]).upper(), size=13, weight=ft.FontWeight.BOLD, color=t["on_accent"] if "on_accent" in t else "#FFFFFF"),
                        bgcolor=t["accent"],
                        radius=16,
                    ),
                    ft.Column([
                        ft.Text(user["prenom"] + " " + user["nom"], size=13, weight=ft.FontWeight.W_600, color=t["texte"]),
                        ft.Text(_libelle_role(user["role"]), size=11, color=t["texte_att"]),
                    ], spacing=0, visible=not est_mobile),
                    btn_theme,
                    ft.IconButton(ft.icons.LOGOUT, tooltip="Déconnexion", on_click=deconnexion),
                ], spacing=10),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            bgcolor=t["surface"],
            padding=ft.padding.symmetric(horizontal=20 if not est_mobile else 12, vertical=12),
            border=ft.border.only(bottom=ft.border.BorderSide(1, t["bordure"])),
        )

        if est_mobile:
            # Le tiroir (drawer) n'est PAS un enfant de l'arbre visuel : Flet
            # le gère via page.drawer / page.open(drawer) (cf. ouvrir_menu).
            app_shell.content = ft.Column(
                [
                    header,
                    ft.Container(content=body, expand=True, bgcolor=t["fond"]),
                ],
                spacing=0,
                expand=True,
            )
        else:
            app_shell.content = ft.Column(
                [
                    header,
                    ft.Row([
                        nav_rail,
                        ft.VerticalDivider(width=1, color=t["bordure"]),
                        ft.Container(content=body, expand=True, bgcolor=t["fond"]),
                    ], expand=True, spacing=0),
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
        route_actuelle["nom"] = route
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
        elif route == "utilisateurs":
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

        route_actuelle["nom"] = "reservation_form"
        body.content = ReservationFormView(page, client, caveau, on_submitted=on_submitted, on_cancel=on_cancel)
        page.update()

    # ─── Démarrage ────────────────────────────────────────────────────────────────
    etat_resize["etait_mobile"] = page.width is not None and page.width < SEUIL_MOBILE
    afficher_login()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8550))
    ft.app(target=main, assets_dir="assets", view=ft.AppView.WEB_BROWSER, port=port)
