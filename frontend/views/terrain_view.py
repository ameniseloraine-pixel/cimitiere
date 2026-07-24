"""
Vue Terrain — Gestion du terrain par l'Admin / Agent
Cimetière → Zones → Blocs → Génération automatique des caveaux
"""

import flet as ft
from api_client import APIError
from components.widgets import (
    champ_texte, bouton_principal, afficher_snackbar,
    chargement, etat_vide, badge_generique,
)
from config import COULEUR_PRIMAIRE


TYPE_ZONE_OPTIONS = [
    ("EXPLOIT", "Exploitable"),
    ("CHEMIN", "Chemin / Allée"),
    ("TECH", "Zone technique"),
    ("ADMIN", "Zone administrative"),
    ("NON_EXP", "Non exploitable"),
]

COULEUR_TYPE_ZONE = {
    "EXPLOIT": "#22c55e",
    "CHEMIN": "#f97316",
    "TECH": "#6b7280",
    "ADMIN": "#3b82f6",
    "NON_EXP": "#9ca3af",
}


def TerrainView(page: ft.Page, client):
    """Vue principale du module Terrain (Admin/Agent uniquement)."""

    # ─── État partagé ─────────────────────────────────────────────────────────
    state = {
        "cimetiere": None,   # cimetière actif sélectionné
        "zones": [],
        "zone_selectionnee": None,
        "blocs": [],
    }

    # ─── Zones de contenu ──────────────────────────────────────────────────────
    zone_cimetiere = ft.Container()
    zone_zones = ft.Container(visible=False, expand=True)
    zone_blocs = ft.Container(visible=False, expand=True)

    # ═══════════════════════════════════════════════════════════════════════════
    # SECTION CIMETIÈRE
    # ═══════════════════════════════════════════════════════════════════════════

    def ouvrir_dialogue_cimetiere(cimetiere=None):
        """Créer ou modifier un cimetière."""
        est_modif = cimetiere is not None
        titre = "Modifier le cimetière" if est_modif else "Créer un cimetière"

        nom_f = champ_texte("Nom du cimetière *", width=350, value=cimetiere["nom"] if est_modif else "")
        adresse_f = champ_texte("Adresse *", width=350, value=cimetiere["adresse"] if est_modif else "", multiline=True, min_lines=2)
        ville_f = champ_texte("Ville *", width=350, value=cimetiere["ville"] if est_modif else "")
        superficie_f = champ_texte("Superficie totale (m²) *", width=350,
                                   keyboard_type=ft.KeyboardType.NUMBER,
                                   value=str(int(cimetiere["superficie_totale_m2"])) if est_modif else "")
        longueur_f = champ_texte("Longueur standard tombeau (m)", width=170,
                                  keyboard_type=ft.KeyboardType.NUMBER,
                                  value=str(cimetiere["tombeau_longueur_m"]) if est_modif else "2.5")
        largeur_f = champ_texte("Largeur standard tombeau (m)", width=170,
                                 keyboard_type=ft.KeyboardType.NUMBER,
                                 value=str(cimetiere["tombeau_largeur_m"]) if est_modif else "1.2")
        pct_f = champ_texte("% chemins/non-exploitable (estimation initiale)", width=350,
                             keyboard_type=ft.KeyboardType.NUMBER,
                             value=str(cimetiere["pourcentage_chemins"]) if est_modif else "20",
                             helper_text="Ce % est utilisé avant la création des zones. Les zones prennent ensuite le relais.")
        tel_f = champ_texte("Téléphone", width=350, value=cimetiere.get("telephone", "") if est_modif else "")
        email_f = champ_texte("Email contact", width=350, value=cimetiere.get("email_contact", "") if est_modif else "")

        def sauvegarder(e):
            if not nom_f.value or not adresse_f.value or not ville_f.value or not superficie_f.value:
                afficher_snackbar(page, "Les champs marqués * sont obligatoires.", succes=False)
                return
            try:
                payload = {
                    "nom": nom_f.value.strip(),
                    "adresse": adresse_f.value.strip(),
                    "ville": ville_f.value.strip(),
                    "superficie_totale_m2": float(superficie_f.value),
                    "tombeau_longueur_m": float(longueur_f.value or 2.5),
                    "tombeau_largeur_m": float(largeur_f.value or 1.2),
                    "pourcentage_chemins": float(pct_f.value or 20),
                    "telephone": tel_f.value.strip(),
                    "email_contact": email_f.value.strip(),
                }
            except ValueError:
                afficher_snackbar(page, "Valeur numérique invalide.", succes=False)
                return

            try:
                if est_modif:
                    result = client._request("PUT", f"/terrain/cimetiere/{cimetiere['id']}", json=payload)
                    afficher_snackbar(page, "Cimetière mis à jour.", succes=True)
                else:
                    result = client._request("POST", "/terrain/cimetiere", json=payload)
                    afficher_snackbar(page, f"Cimetière « {result['nom']} » créé.", succes=True)
                page.close(dlg)
                charger_cimetieres()
            except APIError as err:
                afficher_snackbar(page, err.detail, succes=False)

        dlg = ft.AlertDialog(
            title=ft.Text(titre),
            content=ft.Container(
                content=ft.Column([
                    nom_f, adresse_f, ville_f,
                    ft.Text("Dimensions standard des tombeaux", size=13, weight=ft.FontWeight.W_600),
                    ft.Row([longueur_f, largeur_f], spacing=10),
                    superficie_f, pct_f, tel_f, email_f,
                ], spacing=10, scroll=ft.ScrollMode.AUTO, tight=True),
                width=380, height=480,
            ),
            actions=[
                ft.TextButton("Annuler", on_click=lambda e: page.close(dlg)),
                ft.ElevatedButton("Enregistrer", on_click=sauvegarder,
                                  bgcolor=COULEUR_PRIMAIRE, color="white"),
            ],
        )
        page.open(dlg)

    def construire_carte_cimetiere(c: dict) -> ft.Container:
        a_zones = c.get("calcul_base_sur_zones", False)
        surface_info = (
            f"Surface exploitable : {c['superficie_zones_exploitables_m2']:,.0f} m² (zones réelles)"
            if a_zones
            else f"Surface exploitable estimée : {c['surface_exploitable_m2']:,.0f} m² (forfait {c['pourcentage_chemins']}%)"
        )

        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text(c["nom"], size=17, weight=ft.FontWeight.BOLD),
                    ft.Container(expand=True),
                    ft.IconButton(ft.icons.EDIT, tooltip="Modifier",
                                  on_click=lambda e, cim=c: ouvrir_dialogue_cimetiere(cim)),
                ]),
                ft.Text(f"{c['adresse']}, {c['ville']}", size=13, color="#6b7280"),
                ft.Divider(),
                ft.Row([
                    _stat("Superficie totale", f"{c['superficie_totale_m2']:,.0f} m²"),
                    _stat("Tombeau standard", f"{c['tombeau_longueur_m']}m × {c['tombeau_largeur_m']}m"),
                    _stat("Capacité théorique", f"{c['capacite_theorique_totale']:,} places"),
                ], spacing=16, wrap=True),
                ft.Text(surface_info, size=12, color="#16a34a" if a_zones else "#6b7280"),
                ft.Divider(),
                ft.Row([
                    bouton_principal(
                        "Gérer les zones",
                        on_click=lambda e, cim=c: selectionner_cimetiere(cim),
                        icone=ft.icons.GRID_VIEW,
                    ),
                ]),
            ], spacing=8),
            bgcolor=ft.colors.SURFACE, padding=16, border_radius=12,
            border=ft.border.all(1, "#e5e7eb"),
        )

    def charger_cimetieres():
        zone_cimetiere.content = chargement("Chargement...")
        zone_zones.visible = False
        zone_blocs.visible = False
        page.update()
        try:
            cimetieres = client.liste_cimetieres()
            if not cimetieres:
                zone_cimetiere.content = ft.Column([
                    etat_vide("Aucun cimetière configuré.", ft.icons.LOCATION_CITY),
                    ft.Container(height=10),
                    bouton_principal("Créer le cimetière", on_click=lambda e: ouvrir_dialogue_cimetiere(),
                                     icone=ft.icons.ADD),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)
            else:
                zone_cimetiere.content = ft.Column([
                    ft.Row([
                        ft.Text(f"{len(cimetieres)} cimetière(s) configuré(s)",
                                size=13, color="#6b7280"),
                        ft.Container(expand=True),
                        ft.ElevatedButton("+ Nouveau cimetière", icon=ft.icons.ADD,
                                          on_click=lambda e: ouvrir_dialogue_cimetiere()),
                    ]),
                    *[construire_carte_cimetiere(c) for c in cimetieres],
                ], spacing=12)
        except APIError as err:
            zone_cimetiere.content = etat_vide(f"Erreur : {err.detail}", ft.icons.ERROR_OUTLINE)
        page.update()

    # ═══════════════════════════════════════════════════════════════════════════
    # SECTION ZONES
    # ═══════════════════════════════════════════════════════════════════════════

    def selectionner_cimetiere(cimetiere: dict):
        state["cimetiere"] = cimetiere
        charger_zones()

    def ouvrir_dialogue_zone(zone=None):
        est_modif = zone is not None
        nom_f = champ_texte("Nom de la zone *", width=320, value=zone["nom"] if est_modif else "")
        code_f = champ_texte("Code (ex: A, B, C) *", width=150, value=zone["code"] if est_modif else "")
        superficie_f = champ_texte("Superficie (m²) *", width=150,
                                    keyboard_type=ft.KeyboardType.NUMBER,
                                    value=str(int(zone["superficie_m2"])) if est_modif else "")
        type_dd = ft.Dropdown(
            label="Type de zone *", width=320,
            options=[ft.dropdown.Option(k, v) for k, v in TYPE_ZONE_OPTIONS],
            value=zone["type_zone"] if est_modif else "EXPLOIT",
        )
        description_f = champ_texte("Description", width=320,
                                     value=zone.get("description", "") if est_modif else "",
                                     multiline=True, min_lines=2)

        def sauvegarder(e):
            if not nom_f.value or not code_f.value or not superficie_f.value:
                afficher_snackbar(page, "Les champs * sont obligatoires.", succes=False)
                return
            try:
                payload = {
                    "nom": nom_f.value.strip(),
                    "code": code_f.value.strip().upper(),
                    "type_zone": type_dd.value,
                    "superficie_m2": float(superficie_f.value),
                    "description": description_f.value.strip(),
                    "ordre_affichage": 0,
                }
            except ValueError:
                afficher_snackbar(page, "Superficie invalide.", succes=False)
                return
            try:
                if est_modif:
                    # Pas d'endpoint PUT zone dans l'API — on le supprime et recrée
                    # (zone sans caveaux, uniquement en configuration initiale)
                    afficher_snackbar(page, "Modification non disponible — supprimez et recréez la zone.", succes=False)
                    page.close(dlg)
                    return
                cim_id = state["cimetiere"]["id"]
                client._request("POST", f"/terrain/cimetiere/{cim_id}/zones", json=payload)
                afficher_snackbar(page, f"Zone {payload['code']} créée.", succes=True)
                page.close(dlg)
                charger_zones()
            except APIError as err:
                afficher_snackbar(page, err.detail, succes=False)

        dlg = ft.AlertDialog(
            title=ft.Text("Créer une zone"),
            content=ft.Container(
                content=ft.Column([
                    ft.Row([code_f, superficie_f], spacing=10),
                    nom_f, type_dd, description_f,
                    ft.Container(
                        content=ft.Text(
                            "ℹ️ Les zones 'Non exploitable' et 'Chemin/Allée' sont déduites "
                            "de la surface disponible pour les caveaux.",
                            size=11, color="#6b7280",
                        ),
                        bgcolor="#f0f9ff", padding=8, border_radius=6,
                    ),
                ], spacing=10, tight=True),
                width=350,
            ),
            actions=[
                ft.TextButton("Annuler", on_click=lambda e: page.close(dlg)),
                ft.ElevatedButton("Créer", on_click=sauvegarder, bgcolor=COULEUR_PRIMAIRE, color="white"),
            ],
        )
        page.open(dlg)

    def supprimer_zone(zone: dict):
        def confirmer(e):
            try:
                client._request("DELETE", f"/terrain/zones/{zone['id']}")
                afficher_snackbar(page, f"Zone {zone['code']} supprimée.", succes=True)
                page.close(dlg)
                charger_zones()
            except APIError as err:
                afficher_snackbar(page, err.detail, succes=False)
                page.close(dlg)

        dlg = ft.AlertDialog(
            title=ft.Text(f"Supprimer la zone {zone['code']} ?"),
            content=ft.Text(f"Cette action est irréversible.\n"
                            f"Impossible si des caveaux occupés existent dans cette zone."),
            actions=[
                ft.TextButton("Annuler", on_click=lambda e: page.close(dlg)),
                ft.ElevatedButton("Supprimer", on_click=confirmer, bgcolor="#ef4444", color="white"),
            ],
        )
        page.open(dlg)

    def construire_carte_zone(z: dict) -> ft.Container:
        couleur = COULEUR_TYPE_ZONE.get(z["type_zone"], "#9ca3af")
        libelle_type = dict(TYPE_ZONE_OPTIONS).get(z["type_zone"], z["type_zone"])

        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Container(
                        content=ft.Text(z["code"], color="white", size=13, weight=ft.FontWeight.BOLD),
                        bgcolor=couleur, width=40, height=40,
                        border_radius=8, alignment=ft.alignment.center,
                    ),
                    ft.Column([
                        ft.Row([
                            ft.Text(z["nom"], weight=ft.FontWeight.W_600),
                            badge_generique(libelle_type, couleur),
                        ], spacing=8, wrap=True),
                        ft.Text(
                            f"{z['superficie_m2']:,.0f} m² — {z['nombre_blocs']} bloc(s)",
                            size=12, color="#6b7280",
                        ),
                    ], spacing=4, expand=True),
                ], spacing=12),
                # Bouton pleine largeur, toujours visible (ne peut pas être
                # poussé hors écran comme des icônes alignées à droite).
                ft.Row([
                    ft.OutlinedButton(
                        "Voir les blocs de cette zone",
                        icon=ft.icons.TABLE_CHART,
                        on_click=lambda e, zone=z: selectionner_zone(zone),
                        expand=True,
                    ),
                    ft.IconButton(ft.icons.DELETE_OUTLINE,
                                  tooltip="Supprimer",
                                  on_click=lambda e, zone=z: supprimer_zone(zone)),
                ], spacing=4),
            ], spacing=10),
            bgcolor=ft.colors.SURFACE, padding=12, border_radius=10,
            border=ft.border.all(1, "#e5e7eb"),
        )

    def charger_zones():
        zone_zones.visible = True
        zone_zones.content = chargement("Chargement des zones...")
        zone_blocs.visible = False
        page.update()

        cim = state["cimetiere"]
        try:
            zones = client.liste_zones(cim["id"])
            state["zones"] = zones

            # Calcul de la répartition des surfaces
            surface_exploit = sum(z["superficie_m2"] for z in zones if z["type_zone"] == "EXPLOIT")
            surface_non_exploit = sum(z["superficie_m2"] for z in zones
                                      if z["type_zone"] in ("NON_EXP", "CHEMIN", "TECH", "ADMIN"))
            total_zones = sum(z["superficie_m2"] for z in zones)

            info_calcul = ft.Container(
                content=ft.Column([
                    ft.Text("Répartition des surfaces (basée sur les zones réelles)",
                            size=13, weight=ft.FontWeight.W_600),
                    ft.Row([
                        _stat("Surface exploitable", f"{surface_exploit:,.0f} m²"),
                        _stat("Non exploitable", f"{surface_non_exploit:,.0f} m²"),
                        _stat("Total zones créées", f"{total_zones:,.0f} / {cim['superficie_totale_m2']:,.0f} m²"),
                    ], spacing=16, wrap=True),
                    ft.ProgressBar(
                        value=surface_exploit / cim["superficie_totale_m2"] if cim["superficie_totale_m2"] > 0 else 0,
                        color="#22c55e", bgcolor="#e5e7eb", height=8, border_radius=4,
                    ),
                    ft.Text(
                        f"Capacité calculée : {cim['capacite_theorique_totale']:,} caveaux "
                        f"({'zones réelles' if zones else 'estimation forfaitaire'})",
                        size=12, color="#16a34a",
                    ),
                ], spacing=6),
                bgcolor="#f0fdf4", padding=14, border_radius=10,
                border=ft.border.all(1, "#bbf7d0"),
            )

            contenu_zones = ft.Column([
                ft.Row([
                    ft.Row([
                        ft.IconButton(ft.icons.ARROW_BACK, on_click=lambda e: retour_cimetiere(),
                                      tooltip="Retour"),
                        ft.Text(f"Zones — {cim['nom']}", size=16, weight=ft.FontWeight.BOLD),
                    ]),
                    ft.Container(expand=True),
                    ft.ElevatedButton("+ Nouvelle zone", icon=ft.icons.ADD,
                                      on_click=lambda e: ouvrir_dialogue_zone()),
                ]),
                info_calcul,
                ft.Divider(),
                *([construire_carte_zone(z) for z in zones]
                  if zones else [etat_vide("Aucune zone créée.", ft.icons.GRID_VIEW)]),
            ], spacing=10)

            zone_zones.content = contenu_zones
        except APIError as err:
            zone_zones.content = etat_vide(f"Erreur : {err.detail}", ft.icons.ERROR_OUTLINE)
        page.update()

    def retour_cimetiere():
        zone_zones.visible = False
        zone_blocs.visible = False
        charger_cimetieres()

    # ═══════════════════════════════════════════════════════════════════════════
    # SECTION BLOCS + GÉNÉRATION DES CAVEAUX
    # ═══════════════════════════════════════════════════════════════════════════

    def selectionner_zone(zone: dict):
        state["zone_selectionnee"] = zone
        charger_blocs()

    def ouvrir_dialogue_bloc(bloc=None):
        est_modif = bloc is not None
        nom_f = champ_texte("Nom du bloc *", width=300,
                            value=bloc["nom"] if est_modif else "")
        code_f = champ_texte("Code (ex: B1, B2) *", width=140,
                             value=bloc["code"] if est_modif else "")
        rangees_f = champ_texte("Nombre de rangées *", width=140,
                                keyboard_type=ft.KeyboardType.NUMBER,
                                value=str(bloc["nombre_rangees"]) if est_modif else "5")
        colonnes_f = champ_texte("Nombre de colonnes *", width=140,
                                  keyboard_type=ft.KeyboardType.NUMBER,
                                  value=str(bloc["nombre_colonnes"]) if est_modif else "4")

        def sauvegarder(e):
            if not nom_f.value or not code_f.value:
                afficher_snackbar(page, "Nom et code obligatoires.", succes=False)
                return
            try:
                payload = {
                    "nom": nom_f.value.strip(),
                    "code": code_f.value.strip().upper(),
                    "nombre_rangees": int(rangees_f.value or 5),
                    "nombre_colonnes": int(colonnes_f.value or 4),
                }
            except ValueError:
                afficher_snackbar(page, "Valeur numérique invalide.", succes=False)
                return
            capacite = payload["nombre_rangees"] * payload["nombre_colonnes"]
            try:
                zone_id = state["zone_selectionnee"]["id"]
                client._request("POST", f"/terrain/zones/{zone_id}/blocs", json=payload)
                afficher_snackbar(page, f"Bloc {payload['code']} créé ({capacite} caveaux théoriques).", succes=True)
                page.close(dlg)
                charger_blocs()
            except APIError as err:
                afficher_snackbar(page, err.detail, succes=False)

        dlg = ft.AlertDialog(
            title=ft.Text("Créer un bloc"),
            content=ft.Container(
                content=ft.Column([
                    ft.Row([code_f], spacing=10),
                    nom_f,
                    ft.Text("Grille de caveaux", size=13, weight=ft.FontWeight.W_600),
                    ft.Row([rangees_f, colonnes_f], spacing=10),
                    ft.Text(
                        "La génération automatique crée un caveau pour chaque cellule de la grille.",
                        size=11, color="#6b7280",
                    ),
                ], spacing=10, tight=True),
                width=330,
            ),
            actions=[
                ft.TextButton("Annuler", on_click=lambda e: page.close(dlg)),
                ft.ElevatedButton("Créer", on_click=sauvegarder, bgcolor=COULEUR_PRIMAIRE, color="white"),
            ],
        )
        page.open(dlg)

    def ouvrir_dialogue_generation(bloc: dict):
        lat_f = champ_texte("Latitude origine GPS", width=200,
                             keyboard_type=ft.KeyboardType.NUMBER, value="0.0")
        lon_f = champ_texte("Longitude origine GPS", width=200,
                             keyboard_type=ft.KeyboardType.NUMBER, value="0.0")
        esp_f = champ_texte("Espacement entre caveaux (m)", width=200,
                             keyboard_type=ft.KeyboardType.NUMBER, value="0.5")

        def generer(e):
            try:
                lat = float(lat_f.value or 0)
                lon = float(lon_f.value or 0)
                esp = float(esp_f.value or 0.5)
            except ValueError:
                afficher_snackbar(page, "Valeurs numériques invalides.", succes=False)
                return
            try:
                result = client._request(
                    "POST",
                    f"/terrain/blocs/{bloc['id']}/generer-caveaux",
                    params={"latitude_origine": lat, "longitude_origine": lon, "espacement_m": esp},
                )
                afficher_snackbar(page, result["message"], succes=True)
                page.close(dlg)
                charger_blocs()
            except APIError as err:
                afficher_snackbar(page, err.detail, succes=False)

        dlg = ft.AlertDialog(
            title=ft.Text(f"Générer les caveaux — Bloc {bloc['code']}"),
            content=ft.Container(
                content=ft.Column([
                    ft.Text(
                        f"Ceci va créer {bloc['capacite_theorique']} caveaux "
                        f"({bloc['nombre_rangees']} rangées × {bloc['nombre_colonnes']} colonnes).",
                        size=13,
                    ),
                    ft.Text(
                        "Les coordonnées GPS permettent de positionner les caveaux sur la carte.",
                        size=11, color="#6b7280",
                    ),
                    ft.Row([lat_f, lon_f], spacing=10),
                    esp_f,
                ], spacing=10, tight=True),
                width=360,
            ),
            actions=[
                ft.TextButton("Annuler", on_click=lambda e: page.close(dlg)),
                ft.ElevatedButton(
                    f"Générer {bloc['capacite_theorique']} caveaux",
                    on_click=generer, bgcolor="#16a34a", color="white",
                ),
            ],
        )
        page.open(dlg)

    def construire_carte_bloc(b: dict) -> ft.Container:
        a_caveaux = b["nombre_caveaux_reels"] > 0
        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text(f"Bloc {b['code']}", size=15, weight=ft.FontWeight.BOLD),
                    ft.Container(expand=True),
                    ft.Text(b["nom"], size=13, color="#6b7280"),
                ]),
                ft.Row([
                    _stat("Grille", f"{b['nombre_rangees']} × {b['nombre_colonnes']}"),
                    _stat("Capacité théorique", f"{b['capacite_theorique']} caveaux"),
                    _stat("Caveaux créés", str(b["nombre_caveaux_reels"])),
                ], spacing=16, wrap=True),
                ft.Row([
                    bouton_principal(
                        "Générer les caveaux",
                        on_click=lambda e, bloc=b: ouvrir_dialogue_generation(bloc),
                        icone=ft.icons.ADD_LOCATION_ALT,
                    ) if not a_caveaux else ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.icons.CHECK_CIRCLE, color="#22c55e", size=18),
                            ft.Text(f"{b['nombre_caveaux_reels']} caveaux générés", color="#16a34a", size=13),
                        ]),
                    ),
                ]),
            ], spacing=8),
            bgcolor=ft.colors.SURFACE, padding=14, border_radius=10,
            border=ft.border.all(2 if not a_caveaux else 1, "#3b82f6" if not a_caveaux else "#e5e7eb"),
        )

    def charger_blocs():
        zone_blocs.visible = True
        zone_blocs.content = chargement("Chargement des blocs...")
        page.update()

        zone = state["zone_selectionnee"]
        try:
            blocs = client.liste_blocs(zone["id"])
            state["blocs"] = blocs

            caveaux_crees = sum(b["nombre_caveaux_reels"] for b in blocs)
            caveaux_theoriques = sum(b["capacite_theorique"] for b in blocs)

            en_tete = ft.Column([
                ft.Row([
                    ft.IconButton(ft.icons.ARROW_BACK,
                                  on_click=lambda e: retour_zones(),
                                  tooltip="Retour aux zones"),
                    ft.Text(f"Blocs — Zone {zone['code']} ({zone['nom']})",
                            size=16, weight=ft.FontWeight.BOLD),
                    ft.Container(expand=True),
                    ft.ElevatedButton("+ Nouveau bloc", icon=ft.icons.ADD,
                                      on_click=lambda e: ouvrir_dialogue_bloc()),
                ]),
                ft.Container(
                    content=ft.Row([
                        _stat("Blocs", str(len(blocs))),
                        _stat("Caveaux théoriques", str(caveaux_theoriques)),
                        _stat("Caveaux créés", str(caveaux_crees)),
                        _stat("Restant à générer", str(caveaux_theoriques - caveaux_crees)),
                    ], spacing=16, wrap=True),
                    bgcolor="#eff6ff", padding=12, border_radius=8,
                    border=ft.border.all(1, "#bfdbfe"),
                ),
            ], spacing=10)

            zone_blocs.content = ft.Column([
                en_tete,
                ft.Divider(),
                *([construire_carte_bloc(b) for b in blocs]
                  if blocs else [etat_vide("Aucun bloc créé.", ft.icons.TABLE_CHART)]),
            ], spacing=10)

        except APIError as err:
            zone_blocs.content = etat_vide(f"Erreur : {err.detail}", ft.icons.ERROR_OUTLINE)
        page.update()

    def retour_zones():
        zone_blocs.visible = False
        charger_zones()

    # ═══════════════════════════════════════════════════════════════════════════
    # HELPER
    # ═══════════════════════════════════════════════════════════════════════════

    def _stat(label: str, valeur: str) -> ft.Column:
        return ft.Column([
            ft.Text(valeur, size=15, weight=ft.FontWeight.BOLD),
            ft.Text(label, size=11, color="#6b7280"),
        ], spacing=2, horizontal_alignment=ft.CrossAxisAlignment.CENTER)

    # ─── Chargement initial ────────────────────────────────────────────────────
    charger_cimetieres()

    return ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Text("Gestion du terrain", size=20, weight=ft.FontWeight.BOLD),
                ft.Container(expand=True),
                ft.IconButton(ft.icons.REFRESH, on_click=lambda e: charger_cimetieres(),
                              tooltip="Actualiser"),
            ]),
            ft.Divider(),
            zone_cimetiere,
            zone_zones,
            zone_blocs,
        ], spacing=10, expand=True),
        padding=20,
        expand=True,
    )
