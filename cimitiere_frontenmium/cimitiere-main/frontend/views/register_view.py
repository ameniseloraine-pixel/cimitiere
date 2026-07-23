"""
Vue Inscription — Création de compte client. Même habillage premium
responsive que la vue Login (carte élevée, largeur plafonnée, jamais de
débordement mobile).
"""

import flet as ft
from api_client import APIError
from components.widgets import champ_texte, bouton_principal, afficher_snackbar
from config import couleurs
from responsive import largeur_contenu


def RegisterView(page: ft.Page, client, on_register_success, on_go_login):
    t = couleurs(page)

    nom_field = champ_texte("Nom", autofocus=True)
    prenom_field = champ_texte("Prénom")
    email_field = champ_texte("Adresse email")
    telephone_field = champ_texte("Téléphone (optionnel)")
    password_field = champ_texte("Mot de passe", password=True, can_reveal_password=True)
    password2_field = champ_texte("Confirmer le mot de passe", password=True, can_reveal_password=True)

    loading = ft.ProgressRing(visible=False, width=20, height=20, stroke_width=2, color=t["accent"])

    def faire_register(e):
        if not all([nom_field.value, prenom_field.value, email_field.value, password_field.value]):
            afficher_snackbar(page, "Veuillez remplir tous les champs obligatoires.", succes=False)
            return
        if password_field.value != password2_field.value:
            afficher_snackbar(page, "Les mots de passe ne correspondent pas.", succes=False)
            return
        if len(password_field.value) < 8:
            afficher_snackbar(page, "Le mot de passe doit contenir au moins 8 caractères.", succes=False)
            return

        loading.visible = True
        register_btn.disabled = True
        page.update()

        try:
            client.register(
                email=email_field.value.strip(),
                password=password_field.value,
                nom=nom_field.value.strip(),
                prenom=prenom_field.value.strip(),
                telephone=telephone_field.value.strip(),
            )
            afficher_snackbar(page, "Compte créé avec succès ! Vous pouvez vous connecter.", succes=True)
            on_register_success()
        except APIError as err:
            afficher_snackbar(page, err.detail, succes=False)
        finally:
            loading.visible = False
            register_btn.disabled = False
            page.update()

    register_btn = bouton_principal("Créer mon compte", on_click=faire_register, icone=ft.icons.PERSON_ADD)

    carte_formulaire = ft.Container(
        content=ft.Column(
            [
                ft.Icon(ft.icons.PERSON_ADD_ALT_1, size=40, color=t["accent"]),
                ft.Text(
                    "Créer un compte", size=20, weight=ft.FontWeight.BOLD, color=t["texte"],
                    font_family="Playfair Display, Georgia, serif", text_align=ft.TextAlign.CENTER,
                ),
                ft.Text("Pour réserver et suivre vos dossiers", size=13, color=t["texte_att"], text_align=ft.TextAlign.CENTER),
                ft.Container(height=8),
                nom_field,
                prenom_field,
                email_field,
                telephone_field,
                password_field,
                password2_field,
                register_btn,
                loading,
                ft.Row([
                    ft.Text("Déjà un compte ?", color=t["texte_att"], size=13),
                    ft.TextButton("Se connecter", on_click=lambda e: on_go_login()),
                ], alignment=ft.MainAxisAlignment.CENTER, wrap=True),
            ],
            spacing=12,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            scroll=ft.ScrollMode.AUTO,
        ),
        width=largeur_contenu(page, 400),
        bgcolor=t["surface"],
        padding=ft.padding.symmetric(horizontal=32, vertical=32),
        border_radius=20,
        border=ft.border.all(1, t["bordure"]),
        shadow=ft.BoxShadow(spread_radius=0, blur_radius=30, color=t["ombre"], offset=ft.Offset(0, 12)),
    )

    return ft.Container(
        content=carte_formulaire,
        alignment=ft.alignment.center,
        expand=True,
        padding=20,
        bgcolor=t["fond"],
    )
