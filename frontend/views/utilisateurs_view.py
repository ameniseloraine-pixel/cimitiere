"""
Vue Gestion des Utilisateurs — Admin uniquement
Liste des comptes existants + création avec choix du rôle (RBAC)
"""

import flet as ft
from api_client import APIError
from components.widgets import afficher_snackbar, chargement, etat_vide, bouton_principal

ROLES_DISPONIBLES = [
    ("ADMIN", "Administrateur"),
    ("AGENT", "Agent de terrain"),
    ("SECR", "Secrétariat"),
    ("CLIENT", "Client"),
]


def UtilisateursView(page: ft.Page, client):
    content_area = ft.Container(content=chargement("Chargement des utilisateurs..."), expand=True)

    if not client.is_admin:
        return ft.Container(
            content=etat_vide("Accès réservé aux administrateurs.", ft.icons.LOCK_OUTLINE),
            padding=20,
            expand=True,
        )

    # ─── Formulaire de création ────────────────────────────────────────────
    champ_email = ft.TextField(label="Email", width=280)
    champ_password = ft.TextField(label="Mot de passe", width=280, password=True, can_reveal_password=True)
    champ_nom = ft.TextField(label="Nom", width=200)
    champ_prenom = ft.TextField(label="Prénom", width=200)
    champ_telephone = ft.TextField(label="Téléphone", width=200)
    champ_role = ft.Dropdown(
        label="Rôle",
        width=220,
        options=[ft.dropdown.Option(k, v) for k, v in ROLES_DISPONIBLES],
        value="AGENT",
    )

    def creer(e):
        if not champ_email.value or not champ_password.value or not champ_nom.value or not champ_prenom.value:
            afficher_snackbar(page, "Merci de remplir tous les champs obligatoires.", succes=False)
            return
        try:
            client.creer_utilisateur(
                email=champ_email.value,
                password=champ_password.value,
                nom=champ_nom.value,
                prenom=champ_prenom.value,
                role=champ_role.value,
                telephone=champ_telephone.value or "",
            )
            afficher_snackbar(page, f"Compte {champ_email.value} créé avec succès.", succes=True)
            champ_email.value = ""
            champ_password.value = ""
            champ_nom.value = ""
            champ_prenom.value = ""
            champ_telephone.value = ""
            charger_utilisateurs()
        except APIError as err:
            afficher_snackbar(page, err.detail, succes=False)

    formulaire = ft.Container(
        content=ft.Column([
            ft.Text("Créer un nouvel utilisateur", size=16, weight=ft.FontWeight.BOLD),
            ft.Row([champ_nom, champ_prenom], wrap=True, spacing=10),
            ft.Row([champ_email, champ_telephone], wrap=True, spacing=10),
            ft.Row([champ_password, champ_role], wrap=True, spacing=10),
            bouton_principal("Créer le compte", on_click=creer, icone=ft.icons.PERSON_ADD),
        ], spacing=10),
        bgcolor=ft.colors.SURFACE_VARIANT,
        padding=16,
        border_radius=8,
        border=ft.border.all(1, ft.colors.OUTLINE_VARIANT),
    )

    # ─── Liste des utilisateurs existants ──────────────────────────────────
    def construire_liste(utilisateurs: list) -> ft.Control:
        if not utilisateurs:
            return etat_vide("Aucun utilisateur trouvé.", ft.icons.PEOPLE_OUTLINE)

        lignes = []
        for u in utilisateurs:
            lignes.append(ft.Row([
                ft.Container(width=180, content=ft.Text(f"{u['prenom']} {u['nom']}", size=13)),
                ft.Container(width=220, content=ft.Text(u["email"], size=13, color="#6b7280")),
                ft.Container(
                    width=140,
                    content=ft.Container(
                        content=ft.Text(dict(ROLES_DISPONIBLES).get(u["role"], u["role"]), size=11, color="white"),
                        bgcolor="#3b82f6" if u["role"] == "ADMIN" else "#10b981" if u["role"] == "AGENT" else "#f59e0b" if u["role"] == "SECR" else "#6b7280",
                        padding=ft.padding.symmetric(horizontal=10, vertical=4),
                        border_radius=12,
                    ),
                ),
                ft.Icon(
                    ft.icons.CHECK_CIRCLE if u["is_active"] else ft.icons.CANCEL,
                    color="#10b981" if u["is_active"] else "#ef4444",
                    size=18,
                ),
            ], spacing=10))

        tableau = ft.Column([
            ft.Row([
                ft.Container(width=180, content=ft.Text("Nom", size=12, weight=ft.FontWeight.W_600, color="#6b7280")),
                ft.Container(width=220, content=ft.Text("Email", size=12, weight=ft.FontWeight.W_600, color="#6b7280")),
                ft.Container(width=140, content=ft.Text("Rôle", size=12, weight=ft.FontWeight.W_600, color="#6b7280")),
                ft.Text("Actif", size=12, weight=ft.FontWeight.W_600, color="#6b7280"),
            ], spacing=10),
            ft.Divider(),
            *lignes,
        ], spacing=10)

        # Défilement horizontal : les colonnes à largeur fixe (180+220+140+...)
        # dépassent la largeur d'un écran de téléphone. Plutôt que de les
        # couper (colonnes invisibles hors cadre), tout le tableau devient
        # défilable horizontalement.
        return ft.Row([tableau], scroll=ft.ScrollMode.AUTO, expand=True)

    def charger_utilisateurs():
        content_area.content = chargement("Chargement...")
        page.update()
        try:
            utilisateurs = client.liste_utilisateurs()
            content_area.content = construire_liste(utilisateurs)
        except APIError as err:
            content_area.content = etat_vide(f"Erreur : {err.detail}", ft.icons.ERROR_OUTLINE)
        page.update()

    charger_utilisateurs()

    return ft.Container(
        content=ft.Column([
            ft.Text("Gestion des utilisateurs", size=20, weight=ft.FontWeight.BOLD),
            formulaire,
            ft.Divider(),
            ft.Text("Utilisateurs existants", size=16, weight=ft.FontWeight.BOLD),
            content_area,
        ], spacing=16, expand=True, scroll=ft.ScrollMode.AUTO),
        padding=20,
        expand=True,
    )