"""
Vue Formulaire de Réservation — Soumission par le client
Saisie des informations du défunt + date d'inhumation souhaitée
"""

import flet as ft
from datetime import datetime, date

from api_client import APIError
from components.widgets import champ_texte, bouton_principal, afficher_snackbar
from config import couleurs
from responsive import est_mobile as _est_mobile


def ReservationFormView(page: ft.Page, client, caveau: dict, on_submitted, on_cancel):
    """
    Formulaire de soumission de réservation pour un caveau donné.
    on_submitted(reservation: dict) : callback appelé après succès.
    on_cancel() : callback pour annuler / revenir à la carte.
    """
    t = couleurs(page)
    mobile = _est_mobile(page)

    # ─── Champs Défunt ─────────────────────────────────────────────────────────
    # Pas de width= fixe : chaque champ prend la largeur de sa colonne dans le
    # ResponsiveRow (col={"xs": 12, "sm": 6} => pleine largeur sur téléphone,
    # moitié sur écran plus grand).
    nom_field = champ_texte("Nom du défunt *", autofocus=True)
    prenom_field = champ_texte("Prénom du défunt *")

    date_naissance_field = champ_texte("Date de naissance (JJ/MM/AAAA)")
    date_deces_field = champ_texte("Date de décès * (JJ/MM/AAAA)")
    lieu_deces_field = champ_texte("Lieu de décès")
    nationalite_field = champ_texte("Nationalité")
    acte_deces_field = champ_texte("N° acte de décès")

    # ─── Réservation ─────────────────────────────────────────────────────────
    date_inhumation_field = champ_texte("Date d'inhumation souhaitée (JJ/MM/AAAA)")
    notes_field = champ_texte("Remarques / Notes (optionnel)", multiline=True, min_lines=3)

    loading = ft.ProgressRing(visible=False, width=20, height=20, stroke_width=2, color=t["accent"])

    def _parse_date(value: str, champ_label: str) -> str | None:
        """Convertit JJ/MM/AAAA en AAAA-MM-JJ (format ISO attendu par l'API)."""
        value = (value or "").strip()
        if not value:
            return None
        try:
            d = datetime.strptime(value, "%d/%m/%Y").date()
            return d.isoformat()
        except ValueError:
            raise ValueError(f"Format de date invalide pour « {champ_label} ». Utilisez JJ/MM/AAAA.")

    def soumettre(e):
        if not nom_field.value or not prenom_field.value or not date_deces_field.value:
            afficher_snackbar(page, "Les champs marqués * sont obligatoires.", succes=False)
            return

        try:
            date_deces_iso = _parse_date(date_deces_field.value, "Date de décès")
            date_naissance_iso = _parse_date(date_naissance_field.value, "Date de naissance")
            date_inhumation_iso = _parse_date(date_inhumation_field.value, "Date d'inhumation")
        except ValueError as ve:
            afficher_snackbar(page, str(ve), succes=False)
            return

        if not date_deces_iso:
            afficher_snackbar(page, "La date de décès est obligatoire.", succes=False)
            return

        defunt_payload = {
            "nom": nom_field.value.strip(),
            "prenom": prenom_field.value.strip(),
            "date_deces": date_deces_iso,
            "lieu_deces": lieu_deces_field.value.strip(),
            "nationalite": nationalite_field.value.strip(),
            "acte_deces_numero": acte_deces_field.value.strip(),
        }
        if date_naissance_iso:
            defunt_payload["date_naissance"] = date_naissance_iso

        loading.visible = True
        submit_btn.disabled = True
        page.update()

        try:
            reservation = client.soumettre_reservation(
                caveau_id=caveau["id"],
                defunt=defunt_payload,
                date_inhumation=date_inhumation_iso,
                notes=notes_field.value.strip(),
            )
            afficher_snackbar(
                page,
                f"Demande soumise ! Dossier {reservation['numero_dossier']} en attente de validation.",
                succes=True,
            )
            on_submitted(reservation)
        except APIError as err:
            afficher_snackbar(page, err.detail, succes=False)
        finally:
            loading.visible = False
            submit_btn.disabled = False
            page.update()

    submit_btn = bouton_principal("Soumettre la demande", on_click=soumettre, icone=ft.icons.SEND)
    cancel_btn = ft.OutlinedButton("Annuler", on_click=lambda e: on_cancel())

    return ft.Container(
        content=ft.Column([
            ft.Row([
                ft.IconButton(ft.icons.ARROW_BACK, on_click=lambda e: on_cancel(), tooltip="Retour à la carte"),
                ft.Text("Demande de réservation", size=18 if mobile else 20, weight=ft.FontWeight.BOLD, color=t["texte"]),
            ]),
            ft.Container(
                content=ft.Row([
                    ft.Icon(ft.icons.PLACE, color=t["accent"]),
                    ft.Text(f"Caveau sélectionné : {caveau['reference']}", weight=ft.FontWeight.W_600, color=t["texte"]),
                ], wrap=True),
                bgcolor=ft.colors.with_opacity(0.10, "#22c55e"),
                padding=12,
                border_radius=8,
                border=ft.border.all(1, ft.colors.with_opacity(0.30, "#22c55e")),
            ),
            ft.Divider(color=t["bordure"]),
            ft.Text("Informations sur le défunt", size=15, weight=ft.FontWeight.W_600, color=t["texte"]),
            ft.ResponsiveRow([
                ft.Container(nom_field, col={"xs": 12, "sm": 6}),
                ft.Container(prenom_field, col={"xs": 12, "sm": 6}),
                ft.Container(date_naissance_field, col={"xs": 12, "sm": 6}),
                ft.Container(date_deces_field, col={"xs": 12, "sm": 6}),
                ft.Container(lieu_deces_field, col={"xs": 12, "sm": 6}),
                ft.Container(nationalite_field, col={"xs": 12, "sm": 6}),
                ft.Container(acte_deces_field, col={"xs": 12, "sm": 6}),
            ], spacing=10, run_spacing=10),
            ft.Divider(color=t["bordure"]),
            ft.Text("Détails de la réservation", size=15, weight=ft.FontWeight.W_600, color=t["texte"]),
            date_inhumation_field,
            notes_field,
            ft.Container(
                content=ft.Text(
                    "ℹ️ Après soumission, le caveau passera en statut « Réservé / En attente » "
                    "(orange) jusqu'à validation par l'administration. Une facture vous sera "
                    "envoyée par email après validation.",
                    size=12, color=t["texte_att"],
                ),
                padding=10,
                bgcolor=t["surface_alt"],
                border_radius=8,
            ),
            ft.Row([submit_btn, cancel_btn, loading], spacing=12, wrap=True),
        ], spacing=14, scroll=ft.ScrollMode.AUTO, expand=True,
           horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
        padding=12 if mobile else 20,
        expand=True,
    )
