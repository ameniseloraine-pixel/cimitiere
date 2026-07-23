"""
Client API — Wrapper autour de requests pour communiquer avec le backend
Django Ninja. Gère l'authentification JWT, le MFA et les erreurs.
"""

import requests
from typing import Optional
from config import API_BASE_URL


class APIError(Exception):
    """Exception levée en cas d'erreur retournée par l'API."""
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


class APIClient:
    """
    Client HTTP pour l'API Gestion de Cimetière.
    Conserve le token JWT et les infos utilisateur en mémoire (par session Flet).
    """

    def __init__(self, base_url: str = API_BASE_URL):
        self.base_url = base_url
        self.access_token: Optional[str] = None
        self.refresh_token_value: Optional[str] = None
        self.user: Optional[dict] = None

    # ─── Gestion des headers ──────────────────────────────────────────────────

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    # ─── Méthode générique de requête ─────────────────────────────────────────

    def _request(self, method: str, path: str, retry_on_401: bool = True, **kwargs):
        url = f"{self.base_url}{path}"
        try:
            resp = requests.request(method, url, headers=self._headers(), timeout=15, **kwargs)
        except requests.exceptions.ConnectionError:
            raise APIError(0, "Impossible de contacter le serveur. Vérifiez votre connexion.")
        except requests.exceptions.Timeout:
            raise APIError(0, "Le serveur ne répond pas (timeout).")

        if resp.status_code == 401 and retry_on_401 and self.refresh_token_value:
            if self._refresh_access_token():
                return self._request(method, path, retry_on_401=False, **kwargs)

        if resp.status_code >= 400:
            try:
                detail = resp.json().get("detail", resp.text)
            except Exception:
                detail = resp.text or f"Erreur HTTP {resp.status_code}"
            raise APIError(resp.status_code, detail)

        if resp.content:
            try:
                return resp.json()
            except Exception:
                return resp.content
        return None

    def _refresh_access_token(self) -> bool:
        """Tente de renouveler le token d'accès via le refresh token."""
        try:
            resp = requests.post(
                f"{self.base_url}/auth/refresh",
                json={"refresh_token": self.refresh_token_value},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                self.access_token = data["access_token"]
                self.refresh_token_value = data["refresh_token"]
                return True
        except Exception:
            pass
        return False

    # ─── Authentification ─────────────────────────────────────────────────────

    def login(self, email: str, password: str) -> dict:
        """Étape 1 : login email/mdp → envoi du code MFA."""
        return self._request("POST", "/auth/login", json={"email": email, "password": password}, retry_on_401=False)

    def verify_mfa(self, email: str, code: str) -> dict:
        """Étape 2 : vérification du code MFA → tokens JWT."""
        data = self._request(
            "POST", "/auth/verify-mfa",
            json={"email": email, "code": code},
            retry_on_401=False,
        )
        self.access_token = data["access_token"]
        self.refresh_token_value = data["refresh_token"]
        self.user = self.get_profile()
        return data

    def register(self, email: str, password: str, nom: str, prenom: str, telephone: str = "") -> dict:
        """Inscription d'un nouveau compte client."""
        return self._request(
            "POST", "/auth/register",
            json={
                "email": email, "password": password,
                "nom": nom, "prenom": prenom, "telephone": telephone,
            },
            retry_on_401=False,
        )

    def get_profile(self) -> dict:
        return self._request("GET", "/auth/me")

    def logout(self):
        self.access_token = None
        self.refresh_token_value = None
        self.user = None

    @property
    def is_authenticated(self) -> bool:
        return self.access_token is not None

    @property
    def role(self) -> str:
        return self.user.get("role", "") if self.user else ""

    @property
    def is_admin(self) -> bool:
        return self.role == "ADMIN"

    @property
    def can_validate(self) -> bool:
        return self.role in ("ADMIN", "SECR")

    @property
    def can_edit_map(self) -> bool:
        return self.role in ("ADMIN", "AGENT")

    @property
    def can_see_finance(self) -> bool:
        return self.role in ("ADMIN", "SECR")

    # ─── Utilisateurs ─────────────────────────────────────────────────────────

    def creer_utilisateur(self, email: str, password: str, nom: str, prenom: str,
                           role: str, telephone: str = "") -> dict:
        """Créer un compte Agent/Secrétariat/Admin/Client (Admin uniquement)."""
        return self._request(
            "POST", "/auth/utilisateurs",
            json={
                "email": email, "password": password,
                "nom": nom, "prenom": prenom,
                "telephone": telephone, "role": role,
            },
        )

    def liste_utilisateurs(self) -> list:
        return self._request("GET", "/auth/utilisateurs")

    # ─── Cartographie ──────────────────────────────────────────────────────────

    def liste_caveaux(self, statut: str = None, zone_code: str = None, bloc_code: str = None) -> list:
        params = {}
        if statut: params["statut"] = statut
        if zone_code: params["zone_code"] = zone_code
        if bloc_code: params["bloc_code"] = bloc_code
        return self._request("GET", "/carte/caveaux", params=params)

    def detail_caveau(self, caveau_id: int) -> dict:
        return self._request("GET", f"/carte/caveaux/{caveau_id}")

    def changer_statut_caveau(self, caveau_id: int, statut: str, raison: str = "") -> dict:
        return self._request("PATCH", f"/carte/caveaux/{caveau_id}/statut", json={"statut": statut, "raison": raison})

    def statistiques_carte(self) -> dict:
        return self._request("GET", "/carte/statistiques")

    # ─── Terrain ────────────────────────────────────────────────────────────────

    def liste_cimetieres(self) -> list:
        return self._request("GET", "/terrain/cimetiere")

    def creer_cimetiere(self, nom: str, adresse: str, ville: str, superficie_totale_m2: float,
                         tombeau_longueur_m: float = 2.5, tombeau_largeur_m: float = 1.2,
                         pourcentage_chemins: float = 20.0, telephone: str = "", email_contact: str = "") -> dict:
        return self._request(
            "POST", "/terrain/cimetiere",
            json={
                "nom": nom, "adresse": adresse, "ville": ville,
                "superficie_totale_m2": superficie_totale_m2,
                "tombeau_longueur_m": tombeau_longueur_m,
                "tombeau_largeur_m": tombeau_largeur_m,
                "pourcentage_chemins": pourcentage_chemins,
                "telephone": telephone, "email_contact": email_contact,
            },
        )

    def modifier_cimetiere(self, cimetiere_id: int, **kwargs) -> dict:
        return self._request("PUT", f"/terrain/cimetiere/{cimetiere_id}", json=kwargs)

    def liste_zones(self, cimetiere_id: int) -> list:
        return self._request("GET", f"/terrain/cimetiere/{cimetiere_id}/zones")

    def creer_zone(self, cimetiere_id: int, nom: str, code: str, superficie_m2: float,
                    type_zone: str = "EXPLOIT", description: str = "", ordre_affichage: int = 0) -> dict:
        return self._request(
            "POST", f"/terrain/cimetiere/{cimetiere_id}/zones",
            json={
                "nom": nom, "code": code, "type_zone": type_zone,
                "superficie_m2": superficie_m2, "description": description,
                "ordre_affichage": ordre_affichage,
            },
        )

    def supprimer_zone(self, zone_id: int) -> dict:
        return self._request("DELETE", f"/terrain/zones/{zone_id}")

    def liste_blocs(self, zone_id: int) -> list:
        return self._request("GET", f"/terrain/zones/{zone_id}/blocs")

    def creer_bloc(self, zone_id: int, nom: str, code: str,
                    nombre_rangees: int = 1, nombre_colonnes: int = 1) -> dict:
        return self._request(
            "POST", f"/terrain/zones/{zone_id}/blocs",
            json={
                "nom": nom, "code": code,
                "nombre_rangees": nombre_rangees, "nombre_colonnes": nombre_colonnes,
            },
        )

    def generer_caveaux_bloc(self, bloc_id: int, latitude_origine: float = -4.7761,
                              longitude_origine: float = 11.8636, espacement_m: float = 0.5) -> dict:
        return self._request(
            "POST", f"/terrain/blocs/{bloc_id}/generer-caveaux",
            params={
                "latitude_origine": latitude_origine,
                "longitude_origine": longitude_origine,
                "espacement_m": espacement_m,
            },
        )

    # ─── Réservations ──────────────────────────────────────────────────────────

    def soumettre_reservation(self, caveau_id: int, defunt: dict, date_inhumation: str = None, notes: str = "") -> dict:
        payload = {
            "caveau_id": caveau_id,
            "defunt": defunt,
            "notes_admin": notes,
        }
        if date_inhumation:
            payload["date_inhumation_souhaitee"] = date_inhumation
        return self._request("POST", "/reservations/", json=payload)

    def liste_reservations(self, statut: str = None) -> list:
        params = {"statut": statut} if statut else {}
        return self._request("GET", "/reservations/", params=params)

    def detail_reservation(self, reservation_id: int) -> dict:
        return self._request("GET", f"/reservations/{reservation_id}")

    def valider_reservation(self, reservation_id: int) -> dict:
        return self._request("POST", f"/reservations/{reservation_id}/valider")

    def rejeter_reservation(self, reservation_id: int, motif: str) -> dict:
        return self._request("POST", f"/reservations/{reservation_id}/rejeter", json={"motif": motif})

    def annuler_reservation(self, reservation_id: int) -> dict:
        return self._request("DELETE", f"/reservations/{reservation_id}")

    # ─── Concessions & Exhumations ───────────────────────────────────────────────

    def liste_concessions(self, statut: str = None, alerte_seulement: bool = False) -> list:
        params = {}
        if statut: params["statut"] = statut
        if alerte_seulement: params["alerte_seulement"] = "true"
        return self._request("GET", "/concessions/", params=params)

    def renouveler_concession(self, concession_id: int, nouveau_type: str = None) -> dict:
        payload = {}
        if nouveau_type:
            payload["nouveau_type"] = nouveau_type
        return self._request("POST", f"/concessions/{concession_id}/renouveler", json=payload)

    def liste_exhumations(self, statut: str = None) -> list:
        params = {"statut": statut} if statut else {}
        return self._request("GET", "/concessions/exhumations", params=params)

    def soumettre_exhumation(self, concession_id: int, motif: str, destination: str = "") -> dict:
        return self._request(
            "POST", "/concessions/exhumations",
            json={"concession_id": concession_id, "motif": motif, "destination_restes": destination},
        )

    def autoriser_exhumation(self, exhumation_id: int) -> dict:
        return self._request("POST", f"/concessions/exhumations/{exhumation_id}/autoriser")

    def refuser_exhumation(self, exhumation_id: int, motif: str) -> dict:
        return self._request("POST", f"/concessions/exhumations/{exhumation_id}/refuser", json={"motif_refus": motif})

    # ─── Finance ──────────────────────────────────────────────────────────────────

    def liste_factures(self, statut: str = None) -> list:
        params = {"statut": statut} if statut else {}
        return self._request("GET", "/finance/factures", params=params)

    def detail_facture(self, facture_id: int) -> dict:
        return self._request("GET", f"/finance/factures/{facture_id}")

    # NOUVEAU : téléchargement du PDF de la facture (retourne les bytes bruts)
    def telecharger_facture_pdf(self, facture_id: int) -> bytes:
        return self._request("GET", f"/finance/factures/{facture_id}/pdf")

    def enregistrer_paiement(self, facture_id: int, canal: str, montant: float,
                               reference: str = "", telephone: str = "", notes: str = "") -> dict:
        return self._request(
            "POST", f"/finance/factures/{facture_id}/paiements",
            json={
                "canal": canal, "montant": montant,
                "reference_transaction": reference,
                "telephone_paiement": telephone, "notes": notes,
            },
        )

    def liste_tarifs(self) -> list:
        return self._request("GET", "/finance/tarifs")

    def factures_en_retard(self) -> list:
        return self._request("GET", "/finance/retards")

    # ─── Paiement Mobile Money / Airtel Money (simulation) ───────────────────────

    def initier_paiement_mobile(self, facture_id: int, canal: str, telephone: str, montant: float) -> dict:
        """
        Lance un paiement Mobile Money / Airtel Money simulé.
        Retourne une transaction avec un code de confirmation envoyé par email.
        """
        return self._request(
            "POST", f"/finance/factures/{facture_id}/paiement-mobile/initier",
            json={"canal": canal, "telephone": telephone, "montant": montant},
        )

    def confirmer_paiement_mobile(self, transaction_id: int, code: str) -> dict:
        """Confirme la transaction avec le code reçu par email."""
        return self._request(
            "POST", f"/finance/paiement-mobile/{transaction_id}/confirmer",
            json={"code": code},
        )

    def annuler_paiement_mobile(self, transaction_id: int) -> dict:
        return self._request("POST", f"/finance/paiement-mobile/{transaction_id}/annuler")

    def detail_transaction_mobile(self, transaction_id: int) -> dict:
        return self._request("GET", f"/finance/paiement-mobile/{transaction_id}")

    def historique_transactions_mobile(self, facture_id: int) -> list:
        return self._request("GET", f"/finance/factures/{facture_id}/paiement-mobile/historique")

    # ─── Reporting ────────────────────────────────────────────────────────────────

    def dashboard(self) -> dict:
        return self._request("GET", "/reporting/dashboard")