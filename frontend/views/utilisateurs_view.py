"""
Vue Gestion des Utilisateurs — Admin uniquement
Liste des comptes existants + création avec choix du rôle (RBAC)
"""

import flet as ft
from api_client import APIError
from components.widgets import afficher_snackbar, chargement, etat_vide, bouton_principal, carte_premium
from config import couleurs
from responsive import est_mobile as _est_mobile

ROLES_DISPONIBLES = [
    ("ADMIN", "Administrateur"),
    ("AGENT", "Agent de terrain"),
    ("SECR", "Secrétariat"),
    ("CLIENT", "Client"),
]

COULEUR_ROLE = {
    "ADMIN": "#3b82f6", "AGENT": "#10b981", "SECR": "#f59e0b", "CLIENT": "#6b7280",
}


def UtilisateursView(page: ft.Page, client):
    mobile = _est_mobile(page)
    t = couleurs(page)
    content_area = ft.Container(content=chargement("Chargement des utilisateurs..."), expand=True)

    if not client.is_admin:
        return ft.Container(
            content=etat_vide("Accès réservé aux administrateurs.", ft.icons.LOCK_OUTLINE),
            padding=20,
            expand=True,
        )

    # ─── Formulaire de création ────────────────────────────────────────────
    # Chaque champ est dans un Row(wrap=True) : sur mobile, ils passent
    # naturellement à la ligne sans jamais déborder de l'écran.
    champ_email = ft.TextField(label="Email", expand=True)
    champ_password = ft.TextField(label="Mot de passe", expand=True, password=True, can_reveal_password=True)
    champ_nom = ft.TextField(label="Nom", expand=True)
    champ_prenom = ft.TextField(label="Prénom", expand=True)
    champ_telephone = ft.TextField(label="Téléphone", expand=True)
    champ_role = ft.Dropdown(
        label="Rôle",
        expand=True,
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

    # Sur mobile, un champ par ligne (col 12) ; sur desktop, deux par ligne.
    formulaire = carte_premium(page, ft.Column([
        ft.Text("Créer un nouvel utilisateur", size=16, weight=ft.FontWeight.BOLD, color=t["texte"]),
        ft.ResponsiveRow([
            ft.Container(champ_nom, col={"xs": 12, "sm": 6}),
            ft.Container(champ_prenom, col={"xs": 12, "sm": 6}),
            ft.Container(champ_email, col={"xs": 12, "sm": 6}),
            ft.Container(champ_telephone, col={"xs": 12, "sm": 6}),
            ft.Container(champ_password, col={"xs": 12, "sm": 6}),
            ft.Container(champ_role, col={"xs": 12, "sm": 6}),
        ], spacing=10, run_spacing=10),
        bouton_principal("Créer le compte", on_click=creer, icone=ft.icons.PERSON_ADD),
    ], spacing=10))

    # ─── Liste des utilisateurs existants ──────────────────────────────────

    def carte_utilisateur_mobile(u: dict) -> ft.Container:
        """Une carte par utilisateur — plus lisible qu'un tableau sur petit écran."""
        couleur_role = COULEUR_ROLE.get(u["role"], "#6b7280")
        return carte_premium(page, ft.Column([
            ft.Row([
                ft.Text(f"{u['prenom']} {u['nom']}", size=14, weight=ft.FontWeight.W_600, color=t["texte"]),
                ft.Container(expand=True),
                ft.Icon(
                    ft.icons.CHECK_CIRCLE if u["is_active"] else ft.icons.CANCEL,
                    color="#10b981" if u["is_active"] else "#ef4444", size=18,
                ),
            ]),
            ft.Text(u["email"], size=12, color=t["texte_att"]),
            ft.Container(
                content=ft.Text(dict(ROLES_DISPONIBLES).get(u["role"], u["role"]), size=11, color="white"),
                bgcolor=couleur_role,
                padding=ft.padding.symmetric(horizontal=10, vertical=4),
                border_radius=12,
            ),
        ], spacing=6), padding=14)

    def ligne_utilisateur_desktop(u: dict) -> ft.Row:
        couleur_role = COULEUR_ROLE.get(u["role"], "#6b7280")
        return ft.Row([
            ft.Container(width=180, content=ft.Text(f"{u['prenom']} {u['nom']}", size=13, color=t["texte"])),
            ft.Container(width=220, content=ft.Text(u["email"], size=13, color=t["texte_att"])),
            ft.Container(
                width=140,
                content=ft.Container(
                    content=ft.Text(dict(ROLES_DISPONIBLES).get(u["role"], u["role"]), size=11, color="white"),
                    bgcolor=couleur_role,
                    padding=ft.padding.symmetric(horizontal=10, vertical=4),
                    border_radius=12,
                ),
            ),
            ft.Icon(
                ft.icons.CHECK_CIRCLE if u["is_active"] else ft.icons.CANCEL,
                color="#10b981" if u["is_active"] else "#ef4444", size=18,
            ),
        ], spacing=10)

    def construire_liste(utilisateurs: list) -> ft.Control:
        if not utilisateurs:
            return etat_vide("Aucun utilisateur trouvé.", ft.icons.PEOPLE_OUTLINE)

        if mobile:
            return ft.Column(
                [carte_utilisateur_mobile(u) for u in utilisateurs],
                spacing=10, scroll=ft.ScrollMode.AUTO, expand=True,
            )

        return ft.Column([
            ft.Row([
                ft.Container(width=180, content=ft.Text("Nom", size=12, weight=ft.FontWeight.W_600, color=t["texte_att"])),
                ft.Container(width=220, content=ft.Text("Email", size=12, weight=ft.FontWeight.W_600, color=t["texte_att"])),
                ft.Container(width=140, content=ft.Text("Rôle", size=12, weight=ft.FontWeight.W_600, color=t["texte_att"])),
                ft.Text("Actif", size=12, weight=ft.FontWeight.W_600, color=t["texte_att"]),
            ], spacing=10),
            ft.Divider(color=t["bordure"]),
            *[ligne_utilisateur_desktop(u) for u in utilisateurs],
        ], spacing=10, scroll=ft.ScrollMode.AUTO, expand=True)

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
            ft.Text("Gestion des utilisateurs", size=17 if mobile else 20, weight=ft.FontWeight.BOLD, color=t["texte"]),
            formulaire,
            ft.Divider(color=t["bordure"]),
            ft.Text("Utilisateurs existants", size=16, weight=ft.FontWeight.BOLD, color=t["texte"]),
            content_area,
        ], spacing=16, expand=True, scroll=ft.ScrollMode.AUTO),
        padding=12 if mobile else 20,
        expand=True,
    )
