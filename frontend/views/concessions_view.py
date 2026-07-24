"""
Vue Concessions & Exhumations
- Liste des concessions avec alertes d'expiration (< 90 jours)
- Création (Admin/Secrétariat), renouvellement
- Demandes d'exhumation : soumission, autorisation/refus (admin)
"""

import flet as ft

from api_client import APIError
from components.widgets import (
    badge_generique, afficher_snackbar, chargement, etat_vide,
    bouton_principal, champ_texte,
    COULEURS_STATUT_CONCESSION, COULEURS_STATUT_EXHUMATION,
)
from config import COULEUR_PRIMAIRE


TYPES_CONCESSION = [
    ("TEMP_5", "Temporaire 5 ans"),
    ("TEMP_10", "Temporaire 10 ans"),
    ("TEMP_15", "Temporaire 15 ans"),
    ("PERP", "Perpétuelle"),
    ("FAM", "Familiale"),
]


def ConcessionsView(page: ft.Page, client):
    tabs_content = ft.Container(expand=True)

    # ─── Création d'une concession (NOUVEAU) ──────────────────────────────────

    def ouvrir_dialogue_creation_concession():
        reservation_id_field = champ_texte(
            "ID de la réservation validée *", width=350,
            keyboard_type=ft.KeyboardType.NUMBER,
            hint_text="Voir dans l'onglet Réservations",
        )
        type_dd = ft.Dropdown(
            label="Type de concession *",
            width=350,
            options=[ft.dropdown.Option(k, v) for k, v in TYPES_CONCESSION],
            value="TEMP_10",
        )
        date_debut_field = champ_texte(
            "Date de début (AAAA-MM-JJ) *", width=350,
            hint_text="Ex: 2026-07-09",
        )

        def creer(e):
            if not reservation_id_field.value or not date_debut_field.value:
                afficher_snackbar(page, "Merci de remplir tous les champs obligatoires.", succes=False)
                return
            try:
                reservation_id = int(reservation_id_field.value)
            except ValueError:
                afficher_snackbar(page, "L'ID de réservation doit être un nombre.", succes=False)
                return
            try:
                client.creer_concession(
                    reservation_id=reservation_id,
                    type_concession=type_dd.value,
                    date_debut=date_debut_field.value,
                )
                afficher_snackbar(page, "Concession créée avec succès.", succes=True)
                page.close(dlg)
                charger_concessions()
            except APIError as err:
                afficher_snackbar(page, err.detail, succes=False)

        dlg = ft.AlertDialog(
            title=ft.Text("Créer une concession"),
            content=ft.Container(
                content=ft.Column([
                    ft.Text(
                        "La réservation doit déjà être validée. Trouvez son ID "
                        "dans l'onglet Réservations.",
                        size=12, color="#6b7280",
                    ),
                    reservation_id_field,
                    type_dd,
                    date_debut_field,
                ], spacing=10, tight=True),
                width=350,
            ),
            actions=[
                ft.TextButton("Annuler", on_click=lambda e: page.close(dlg)),
                ft.ElevatedButton("Créer", on_click=creer, bgcolor=COULEUR_PRIMAIRE, color="white"),
            ],
        )
        page.open(dlg)

    # ─── Onglet Concessions ───────────────────────────────────────────────────

    def ouvrir_dialogue_exhumation(concession: dict):
        motif_field = champ_texte("Motif de l'exhumation *", width=350, multiline=True, min_lines=2)
        destination_field = champ_texte("Destination des restes mortels (optionnel)", width=350, multiline=True, min_lines=2)

        def soumettre(e):
            if not motif_field.value:
                afficher_snackbar(page, "Le motif est obligatoire.", succes=False)
                return
            try:
                client.soumettre_exhumation(concession["id"], motif_field.value, destination_field.value or "")
                afficher_snackbar(page, "Demande d'exhumation soumise.", succes=True)
                page.close(dlg)
                charger_concessions()
            except APIError as err:
                afficher_snackbar(page, err.detail, succes=False)

        dlg = ft.AlertDialog(
            title=ft.Text(f"Demande d'exhumation — {concession['numero_contrat']}"),
            content=ft.Column([motif_field, destination_field], tight=True, spacing=10),
            actions=[
                ft.TextButton("Annuler", on_click=lambda e: page.close(dlg)),
                ft.ElevatedButton("Soumettre", on_click=soumettre, bgcolor=COULEUR_PRIMAIRE, color="white"),
            ],
        )
        page.open(dlg)

    def renouveler(concession: dict):
        def confirmer(e):
            try:
                client.renouveler_concession(concession["id"])
                afficher_snackbar(page, "Concession renouvelée avec succès.", succes=True)
                page.close(dlg)
                charger_concessions()
            except APIError as err:
                afficher_snackbar(page, err.detail, succes=False)
                page.close(dlg)

        dlg = ft.AlertDialog(
            title=ft.Text("Renouveler la concession ?"),
            content=ft.Text(
                f"Renouveler la concession {concession['numero_contrat']} "
                f"({concession['type_concession_libelle']}) ?\nUn nouveau contrat sera créé."
            ),
            actions=[
                ft.TextButton("Annuler", on_click=lambda e: page.close(dlg)),
                ft.ElevatedButton("Renouveler", on_click=confirmer, bgcolor=COULEUR_PRIMAIRE, color="white"),
            ],
        )
        page.open(dlg)

    def construire_carte_concession(c: dict) -> ft.Container:
        couleur = COULEURS_STATUT_CONCESSION.get(c["statut"], "#9ca3af")

        infos = [
            ft.Row([
                ft.Text(c["numero_contrat"], weight=ft.FontWeight.BOLD, size=15),
                badge_generique(c["statut_libelle"], couleur),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Text(f"Type : {c['type_concession_libelle']}", size=13),
            ft.Text(f"Caveau : {c['caveau_reference']}", size=13, color="#6b7280"),
        ]

        if client.can_see_finance:
            infos.append(ft.Text(f"Titulaire : {c['titulaire_nom']} ({c['titulaire_email']})", size=12, color="#6b7280"))

        if c["est_perpetuelle"]:
            infos.append(ft.Text("Concession perpétuelle (sans expiration)", size=12, color="#3b82f6"))
        else:
            infos.append(ft.Text(
                f"Validité : {c['date_debut']} → {c['date_fin']}"
                + (f"  ({c['jours_avant_expiration']} jours restants)" if c['jours_avant_expiration'] is not None else ""),
                size=12, color="#6b7280",
            ))

        if c["necessite_alerte"]:
            infos.append(ft.Container(
                content=ft.Row([
                    ft.Icon(ft.icons.WARNING_AMBER, color="#f97316", size=16),
                    ft.Text(f"Expire dans {c['jours_avant_expiration']} jours — renouvellement conseillé", size=12, color="#92400e"),
                ]),
                bgcolor="#fff7ed", padding=8, border_radius=6,
            ))

        actions = []
        if c["statut"] == "ACTIVE" and not c["est_perpetuelle"]:
            actions.append(ft.OutlinedButton("Renouveler", icon=ft.icons.AUTORENEW,
                                               on_click=lambda e, conc=c: renouveler(conc)))
        if c["statut"] in ("ACTIVE", "ALERTE"):
            actions.append(ft.OutlinedButton("Demander une exhumation", icon=ft.icons.OUTBOX,
                                               on_click=lambda e, conc=c: ouvrir_dialogue_exhumation(conc)))

        if actions:
            infos.append(ft.Row(actions, spacing=8))

        return ft.Container(
            content=ft.Column(infos, spacing=6),
            bgcolor=ft.colors.SURFACE, padding=14, border_radius=10, border=ft.border.all(1, "#e5e7eb"),
        )

    concessions_content = ft.Container(content=chargement("Chargement..."), expand=True)
    filtre_alerte = ft.Checkbox(label="Alertes uniquement (< 90 jours)", on_change=lambda e: charger_concessions())

    def charger_concessions():
        concessions_content.content = chargement("Chargement des concessions...")
        page.update()
        try:
            concessions = client.liste_concessions(alerte_seulement=filtre_alerte.value)
            if not concessions:
                concessions_content.content = etat_vide("Aucune concession trouvée.", ft.icons.DESCRIPTION)
            else:
                concessions_content.content = ft.Column(
                    [construire_carte_concession(c) for c in concessions],
                    spacing=10, scroll=ft.ScrollMode.AUTO, expand=True,
                )
        except APIError as err:
            concessions_content.content = etat_vide(f"Erreur : {err.detail}", ft.icons.ERROR_OUTLINE)
        page.update()

    # ─── Onglet Exhumations ────────────────────────────────────────────────────

    def autoriser_exhumation(exhumation: dict):
        def confirmer(e):
            try:
                client.autoriser_exhumation(exhumation["id"])
                afficher_snackbar(page, "Exhumation autorisée. Documents générés et envoyés.", succes=True)
                page.close(dlg)
                charger_exhumations()
            except APIError as err:
                afficher_snackbar(page, err.detail, succes=False)
                page.close(dlg)

        dlg = ft.AlertDialog(
            title=ft.Text("Autoriser l'exhumation ?"),
            content=ft.Text(f"Autoriser la demande {exhumation['numero_demande']} ?\nL'autorisation et le PV seront générés et envoyés par email."),
            actions=[
                ft.TextButton("Annuler", on_click=lambda e: page.close(dlg)),
                ft.ElevatedButton("Autoriser", on_click=confirmer, bgcolor="#22c55e", color="white"),
            ],
        )
        page.open(dlg)

    def refuser_exhumation(exhumation: dict):
        motif_field = champ_texte("Motif du refus", width=320, multiline=True, min_lines=2)

        def confirmer(e):
            try:
                client.refuser_exhumation(exhumation["id"], motif_field.value or "")
                afficher_snackbar(page, "Demande refusée.", succes=True)
                page.close(dlg)
                charger_exhumations()
            except APIError as err:
                afficher_snackbar(page, err.detail, succes=False)

        dlg = ft.AlertDialog(
            title=ft.Text(f"Refuser la demande {exhumation['numero_demande']}"),
            content=motif_field,
            actions=[
                ft.TextButton("Annuler", on_click=lambda e: page.close(dlg)),
                ft.ElevatedButton("Refuser", on_click=confirmer, bgcolor="#ef4444", color="white"),
            ],
        )
        page.open(dlg)

    def construire_carte_exhumation(ex: dict) -> ft.Container:
        couleur = COULEURS_STATUT_EXHUMATION.get(ex["statut"], "#9ca3af")

        infos = [
            ft.Row([
                ft.Text(ex["numero_demande"], weight=ft.FontWeight.BOLD, size=15),
                badge_generique(ex["statut_libelle"], couleur),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Text(f"Concession : {ex['concession_numero']}", size=13),
            ft.Text(f"Demandeur : {ex['demandeur_nom']}", size=12, color="#6b7280"),
            ft.Text(f"Motif : {ex['motif']}", size=12),
        ]

        if ex.get("destination_restes"):
            infos.append(ft.Text(f"Destination : {ex['destination_restes']}", size=12, color="#6b7280"))

        infos.append(ft.Text(f"Soumise le {ex['date_demande'][:10]}", size=11, color="#9ca3af"))

        if ex["statut"] == "REFUSEE" and ex.get("motif_refus"):
            infos.append(ft.Container(
                content=ft.Text(f"Motif du refus : {ex['motif_refus']}", size=12, color="#991b1b"),
                bgcolor="#fef2f2", padding=8, border_radius=6,
            ))

        if ex["statut"] in ("DEMANDE", "INSTRUCT") and client.is_admin:
            infos.append(ft.Row([
                ft.ElevatedButton("Autoriser", icon=ft.icons.CHECK, bgcolor="#22c55e", color="white",
                                   on_click=lambda e, exh=ex: autoriser_exhumation(exh)),
                ft.OutlinedButton("Refuser", icon=ft.icons.CLOSE,
                                   on_click=lambda e, exh=ex: refuser_exhumation(exh)),
            ], spacing=8))

        return ft.Container(
            content=ft.Column(infos, spacing=6),
            bgcolor=ft.colors.SURFACE, padding=14, border_radius=10, border=ft.border.all(1, "#e5e7eb"),
        )

    exhumations_content = ft.Container(content=chargement("Chargement..."), expand=True)

    def charger_exhumations():
        exhumations_content.content = chargement("Chargement des exhumations...")
        page.update()
        try:
            exhumations = client.liste_exhumations()
            if not exhumations:
                exhumations_content.content = etat_vide("Aucune demande d'exhumation.", ft.icons.OUTBOX)
            else:
                exhumations_content.content = ft.Column(
                    [construire_carte_exhumation(ex) for ex in exhumations],
                    spacing=10, scroll=ft.ScrollMode.AUTO, expand=True,
                )
        except APIError as err:
            exhumations_content.content = etat_vide(f"Erreur : {err.detail}", ft.icons.ERROR_OUTLINE)
        page.update()

    # ─── Construction des onglets ───────────────────────────────────────────────

    def on_tab_change(e):
        if e.control.selected_index == 0:
            charger_concessions()
            tabs_content.content = ft.Column([filtre_alerte, concessions_content], spacing=10, expand=True)
        else:
            charger_exhumations()
            tabs_content.content = exhumations_content
        page.update()

    tabs = ft.Tabs(
        selected_index=0,
        on_change=on_tab_change,
        tabs=[
            ft.Tab(text="Concessions"),
            ft.Tab(text="Exhumations"),
        ],
    )

    charger_concessions()
    tabs_content.content = ft.Column([filtre_alerte, concessions_content], spacing=10, expand=True)

    # NOUVEAU : bouton "Créer une concession", visible pour Admin/Secrétariat uniquement
    bouton_creer = ft.ElevatedButton(
        "Créer une concession", icon=ft.icons.ADD,
        bgcolor=COULEUR_PRIMAIRE, color="white",
        on_click=lambda e: ouvrir_dialogue_creation_concession(),
        visible=client.can_see_finance,
    )

    return ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Text("Concessions & Exhumations", size=20, weight=ft.FontWeight.BOLD),
                ft.Container(expand=True),
                bouton_creer,
                ft.IconButton(ft.icons.REFRESH, on_click=lambda e: on_tab_change(
                    type("E", (), {"control": tabs})()
                ), tooltip="Actualiser"),
            ]),
            tabs,
            ft.Divider(),
            tabs_content,
        ], spacing=10, expand=True),
        padding=20, expand=True,
    )