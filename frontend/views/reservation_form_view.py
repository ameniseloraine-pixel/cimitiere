"""
Vue Formulaire de Réservation — Soumission par le client
Saisie des informations du défunt + date d'inhumation souhaitée
"""

import flet as ft
from datetime import datetime, date

from api_client import APIError
from components.widgets import champ_texte, bouton_principal, afficher_snackbar
from config import COULEUR_PRIMAIRE


def ReservationFormView(page: ft.Page, client, caveau: dict, on_submitted, on_cancel):
    """
    Formulaire de soumission de réservation pour un caveau donné.
    on_submitted(reservation: dict) : callback appelé après succès.
    on_cancel() : callback pour annuler / revenir à la carte.
    """

    # ─── Champs Défunt ─────────────────────────────────────────────────────────
    nom_field = champ_texte("Nom du défunt *", width=300, autofocus=True)
    prenom_field = champ_texte("Prénom du défunt *", width=300)

    date_naissance_field = champ_texte("Date de naissance (JJ/MM/AAAA)", width=300)
    date_deces_field = champ_texte("Date de décès * (JJ/MM/AAAA)", width=300)
    lieu_deces_field = champ_texte("Lieu de décès", width=300)
    nationalite_field = champ_texte("Nationalité", width=300)
    acte_deces_field = champ_texte("N° acte de décès", width=300)

    # ─── Réservation ─────────────────────────────────────────────────────────
    date_inhumation_field = champ_texte("Date d'inhumation souhaitée (JJ/MM/AAAA)", width=300)
    notes_field = champ_texte("Remarques / Notes (optionnel)", width=620, multiline=True, min_lines=3)

    loading = ft.ProgressRing(visible=False, width=20, height=20, stroke_width=2)

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
        # Validation des champs obligatoires
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

    submit_btn = bouton_principal("Soumettre la demande", on_click=soumettre, icone=ft.icons.SEND, width=300)
    cancel_btn = ft.OutlinedButton("Annuler", on_click=lambda e: on_cancel(), width=150)

    return ft.Container(
        content=ft.Column([
            ft.Row([
                ft.IconButton(ft.icons.ARROW_BACK, on_click=lambda e: on_cancel(), tooltip="Retour à la carte"),
                ft.Text("Demande de réservation", size=20, weight=ft.FontWeight.BOLD),
            ]),
            ft.Container(
                content=ft.Row([
                    ft.Icon(ft.icons.PLACE, color=COULEUR_PRIMAIRE),
                    ft.Text(f"Caveau sélectionné : {caveau['reference']}", weight=ft.FontWeight.W_600),
                ]),
                bgcolor="#f0fdf4",
                padding=12,
                border_radius=8,
                border=ft.border.all(1, "#bbf7d0"),
            ),
            ft.Divider(),
            ft.Text("Informations sur le défunt", size=15, weight=ft.FontWeight.W_600),
            ft.ResponsiveRow([
                ft.Container(nom_field, col=6),
                ft.Container(prenom_field, col=6),
                ft.Container(date_naissance_field, col=6),
                ft.Container(date_deces_field, col=6),
                ft.Container(lieu_deces_field, col=6),
                ft.Container(nationalite_field, col=6),
                ft.Container(acte_deces_field, col=6),
            ], spacing=10, run_spacing=10),
            ft.Divider(),
            ft.Text("Détails de la réservation", size=15, weight=ft.FontWeight.W_600),
            date_inhumation_field,
            notes_field,
            ft.Container(
                content=ft.Text(
                    "ℹ️ Après soumission, le caveau passera en statut « Réservé / En attente » "
                    "(orange) jusqu'à validation par l'administration. Une facture vous sera "
                    "envoyée par email après validation.",
                    size=12, color="#6b7280",
                ),
                padding=10,
                bgcolor="#fff7ed",
                border_radius=8,
            ),
            ft.Row([submit_btn, cancel_btn, loading], spacing=12),
        ], spacing=14, scroll=ft.ScrollMode.AUTO, expand=True),
        padding=20,
        expand=True,
    )
