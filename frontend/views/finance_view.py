"""
Vue Finance — Factures et paiements multi-canal
- Client : voit ses factures, peut consulter le solde
- Admin/Secrétariat : enregistre les paiements (Mobile Money, Airtel Money, Espèces, Virement)
NOUVEAU : bouton "Télécharger le PDF" sur chaque facture
"""

import flet as ft

from api_client import APIError
from components.widgets import (
    badge_generique, afficher_snackbar, chargement, etat_vide,
    bouton_principal, champ_texte, COULEURS_STATUT_FACTURE,
)
from config import COULEUR_PRIMAIRE, API_BASE_URL
from responsive import est_mobile as _est_mobile


CANAUX_PAIEMENT = [
    ("MOBILE_MONEY", "Mobile Money"),
    ("AIRTEL_MONEY", "Airtel Money"),
    ("ESPECES", "Espèces"),
    ("VIREMENT", "Virement bancaire"),
    ("CHEQUE", "Chèque"),
]


def FinanceView(page: ft.Page, client):
    content_area = ft.Container(content=chargement("Chargement des factures..."), expand=True)
    filtre_statut = ft.Dropdown(
        label="Filtrer par statut",
        width=220,
        options=[ft.dropdown.Option("", "Toutes")] + [
            ft.dropdown.Option(k, v) for k, v in {
                "BROUILLON": "Brouillon", "EMISE": "Émise",
                "PARTIEL": "Partiellement payée", "PAYEE": "Payée",
                "RETARD": "En retard", "ANNULEE": "Annulée",
            }.items()
        ],
        value="",
        on_change=lambda e: charger(),
    )

    # NOUVEAU : ouverture du PDF dans un nouvel onglet du navigateur du client.
    #
    # CORRECTIF (faille précédente) : l'ancienne version téléchargeait les
    # octets du PDF côté serveur (client.telecharger_facture_pdf), les
    # écrivait dans un fichier temporaire DU SERVEUR, puis appelait
    # webbrowser.open("file:///...") — qui essaie d'ouvrir un navigateur
    # sur le serveur Render (headless, sans interface graphique). En mode
    # Flet Web (view=ft.AppView.WEB_BROWSER), tout le code Python s'exécute
    # côté serveur : le PDF n'atteignait donc jamais le client, sans la
    # moindre erreur visible (webbrowser.open() échoue silencieusement).
    #
    # Corrigé ici en demandant au navigateur DU CLIENT (via page.launch_url,
    # qui envoie l'ordre d'ouverture au client via le websocket Flet)
    # d'ouvrir directement l'URL de l'endpoint PDF du backend. Le token
    # JWT est passé en paramètre d'URL car un lien de navigateur classique
    # ne peut pas envoyer de header Authorization (voir auth_telechargement
    # côté backend, apps/users/api.py).
    def telecharger_pdf(facture: dict):
        try:
            url = f"{API_BASE_URL}/finance/factures/{facture['id']}/pdf?token={client.access_token}"
            page.launch_url(url)
        except Exception:
            afficher_snackbar(page, "Impossible d'ouvrir le PDF.", succes=False)

    def ouvrir_dialogue_paiement(facture: dict):
        canal_dd = ft.Dropdown(
            label="Canal de paiement *",
            width=320,
            options=[ft.dropdown.Option(k, v) for k, v in CANAUX_PAIEMENT],
        )
        montant_field = champ_texte(
            "Montant (FCFA) *", width=320, keyboard_type=ft.KeyboardType.NUMBER,
            value=str(int(facture["solde_restant"])),
        )
        reference_field = champ_texte("Référence transaction (optionnel)", width=320)
        telephone_field = champ_texte("Téléphone utilisé (optionnel)", width=320)
        notes_field = champ_texte("Notes (optionnel)", width=320, multiline=True, min_lines=2)

        info_solde = ft.Text(
            f"Solde restant : {facture['solde_restant']:,.0f} FCFA / Total : {facture['montant_total']:,.0f} FCFA",
            size=12, color="#6b7280",
        )

        def enregistrer(e):
            if not canal_dd.value:
                afficher_snackbar(page, "Veuillez sélectionner un canal de paiement.", succes=False)
                return
            try:
                montant = float(montant_field.value.replace(",", "."))
            except (ValueError, AttributeError):
                afficher_snackbar(page, "Montant invalide.", succes=False)
                return
            if montant <= 0:
                afficher_snackbar(page, "Le montant doit être positif.", succes=False)
                return

            try:
                client.enregistrer_paiement(
                    facture_id=facture["id"],
                    canal=canal_dd.value,
                    montant=montant,
                    reference=reference_field.value or "",
                    telephone=telephone_field.value or "",
                    notes=notes_field.value or "",
                )
                afficher_snackbar(page, "Paiement enregistré avec succès.", succes=True)
                page.close(dlg)
                charger()
            except APIError as err:
                afficher_snackbar(page, err.detail, succes=False)

        dlg = ft.AlertDialog(
            title=ft.Text(f"Enregistrer un paiement — {facture['numero_facture']}"),
            content=ft.Container(
                content=ft.Column([
                    info_solde,
                    canal_dd, montant_field, reference_field, telephone_field, notes_field,
                ], spacing=10, tight=True),
                width=350,
            ),
            actions=[
                ft.TextButton("Annuler", on_click=lambda e: page.close(dlg)),
                ft.ElevatedButton("Enregistrer", on_click=enregistrer, bgcolor=COULEUR_PRIMAIRE, color="white"),
            ],
        )
        page.open(dlg)

    def ouvrir_dialogue_paiement_mobile(facture: dict):
        """
        Flux de paiement Mobile Money / Airtel Money en self-service.
        Étape 1 : le client choisit le canal + son numéro + le montant.
        Étape 2 : un code de confirmation est envoyé par email (simulation
        de la notification push opérateur) ; le client le saisit pour valider.
        """
        canal_dd = ft.Dropdown(
            label="Opérateur *",
            width=320,
            options=[
                ft.dropdown.Option("MOBILE_MONEY", "Mobile Money (MTN)"),
                ft.dropdown.Option("AIRTEL_MONEY", "Airtel Money"),
            ],
            value="MOBILE_MONEY",
        )
        telephone_field = champ_texte("Numéro Mobile Money *", width=320, hint_text="06 XXX XXXX")
        montant_field = champ_texte(
            "Montant (FCFA) *", width=320, keyboard_type=ft.KeyboardType.NUMBER,
            value=str(int(facture["solde_restant"])),
        )
        info_solde = ft.Text(
            f"Solde restant : {facture['solde_restant']:,.0f} FCFA", size=12, color="#6b7280",
        )

        loading = ft.ProgressRing(visible=False, width=18, height=18, stroke_width=2)

        step1 = ft.Column([info_solde, canal_dd, telephone_field, montant_field], spacing=10, tight=True)
        step2 = ft.Column(visible=False, spacing=10, tight=True)

        transaction_courante = {"data": None}

        def lancer_paiement(e):
            if not telephone_field.value:
                afficher_snackbar(page, "Veuillez saisir un numéro Mobile Money.", succes=False)
                return
            try:
                montant = float(montant_field.value.replace(",", "."))
            except (ValueError, AttributeError):
                afficher_snackbar(page, "Montant invalide.", succes=False)
                return
            if montant <= 0:
                afficher_snackbar(page, "Le montant doit être positif.", succes=False)
                return

            loading.visible = True
            page.update()
            try:
                transaction = client.initier_paiement_mobile(
                    facture_id=facture["id"], canal=canal_dd.value,
                    telephone=telephone_field.value, montant=montant,
                )
                transaction_courante["data"] = transaction

                code_field = champ_texte(
                    "Code de confirmation (6 chiffres)", width=320,
                    max_length=6, text_align=ft.TextAlign.CENTER,
                )
                info_attente = ft.Text(
                    f"Un code a été envoyé par email pour confirmer ce paiement "
                    f"{transaction['canal_libelle']} de {transaction['montant']:,.0f} FCFA.\n"
                    f"Réf. : {transaction['reference']}\n"
                    f"Valide 5 minutes.",
                    size=12, color="#6b7280",
                )

                def confirmer(e2):
                    if not code_field.value or len(code_field.value) != 6:
                        afficher_snackbar(page, "Le code doit contenir 6 chiffres.", succes=False)
                        return
                    loading.visible = True
                    page.update()
                    try:
                        resultat = client.confirmer_paiement_mobile(
                            transaction_courante["data"]["id"], code_field.value
                        )
                        if resultat["succes"]:
                            afficher_snackbar(page, "Paiement confirmé avec succès !", succes=True)
                            page.close(dlg)
                            charger()
                        else:
                            afficher_snackbar(page, resultat["detail"], succes=False)
                            code_field.value = ""
                    except APIError as err:
                        afficher_snackbar(page, err.detail, succes=False)
                    finally:
                        loading.visible = False
                        page.update()

                step2.controls = [
                    ft.Icon(ft.icons.PHONE_ANDROID, size=40, color=COULEUR_PRIMAIRE),
                    info_attente,
                    code_field,
                    ft.ElevatedButton(
                        "Confirmer le paiement", icon=ft.icons.CHECK_CIRCLE,
                        bgcolor=COULEUR_PRIMAIRE, color="white",
                        on_click=confirmer,
                    ),
                ]
                step1.visible = False
                step2.visible = True

            except APIError as err:
                afficher_snackbar(page, err.detail, succes=False)
            finally:
                loading.visible = False
                page.update()

        dlg = ft.AlertDialog(
            title=ft.Row([
                ft.Icon(ft.icons.PHONE_ANDROID, color=COULEUR_PRIMAIRE),
                ft.Text("Paiement Mobile Money / Airtel"),
            ]),
            content=ft.Container(
                content=ft.Column([step1, step2, loading], spacing=14, tight=True),
                width=350,
            ),
            actions=[
                ft.TextButton("Annuler", on_click=lambda e: page.close(dlg)),
                ft.ElevatedButton(
                    "Lancer le paiement", on_click=lancer_paiement,
                    bgcolor=COULEUR_PRIMAIRE, color="white",
                ),
            ],
        )
        page.open(dlg)

    def ouvrir_detail_facture(facture_resume: dict):
        try:
            facture = client.detail_facture(facture_resume["id"])
        except APIError as err:
            afficher_snackbar(page, err.detail, succes=False)
            return

        lignes_rows = [
            ft.Row([
                ft.Text(l["description"], size=12, expand=True),
                ft.Text(f"{l['quantite']} x {l['prix_unitaire']:,.0f}", size=12),
                ft.Text(f"{l['montant_total']:,.0f} FCFA", size=12, weight=ft.FontWeight.W_600),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
            for l in facture["lignes"]
        ]

        paiements_rows = [
            ft.Row([
                ft.Text(p["canal_libelle"], size=12, expand=True),
                ft.Text(p["date_paiement"][:10], size=11, color="#6b7280"),
                ft.Text(f"{p['montant']:,.0f} FCFA", size=12, weight=ft.FontWeight.W_600, color="#22c55e"),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
            for p in facture["paiements"]
        ] or [ft.Text("Aucun paiement enregistré.", size=12, color="#9ca3af")]

        actions = []

        # NOUVEAU : bouton téléchargement PDF, toujours visible
        actions.append(
            ft.OutlinedButton(
                "Télécharger le PDF", icon=ft.icons.PICTURE_AS_PDF,
                on_click=lambda e: telecharger_pdf(facture),
            )
        )

        # Paiement self-service Mobile Money / Airtel : accessible au client
        # lui-même (et au staff, pour un paiement assisté au guichet).
        if facture["statut"] not in ("PAYEE", "ANNULEE", "BROUILLON"):
            actions.append(
                ft.ElevatedButton(
                    "Payer via Mobile Money", icon=ft.icons.PHONE_ANDROID,
                    bgcolor="#16a34a", color="white",
                    on_click=lambda e: (page.close(dlg), ouvrir_dialogue_paiement_mobile(facture)),
                )
            )
        if client.can_see_finance and facture["statut"] not in ("PAYEE", "ANNULEE", "BROUILLON"):
            actions.append(
                ft.ElevatedButton(
                    "Enregistrer un paiement manuel", icon=ft.icons.PAYMENTS,
                    bgcolor=COULEUR_PRIMAIRE, color="white",
                    on_click=lambda e: (page.close(dlg), ouvrir_dialogue_paiement(facture)),
                )
            )

        dlg = ft.AlertDialog(
            title=ft.Text(f"Facture {facture['numero_facture']}"),
            content=ft.Container(
                content=ft.Column([
                    ft.Text(f"Client : {facture['client_nom']}", size=13),
                    ft.Divider(),
                    ft.Text("Détail", size=13, weight=ft.FontWeight.W_600),
                    *lignes_rows,
                    ft.Divider(),
                    ft.Row([ft.Text("Sous-total", size=12), ft.Text(f"{facture['sous_total']:,.0f} FCFA", size=12)],
                           alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Row([ft.Text("TOTAL", weight=ft.FontWeight.BOLD), ft.Text(f"{facture['montant_total']:,.0f} FCFA", weight=ft.FontWeight.BOLD)],
                           alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Row([ft.Text("Payé", size=12, color="#22c55e"), ft.Text(f"{facture['montant_paye']:,.0f} FCFA", size=12, color="#22c55e")],
                           alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Row([ft.Text("Solde restant", size=12, color="#ef4444"), ft.Text(f"{facture['solde_restant']:,.0f} FCFA", size=12, color="#ef4444", weight=ft.FontWeight.BOLD)],
                           alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Divider(),
                    ft.Text("Historique des paiements", size=13, weight=ft.FontWeight.W_600),
                    *paiements_rows,
                ], spacing=8, tight=True, scroll=ft.ScrollMode.AUTO),
                width=380, height=420,
            ),
            actions=actions + [ft.TextButton("Fermer", on_click=lambda e: page.close(dlg))],
        )
        page.open(dlg)

    def construire_carte_facture(f: dict) -> ft.Container:
        couleur = COULEURS_STATUT_FACTURE.get(f["statut"], "#9ca3af")

        # Barre de progression du paiement
        ratio = f["montant_paye"] / f["montant_total"] if f["montant_total"] > 0 else 0

        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text(f["numero_facture"], weight=ft.FontWeight.BOLD, size=15),
                    badge_generique(f["statut_libelle"], couleur),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Text(f"Client : {f['client_nom']}", size=12, color="#6b7280") if client.can_see_finance else ft.Container(),
                ft.Row([
                    ft.Text(f"Total : {f['montant_total']:,.0f} FCFA", size=13),
                    ft.Text(f"Payé : {f['montant_paye']:,.0f} FCFA", size=13, color="#22c55e"),
                    ft.Text(f"Restant : {f['solde_restant']:,.0f} FCFA", size=13,
                            color="#ef4444" if f["solde_restant"] > 0 else "#22c55e"),
                ], spacing=16, wrap=True, run_spacing=4),
                ft.ProgressBar(value=ratio, color="#22c55e", bgcolor="#e5e7eb", height=6, border_radius=4),
                ft.Row([
                    ft.Text(f"Émise le {f['date_emission'][:10]}"
                            + (f" — Échéance : {f['date_echeance']}" if f.get("date_echeance") else ""),
                            size=11, color="#9ca3af"),
                    ft.Container(expand=True),
                    # NOUVEAU : téléchargement direct depuis la carte
                    ft.IconButton(
                        ft.icons.PICTURE_AS_PDF, tooltip="Télécharger le PDF",
                        on_click=lambda e, fact=f: telecharger_pdf(fact),
                    ),
                    ft.TextButton("Voir détail", icon=ft.icons.VISIBILITY,
                                   on_click=lambda e, fact=f: ouvrir_detail_facture(fact)),
                ], wrap=True, run_spacing=4),
            ], spacing=8),
            bgcolor=ft.colors.SURFACE, padding=14, border_radius=10, border=ft.border.all(1, ft.colors.OUTLINE_VARIANT),
        )

    def charger():
        content_area.content = chargement("Chargement des factures...")
        page.update()
        try:
            factures = client.liste_factures(statut=filtre_statut.value or None)
            if not factures:
                content_area.content = etat_vide("Aucune facture trouvée.", ft.icons.RECEIPT_LONG)
            else:
                content_area.content = ft.Column(
                    [construire_carte_facture(f) for f in factures],
                    spacing=10, scroll=ft.ScrollMode.AUTO, expand=True,
                )
        except APIError as err:
            content_area.content = etat_vide(f"Erreur : {err.detail}", ft.icons.ERROR_OUTLINE)
        page.update()

    charger()

    titre = "Mes factures" if not client.can_see_finance else "Gestion financière"
    mobile = _est_mobile(page)
    filtre_statut.width = 220 if not mobile else None
    filtre_statut.expand = mobile

    return ft.Container(
        content=ft.Column([
            ft.Row(
                [
                    ft.Text(titre, size=20, weight=ft.FontWeight.BOLD),
                    ft.Container(expand=True) if not mobile else ft.Container(width=0),
                    filtre_statut,
                    ft.IconButton(ft.icons.REFRESH, on_click=lambda e: charger(), tooltip="Actualiser"),
                ],
                wrap=True,
                run_spacing=8,
            ),
            ft.Divider(),
            content_area,
        ], spacing=10, expand=True),
        padding=20, expand=True,
    )
