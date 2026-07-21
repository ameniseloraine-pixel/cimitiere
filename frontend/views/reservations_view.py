"""
Vue Réservations — Liste des réservations
- Client : ses propres dossiers + annulation possible si EN_ATTENTE
- Admin/Secrétariat : toutes les réservations + validation/rejet
"""

import flet as ft

from api_client import APIError
from components.widgets import (
    badge_generique, afficher_snackbar, chargement, etat_vide,
    bouton_principal, COULEURS_STATUT_RESERVATION,
)
from config import COULEUR_PRIMAIRE
from responsive import est_mobile as _est_mobile, largeur_contenu


def ReservationsView(page: ft.Page, client):
    mobile = _est_mobile(page)
    content_area = ft.Container(content=chargement("Chargement des réservations..."), expand=True)
    filtre_statut = ft.Dropdown(
        label="Filtrer par statut",
        width=largeur_contenu(page, 220, marge=24) if mobile else 220,
        options=[
            ft.dropdown.Option("", "Tous les statuts"),
            ft.dropdown.Option("ATTENTE", "En attente de validation"),
            ft.dropdown.Option("VALIDEE", "Validée"),
            ft.dropdown.Option("REJETEE", "Rejetée"),
            ft.dropdown.Option("ANNULEE", "Annulée"),
        ],
        value="",
        on_change=lambda e: charger(),
    )

    def ouvrir_dialogue_rejet(reservation):
        motif_field = ft.TextField(label="Motif du rejet", multiline=True, min_lines=2, expand=True)

        def confirmer_rejet(e):
            try:
                client.rejeter_reservation(reservation["id"], motif_field.value or "")
                afficher_snackbar(page, f"Dossier {reservation['numero_dossier']} rejeté.", succes=True)
                page.close(dlg)
                charger()
            except APIError as err:
                afficher_snackbar(page, err.detail, succes=False)

        dlg = ft.AlertDialog(
            title=ft.Text(f"Rejeter le dossier {reservation['numero_dossier']}"),
            content=ft.Container(content=motif_field, width=largeur_contenu(page, 380)),
            actions=[
                ft.TextButton("Annuler", on_click=lambda e: page.close(dlg)),
                ft.ElevatedButton("Confirmer le rejet", on_click=confirmer_rejet, bgcolor="#ef4444", color="white"),
            ],
        )
        page.open(dlg)

    def valider(reservation):
        def confirmer(e):
            try:
                client.valider_reservation(reservation["id"])
                afficher_snackbar(
                    page,
                    f"Dossier {reservation['numero_dossier']} validé. Facture envoyée au client.",
                    succes=True,
                )
                page.close(dlg)
                charger()
            except APIError as err:
                afficher_snackbar(page, err.detail, succes=False)
                page.close(dlg)

        dlg = ft.AlertDialog(
            title=ft.Text("Confirmer la validation"),
            content=ft.Text(
                f"Valider le dossier {reservation['numero_dossier']} ?\n\n"
                f"Le caveau {reservation['caveau_reference']} passera en statut OCCUPÉ "
                f"et une facture sera générée et envoyée au client."
            ),
            actions=[
                ft.TextButton("Annuler", on_click=lambda e: page.close(dlg)),
                ft.ElevatedButton("Valider", on_click=confirmer, bgcolor="#22c55e", color="white"),
            ],
        )
        page.open(dlg)

    def annuler(reservation):
        def confirmer(e):
            try:
                client.annuler_reservation(reservation["id"])
                afficher_snackbar(page, "Réservation annulée.", succes=True)
                page.close(dlg)
                charger()
            except APIError as err:
                afficher_snackbar(page, err.detail, succes=False)
                page.close(dlg)

        dlg = ft.AlertDialog(
            title=ft.Text("Annuler la réservation ?"),
            content=ft.Text(f"Le dossier {reservation['numero_dossier']} sera annulé et le caveau redeviendra disponible."),
            actions=[
                ft.TextButton("Non", on_click=lambda e: page.close(dlg)),
                ft.ElevatedButton("Oui, annuler", on_click=confirmer, bgcolor="#ef4444", color="white"),
            ],
        )
        page.open(dlg)

    def construire_carte_reservation(r: dict) -> ft.Container:
        statut = r["statut"]
        couleur = COULEURS_STATUT_RESERVATION.get(statut, "#9ca3af")

        actions = []
        if statut == "ATTENTE":
            if client.can_validate:
                actions += [
                    ft.ElevatedButton("Valider", icon=ft.icons.CHECK, bgcolor="#22c55e", color="white",
                                       on_click=lambda e, res=r: valider(res)),
                    ft.OutlinedButton("Rejeter", icon=ft.icons.CLOSE,
                                       on_click=lambda e, res=r: ouvrir_dialogue_rejet(res)),
                ]
            elif r["client_email"] == client.user["email"]:
                actions.append(
                    ft.OutlinedButton("Annuler ma demande", icon=ft.icons.DELETE_OUTLINE,
                                       on_click=lambda e, res=r: annuler(res))
                )

        infos = [
            ft.Row([
                ft.Text(r["numero_dossier"], weight=ft.FontWeight.BOLD, size=15),
                badge_generique(r["statut_libelle"], couleur),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Text(f"Défunt : {r['defunt_nom_complet']} — Décès le {r['defunt_date_deces']}", size=13),
            ft.Text(f"Caveau : {r['caveau_reference']}", size=13, color="#6b7280"),
        ]

        if not client.is_admin and client.role == "CLIENT":
            pass  # client_nom déjà implicite
        else:
            infos.append(ft.Text(f"Client : {r['client_nom']} ({r['client_email']})", size=13, color="#6b7280"))

        if r.get("date_inhumation_souhaitee"):
            infos.append(ft.Text(f"Inhumation souhaitée : {r['date_inhumation_souhaitee']}", size=12, color="#6b7280"))

        infos.append(ft.Text(f"Soumis le {r['date_soumission'][:10]}", size=11, color="#9ca3af"))

        if r["statut"] == "REJETEE" and r.get("motif_rejet"):
            infos.append(ft.Container(
                content=ft.Text(f"Motif du rejet : {r['motif_rejet']}", size=12, color="#991b1b"),
                bgcolor="#fef2f2", padding=8, border_radius=6,
            ))

        if r["statut"] == "VALIDEE" and r.get("validee_par"):
            infos.append(ft.Text(f"Validé par {r['validee_par']} le {r['date_validation'][:10]}", size=11, color="#16a34a"))

        if actions:
            infos.append(ft.Row(actions, spacing=8))

        return ft.Container(
            content=ft.Column(infos, spacing=6),
            bgcolor=ft.colors.SURFACE,
            padding=14,
            border_radius=10,
            border=ft.border.all(1, "#e5e7eb"),
        )

    def charger():
        content_area.content = chargement("Chargement des réservations...")
        page.update()
        try:
            reservations = client.liste_reservations(statut=filtre_statut.value or None)
            if not reservations:
                content_area.content = etat_vide("Aucune réservation trouvée.", ft.icons.ASSIGNMENT_OUTLINED)
            else:
                content_area.content = ft.Column(
                    [construire_carte_reservation(r) for r in reservations],
                    spacing=10, scroll=ft.ScrollMode.AUTO, expand=True,
                )
        except APIError as err:
            content_area.content = etat_vide(f"Erreur : {err.detail}", ft.icons.ERROR_OUTLINE)
        page.update()

    charger()

    titre = "Réservations" if not client.can_validate else "Gestion des réservations"

    return ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Text(titre, size=17 if mobile else 20, weight=ft.FontWeight.BOLD),
                ft.Container(expand=True),
                filtre_statut,
                ft.IconButton(ft.icons.REFRESH, on_click=lambda e: charger(), tooltip="Actualiser"),
            ], wrap=True, spacing=8, run_spacing=8),
            ft.Divider(),
            content_area,
        ], spacing=10, expand=True, scroll=ft.ScrollMode.AUTO),
        padding=12 if mobile else 20, expand=True,
    )
