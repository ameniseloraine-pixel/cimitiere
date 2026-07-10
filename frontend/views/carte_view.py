"""
Vue Cartographie — Carte interactive des caveaux
Représentation en grille colorée par statut (Vert/Orange/Rouge/Gris)
Cliquer sur un caveau ouvre le détail + actions (réserver / changer statut)
NOUVEAU : bouton "Vue GPS" — WebView intégré sur mobile/web,
          ouverture navigateur sur desktop (WebView non supporté sur desktop Flet)
"""

import os
import tempfile
import webbrowser
import urllib.parse
import flet as ft
from collections import defaultdict

from api_client import APIError
from components.widgets import badge_statut, afficher_snackbar, chargement, etat_vide, bouton_principal
from config import COULEURS_STATUT, LIBELLES_STATUT, COULEUR_PRIMAIRE


def CarteView(page: ft.Page, client, on_reserver_caveau):
    """
    on_reserver_caveau(caveau: dict) : callback déclenché quand le client
    clique sur "Réserver" pour un caveau disponible.
    """

    content_area = ft.Container(content=chargement("Chargement de la carte..."), expand=True)
    filtre_zone = ft.Dropdown(label="Zone", width=180, options=[], on_change=lambda e: charger_carte())
    filtre_statut = ft.Dropdown(
        label="Statut",
        width=200,
        options=[ft.dropdown.Option("", "Tous les statuts")] + [
            ft.dropdown.Option(k, v) for k, v in LIBELLES_STATUT.items()
        ],
        on_change=lambda e: charger_carte(),
    )

    mode_affichage = {"valeur": "grille"}  # "grille" ou "gps"

    # NOUVEAU : détecte si on est sur mobile/web (WebView OK) ou desktop (WebView KO)
    def _webview_supporte() -> bool:
        return page.web or page.platform in (ft.PagePlatform.ANDROID, ft.PagePlatform.IOS)

    legende = ft.Row([
        ft.Row([
            ft.Container(width=14, height=14, bgcolor=couleur, border_radius=4),
            ft.Text(LIBELLES_STATUT[statut], size=12, color="#6b7280"),
        ], spacing=4)
        for statut, couleur in COULEURS_STATUT.items()
        if statut != "MAINT"
    ], spacing=16, wrap=True)

    def ouvrir_detail_caveau(caveau: dict):
        statut = caveau["statut"]
        actions = []

        if statut == "DISPO" and not client.is_admin and not client.can_edit_map:
            def reserver(e):
                page.close(dlg)
                on_reserver_caveau(caveau)
            actions.append(bouton_principal("Réserver ce caveau", on_click=reserver, icone=ft.icons.BOOKMARK_ADD))

        if client.can_edit_map:
            nouveau_statut_dd = ft.Dropdown(
                label="Nouveau statut",
                value=statut,
                options=[ft.dropdown.Option(k, v) for k, v in LIBELLES_STATUT.items()],
                width=250,
            )
            raison_field = ft.TextField(label="Raison du changement", width=250, multiline=True, min_lines=2)

            def changer_statut(e):
                try:
                    client.changer_statut_caveau(caveau["id"], nouveau_statut_dd.value, raison_field.value or "")
                    afficher_snackbar(page, f"Statut du caveau {caveau['numero']} mis à jour.", succes=True)
                    page.close(dlg)
                    charger_carte()
                except APIError as err:
                    afficher_snackbar(page, err.detail, succes=False)

            actions.append(ft.Column([
                ft.Divider(),
                ft.Text("Modifier le statut (Agent/Admin)", size=13, weight=ft.FontWeight.W_600),
                nouveau_statut_dd,
                raison_field,
                bouton_principal("Enregistrer", on_click=changer_statut, icone=ft.icons.SAVE),
            ], spacing=10))

        dlg = ft.AlertDialog(
            title=ft.Row([
                ft.Icon(ft.icons.PLACE, color=COULEURS_STATUT.get(statut, "#9ca3af")),
                ft.Text(f"Caveau {caveau['numero']}"),
            ]),
            content=ft.Container(
                content=ft.Column([
                    ft.Row([ft.Text("Référence :", weight=ft.FontWeight.W_600), ft.Text(caveau["reference"])]),
                    ft.Row([ft.Text("Zone :", weight=ft.FontWeight.W_600), ft.Text(caveau["zone_code"])]),
                    ft.Row([ft.Text("Bloc :", weight=ft.FontWeight.W_600), ft.Text(caveau["bloc_code"])]),
                    ft.Row([ft.Text("Statut :", weight=ft.FontWeight.W_600), badge_statut(statut)]),
                    *actions,
                ], spacing=10, tight=True),
                width=320,
            ),
            actions=[ft.TextButton("Fermer", on_click=lambda e: page.close(dlg))],
        )
        page.open(dlg)

    def construire_grille(caveaux: list) -> ft.Control:
        if not caveaux:
            return etat_vide("Aucun caveau trouvé pour ces filtres.", ft.icons.MAP_OUTLINED)

        zones = defaultdict(lambda: defaultdict(list))
        for c in caveaux:
            zones[c["zone_code"]][c["bloc_code"]].append(c)

        sections = []
        for zone_code, blocs in sorted(zones.items()):
            bloc_sections = []
            for bloc_code, caveaux_bloc in sorted(blocs.items()):
                caveaux_bloc.sort(key=lambda c: c["numero"])

                tuiles = [
                    ft.Container(
                        width=36, height=36,
                        bgcolor=c["couleur"],
                        border_radius=6,
                        alignment=ft.alignment.center,
                        tooltip=f"{c['numero']} — {LIBELLES_STATUT.get(c['statut'], c['statut'])}",
                        content=ft.Text(
                            c["numero"].split("-")[-1] if "-" in c["numero"] else c["numero"][-2:],
                            size=9, color="white", weight=ft.FontWeight.BOLD,
                        ),
                        ink=True,
                        on_click=lambda e, cav=c: ouvrir_detail_caveau(cav),
                    )
                    for c in caveaux_bloc
                ]

                bloc_sections.append(ft.Container(
                    content=ft.Column([
                        ft.Text(f"Bloc {bloc_code}", size=13, weight=ft.FontWeight.W_600, color="#374151"),
                        ft.Row(tuiles, wrap=True, spacing=4, run_spacing=4),
                    ], spacing=6),
                    bgcolor="#f8fafc",
                    padding=12,
                    border_radius=8,
                    border=ft.border.all(1, "#e5e7eb"),
                ))

            sections.append(ft.Column([
                ft.Text(f"Zone {zone_code}", size=16, weight=ft.FontWeight.BOLD, color=COULEUR_PRIMAIRE),
                ft.Row(bloc_sections, wrap=True, spacing=12, run_spacing=12),
            ], spacing=10))

        return ft.Column(sections, spacing=24, scroll=ft.ScrollMode.AUTO, expand=True)

    def _generer_html_carte(caveaux_geo: list) -> str:
        lat_centre = caveaux_geo[0]["latitude"]
        lng_centre = caveaux_geo[0]["longitude"]

        markers_js = ""
        for c in caveaux_geo:
            couleur = c["couleur"]
            popup = f"{c['reference']} — {LIBELLES_STATUT.get(c['statut'], c['statut'])}".replace('"', "'")
            markers_js += f"""
            L.circleMarker([{c['latitude']}, {c['longitude']}], {{
                radius: 9, color: "{couleur}", fillColor: "{couleur}", fillOpacity: 0.9, weight: 2
            }}).addTo(map).bindPopup("{popup}");
            """

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
          <link rel="stylesheet" href="https://unpkg.com/leaflet/dist/leaflet.css"/>
          <script src="https://unpkg.com/leaflet/dist/leaflet.js"></script>
          <style>#map {{ height: 100vh; width: 100%; }} body {{ margin: 0; }}</style>
        </head>
        <body>
          <div id="map"></div>
          <script>
            var map = L.map('map').setView([{lat_centre}, {lng_centre}], 17);
            L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png').addTo(map);
            {markers_js}
          </script>
        </body>
        </html>
        """

    # NOUVEAU : carte GPS intégrée (mobile / web)
    def construire_carte_gps_inline(caveaux: list) -> ft.Control:
        caveaux_geo = [c for c in caveaux if c.get("latitude") is not None and c.get("longitude") is not None]
        if not caveaux_geo:
            return etat_vide("Aucun caveau ne possède de coordonnées GPS pour le moment.", ft.icons.MAP_OUTLINED)

        html_content = _generer_html_carte(caveaux_geo)
        data_url = "data:text/html;charset=utf-8," + urllib.parse.quote(html_content)

        return ft.Container(
            content=ft.WebView(url=data_url, expand=True),
            expand=True,
            border_radius=8,
            border=ft.border.all(1, "#e5e7eb"),
        )

    # NOUVEAU : carte GPS ouverte dans le navigateur (desktop uniquement)
    def ouvrir_carte_gps_navigateur(caveaux: list):
        caveaux_geo = [c for c in caveaux if c.get("latitude") is not None and c.get("longitude") is not None]
        if not caveaux_geo:
            afficher_snackbar(page, "Aucun caveau ne possède de coordonnées GPS pour le moment.", succes=False)
            return

        html_content = _generer_html_carte(caveaux_geo)
        chemin_fichier = os.path.join(tempfile.gettempdir(), "carte_cimetiere.html")
        with open(chemin_fichier, "w", encoding="utf-8") as f:
            f.write(html_content)
        webbrowser.open(f"file:///{chemin_fichier}")

    def charger_carte():
        content_area.content = chargement("Chargement de la carte...")
        page.update()

        try:
            caveaux = client.liste_caveaux(
                statut=filtre_statut.value or None,
                zone_code=filtre_zone.value or None,
            )

            if not filtre_zone.options:
                zones_uniques = sorted(set(c["zone_code"] for c in caveaux))
                filtre_zone.options = [ft.dropdown.Option("", "Toutes les zones")] + [
                    ft.dropdown.Option(z, f"Zone {z}") for z in zones_uniques
                ]

            if mode_affichage["valeur"] == "gps" and _webview_supporte():
                content_area.content = construire_carte_gps_inline(caveaux)
            else:
                content_area.content = construire_grille(caveaux)
        except APIError as err:
            content_area.content = etat_vide(f"Erreur : {err.detail}", ft.icons.ERROR_OUTLINE)

        page.update()

    # NOUVEAU : clic sur le bouton "Vue GPS"
    def basculer_vue(e):
        if _webview_supporte():
            # Mobile/Web : bascule inline entre grille et carte GPS
            mode_affichage["valeur"] = "gps" if mode_affichage["valeur"] == "grille" else "grille"
            btn_bascule.text = "Vue Blocs" if mode_affichage["valeur"] == "gps" else "Vue GPS"
            btn_bascule.icon = ft.icons.GRID_VIEW if mode_affichage["valeur"] == "gps" else ft.icons.MAP
            charger_carte()
        else:
            # Desktop : ouvre la carte dans le navigateur (WebView non supporté)
            try:
                caveaux = client.liste_caveaux(
                    statut=filtre_statut.value or None,
                    zone_code=filtre_zone.value or None,
                )
                ouvrir_carte_gps_navigateur(caveaux)
            except APIError as err:
                afficher_snackbar(page, err.detail, succes=False)

    btn_bascule = ft.OutlinedButton(
        text="Vue GPS",
        icon=ft.icons.MAP,
        on_click=basculer_vue,
    )

    charger_carte()

    return ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Text("Carte interactive du cimetière", size=20, weight=ft.FontWeight.BOLD),
                ft.Container(expand=True),
                btn_bascule,
                filtre_zone,
                filtre_statut,
                ft.IconButton(ft.icons.REFRESH, on_click=lambda e: charger_carte(), tooltip="Actualiser"),
            ], alignment=ft.MainAxisAlignment.START),
            ft.Container(
                content=legende,
                padding=ft.padding.symmetric(vertical=8),
            ),
            ft.Divider(),
            content_area,
        ], spacing=10, expand=True),
        padding=20,
        expand=True,
    )