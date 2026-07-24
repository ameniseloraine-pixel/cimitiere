"""
Vue Login — Authentification en 2 étapes : email/mot de passe puis code MFA
"""

import flet as ft
from api_client import APIError
from components.widgets import champ_texte, bouton_principal, afficher_snackbar
from config import COULEUR_PRIMAIRE


def LoginView(page: ft.Page, client, on_login_success, on_go_register):
    """
    Construit la vue de connexion avec workflow MFA.
    on_login_success() : callback appelé quand l'authentification réussit.
    on_go_register() : callback pour aller vers l'inscription.
    """

    # ─── Étape 1 : Email / Mot de passe ───────────────────────────────────────
    email_field = champ_texte("Adresse email", autofocus=True, width=320)
    password_field = champ_texte("Mot de passe", password=True, can_reveal_password=True, width=320)

    # ─── Étape 2 : Code MFA ─────────────────────────────────────────────────
    mfa_field = champ_texte("Code à 6 chiffres", width=320, max_length=6, text_align=ft.TextAlign.CENTER)
    mfa_info_text = ft.Text("", size=13, color="#6b7280", text_align=ft.TextAlign.CENTER)

    loading = ft.ProgressRing(visible=False, width=20, height=20, stroke_width=2)

    # Conteneurs pour basculer entre les étapes
    step1_container = ft.Container()
    step2_container = ft.Container(visible=False)

    email_en_attente = {"email": ""}

    def faire_login(e):
        email = email_field.value.strip()
        password = password_field.value

        if not email or not password:
            afficher_snackbar(page, "Veuillez remplir tous les champs.", succes=False)
            return

        loading.visible = True
        login_btn.disabled = True
        page.update()

        try:
            result = client.login(email, password)
            email_en_attente["email"] = email
            mfa_info_text.value = result.get("message", f"Code envoyé à {email}")
            step1_container.visible = False
            step2_container.visible = True
            mfa_field.focus()
        except APIError as err:
            afficher_snackbar(page, err.detail, succes=False)
        finally:
            loading.visible = False
            login_btn.disabled = False
            page.update()

    def verifier_mfa(e):
        code = mfa_field.value.strip()
        if len(code) != 6 or not code.isdigit():
            afficher_snackbar(page, "Le code doit contenir 6 chiffres.", succes=False)
            return

        loading.visible = True
        verify_btn.disabled = True
        page.update()

        try:
            client.verify_mfa(email_en_attente["email"], code)
            afficher_snackbar(page, f"Bienvenue, {client.user['prenom']} !", succes=True)
            on_login_success()
        except APIError as err:
            afficher_snackbar(page, err.detail, succes=False)
            mfa_field.value = ""
        finally:
            loading.visible = False
            verify_btn.disabled = False
            page.update()

    def retour_etape1(e):
        step1_container.visible = True
        step2_container.visible = False
        mfa_field.value = ""
        page.update()

    def renvoyer_code(e):
        try:
            result = client.login(email_en_attente["email"], password_field.value)
            mfa_info_text.value = result.get("message", "Nouveau code envoyé.")
            afficher_snackbar(page, "Un nouveau code a été envoyé.", succes=True)
        except APIError as err:
            afficher_snackbar(page, err.detail, succes=False)
        page.update()

    login_btn = bouton_principal("Se connecter", on_click=faire_login, icone=ft.icons.LOGIN, width=320)
    verify_btn = bouton_principal("Vérifier", on_click=verifier_mfa, icone=ft.icons.VERIFIED_USER, width=320)

    # Permettre la soumission avec Entrée
    password_field.on_submit = faire_login
    mfa_field.on_submit = verifier_mfa

    step1_container.content = ft.Column(
        [
            email_field,
            password_field,
            login_btn,
            ft.Row([
                ft.Text("Pas encore de compte ?", color="#6b7280", size=13),
                ft.TextButton("Créer un compte", on_click=lambda e: on_go_register()),
            ], alignment=ft.MainAxisAlignment.CENTER),
        ],
        spacing=16,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    step2_container.content = ft.Column(
        [
            ft.Icon(ft.icons.MARK_EMAIL_READ, size=48, color=COULEUR_PRIMAIRE),
            ft.Text("Vérification en deux étapes", size=18, weight=ft.FontWeight.BOLD),
            mfa_info_text,
            mfa_field,
            verify_btn,
            ft.Row([
                ft.TextButton("Renvoyer le code", on_click=renvoyer_code),
                ft.TextButton("Modifier l'email", on_click=retour_etape1),
            ], alignment=ft.MainAxisAlignment.CENTER),
        ],
        spacing=14,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    return ft.Container(
        content=ft.Column(
            [
                ft.Icon(ft.icons.LOCATION_CITY, size=56, color=COULEUR_PRIMAIRE),
                ft.Text("Gestion de Cimetière", size=24, weight=ft.FontWeight.BOLD, color=ft.colors.ON_SURFACE),
                ft.Text("Connectez-vous à votre espace", size=14, color="#6b7280"),
                ft.Container(height=10),
                step1_container,
                step2_container,
                loading,
            ],
            spacing=12,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            scroll=ft.ScrollMode.AUTO,
        ),
        alignment=ft.alignment.center,
        expand=True,
        padding=30,
    )
