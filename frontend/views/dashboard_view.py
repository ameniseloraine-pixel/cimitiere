"""
Vue Dashboard — Tableau de bord
Taux d'occupation, jauge de saturation, revenus, alertes
"""

import flet as ft

from api_client import APIError
from components.widgets import carte_stat, chargement, etat_vide
from config import COULEUR_PRIMAIRE


def DashboardView(page: ft.Page, client):
    content_area = ft.Container(content=chargement("Chargement du tableau de bord..."), expand=True)

    def jauge_saturation(taux: float) -> ft.Container:
        if taux >= 90:
            couleur = "#ef4444"
        elif taux >= 70:
            couleur = "#f97316"
        else:
            couleur = "#22c55e"

        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text("Jauge de saturation globale", size=14, weight=ft.FontWeight.W_600),
                    ft.Text(f"{taux}%", size=14, weight=ft.FontWeight.BOLD, color=couleur),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.ProgressBar(value=taux / 100, color=couleur, bgcolor="#e5e7eb", height=10, border_radius=6),
                ft.Text(
                    "⚠️ Seuil critique atteint — anticiper l'extension des espaces" if taux >= 90
                    else "Niveau de saturation sous contrôle",
                    size=11, color="#6b7280",
                ),
            ], spacing=8),
            bgcolor="white", padding=16, border_radius=12, border=ft.border.all(1, "#e5e7eb"),
        )

    def tableau_blocs(par_bloc: list) -> ft.Container:
        if not par_bloc:
            return ft.Container()

        rows = [
            ft.DataRow(cells=[
                ft.DataCell(ft.Text(b["bloc"])),
                ft.DataCell(ft.Text(str(b["total"]))),
                ft.DataCell(ft.Text(str(b["occupes"]))),
                ft.DataCell(ft.Row([
                    ft.ProgressBar(
                        value=b["taux_occupation_pct"] / 100, width=80, height=8,
                        color="#ef4444" if b["alerte_saturation"] else "#22c55e",
                        bgcolor="#e5e7eb", border_radius=4,
                    ),
                    ft.Text(f"{b['taux_occupation_pct']}%", size=12),
                ], spacing=8)),
                ft.DataCell(ft.Icon(ft.icons.WARNING, color="#f97316", size=16) if b["alerte_saturation"] else ft.Text("")),
            ])
            for b in par_bloc
        ]

        return ft.Container(
            content=ft.Column([
                ft.Text("Occupation par bloc", size=15, weight=ft.FontWeight.W_600),
                ft.DataTable(
                    columns=[
                        ft.DataColumn(ft.Text("Bloc")),
                        ft.DataColumn(ft.Text("Total")),
                        ft.DataColumn(ft.Text("Occupés")),
                        ft.DataColumn(ft.Text("Taux")),
                        ft.DataColumn(ft.Text("Alerte")),
                    ],
                    rows=rows,
                ),
            ], spacing=12, scroll=ft.ScrollMode.AUTO),
            bgcolor="white", padding=16, border_radius=12, border=ft.border.all(1, "#e5e7eb"),
        )

    def charger():
        content_area.content = chargement("Chargement du tableau de bord...")
        page.update()

        try:
            data = client.dashboard()
            occ = data["occupation"]

            cartes_stats = ft.ResponsiveRow([
                ft.Container(carte_stat("Caveaux totaux", occ["total"], ft.icons.GRID_VIEW, COULEUR_PRIMAIRE), col={"sm": 6, "md": 3}),
                ft.Container(carte_stat("Disponibles", occ["disponibles"], ft.icons.CHECK_CIRCLE, "#22c55e"), col={"sm": 6, "md": 3}),
                ft.Container(carte_stat("Réservés", occ["reserves"], ft.icons.HOURGLASS_EMPTY, "#f97316"), col={"sm": 6, "md": 3}),
                ft.Container(carte_stat("Occupés", occ["occupes"], ft.icons.LOCK, "#ef4444"), col={"sm": 6, "md": 3}),
            ], spacing=12, run_spacing=12)

            sections = [cartes_stats, jauge_saturation(occ["jauge_saturation"])]

            # Finances (si permission)
            fin = data.get("finances")
            if fin:
                sections.append(ft.ResponsiveRow([
                    ft.Container(carte_stat("Revenus totaux", f"{fin['revenus_total']:,.0f} FCFA", ft.icons.PAYMENTS, COULEUR_PRIMAIRE), col={"sm": 6, "md": 4}),
                    ft.Container(carte_stat("Revenus ce mois", f"{fin['revenus_ce_mois']:,.0f} FCFA", ft.icons.CALENDAR_MONTH, "#22c55e"), col={"sm": 6, "md": 4}),
                    ft.Container(carte_stat("Factures en retard", fin["factures_en_retard"], ft.icons.WARNING_AMBER, "#ef4444"), col={"sm": 6, "md": 4}),
                ], spacing=12, run_spacing=12))

            # Alertes concessions
            alertes = data.get("alertes", {})
            if alertes.get("concessions_expirant_bientot", 0) > 0:
                sections.append(ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.icons.NOTIFICATION_IMPORTANT, color="#f97316"),
                        ft.Text(
                            f"{alertes['concessions_expirant_bientot']} concession(s) "
                            f"expirent dans moins de 90 jours.",
                            color="#92400e",
                        ),
                    ]),
                    bgcolor="#fff7ed", padding=14, border_radius=10, border=ft.border.all(1, "#fed7aa"),
                ))

            sections.append(tableau_blocs(data.get("par_bloc", [])))

            content_area.content = ft.Column(sections, spacing=16, scroll=ft.ScrollMode.AUTO, expand=True)

        except APIError as err:
            content_area.content = etat_vide(f"Erreur : {err.detail}", ft.icons.ERROR_OUTLINE)

        page.update()

    charger()

    return ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Text("Tableau de bord", size=20, weight=ft.FontWeight.BOLD),
                ft.Container(expand=True),
                ft.IconButton(ft.icons.REFRESH, on_click=lambda e: charger(), tooltip="Actualiser"),
            ]),
            ft.Divider(),
            content_area,
        ], spacing=10, expand=True),
        padding=20, expand=True,
    )
