"""
Vue Login — Authentification en 2 étapes : email/mot de passe puis code MFA.
Carte unique centrée, identique sur tous les écrans (pas de panneau
"desktop only" qui change l'apparence selon la taille). Fond avec un
dégradé radial très doux (accent or) pour une touche premium discrète,
qui reste correctement thème-aware en clair comme en sombre.
"""

import flet as ft
from api_client import APIError
from components.widgets import champ_texte, bouton_principal, afficher_snackbar
from config import couleurs
from responsive import largeur_contenu, est_mobile as _est_mobile


def LoginView(page: ft.Page, client, on_login_success, on_go_register):
    """
    Construit la vue de connexion avec workflow MFA.
    on_login_success() : callback appelé quand l'authentification réussit.
    on_go_register() : callback pour aller vers l'inscription.
    """
    t = couleurs(page)
    mobile = _est_mobile(page)

    # ─── Étape 1 : Email / Mot de passe ───────────────────────────────────────
    email_field = champ_texte("Adresse email", autofocus=True)
    password_field = champ_texte("Mot de passe", password=True, can_reveal_password=True)

    # ─── Étape 2 : Code MFA ─────────────────────────────────────────────────
    mfa_field = champ_texte("Code à 6 chiffres", max_length=6, text_align=ft.TextAlign.CENTER)
    mfa_info_text = ft.Text("", size=13, color=t["texte_att"], text_align=ft.TextAlign.CENTER)

    loading = ft.ProgressRing(visible=False, width=20, height=20, stroke_width=2, color=t["accent"])

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
            page.update()
            try:
                mfa_field.focus()
            except Exception:
                pass
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

    login_btn = bouton_principal("Se connecter", on_click=faire_login, icone=ft.icons.LOGIN)
    verify_btn = bouton_principal("Vérifier", on_click=verifier_mfa, icone=ft.icons.VERIFIED_USER)

    password_field.on_submit = faire_login
    mfa_field.on_submit = verifier_mfa

    step1_container.content = ft.Column(
        [
            email_field,
            password_field,
            login_btn,
            ft.Row([
                ft.Text("Pas encore de compte ?", color=t["texte_att"], size=13),
                ft.TextButton("Créer un compte", on_click=lambda e: on_go_register()),
            ], alignment=ft.MainAxisAlignment.CENTER, wrap=True),
        ],
        spacing=16,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
    )

    step2_container.content = ft.Column(
        [
            ft.Icon(ft.icons.MARK_EMAIL_READ, size=44, color=t["accent"]),
            ft.Text("Vérification en deux étapes", size=17, weight=ft.FontWeight.BOLD, color=t["texte"], text_align=ft.TextAlign.CENTER),
            mfa_info_text,
            mfa_field,
            verify_btn,
            ft.Row([
                ft.TextButton("Renvoyer le code", on_click=renvoyer_code),
                ft.TextButton("Modifier l'email", on_click=retour_etape1),
            ], alignment=ft.MainAxisAlignment.CENTER, wrap=True),
        ],
        spacing=14,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
    )

    # ─── Carte de formulaire — élevée, plafonnée en largeur, jamais de débordement ───
    carte_formulaire = ft.Container(
        content=ft.Column(
            [
                ft.Container(
                    content=ft.Icon(ft.icons.LOCATION_CITY, size=30, color=t["on_accent"]),
                    bgcolor=t["accent"],
                    width=64, height=64,
                    border_radius=18,
                    alignment=ft.alignment.center,
                ),
                ft.Container(height=6),
                ft.Text(
                    "Gestion de Cimetière", size=22, weight=ft.FontWeight.BOLD, color=t["texte"],
                    font_family="Playfair Display, Georgia, serif", text_align=ft.TextAlign.CENTER,
                ),
                ft.Text("Connectez-vous à votre espace", size=13, color=t["texte_att"], text_align=ft.TextAlign.CENTER),
                ft.Container(height=8),
                step1_container,
                step2_container,
                loading,
            ],
            spacing=12,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            scroll=ft.ScrollMode.AUTO,
        ),
        width=largeur_contenu(page, 400),
        bgcolor=t["surface"],
        padding=ft.padding.symmetric(horizontal=32, vertical=36),
        border_radius=20,
        border=ft.border.all(1, t["bordure"]),
        shadow=ft.BoxShadow(spread_radius=0, blur_radius=30, color=t["ombre"], offset=ft.Offset(0, 12)),
    )

    return ft.Container(
        content=carte_formulaire,
        alignment=ft.alignment.center,
        expand=True,
        padding=20,
        gradient=ft.RadialGradient(
            center=ft.alignment.top_center, radius=1.4,
            colors=[ft.colors.with_opacity(0.10, t["accent"]), t["fond"]],
        ),
    )
