# Frontend Flet — Gestion de Cimetière

Application multiplateforme (Windows / Mac / Linux / Web) construite avec Flet
(Python/Flutter), consommant l'API Django Ninja.

## Installation (Windows)

### 1. Prérequis
- Python 3.10+ installé (cocher "Add to PATH" lors de l'installation)
- Le backend Django doit être lancé (voir README principal du projet)

### 2. Ouvrir PowerShell ou l'invite de commande dans le dossier `frontend`

```powershell
cd cimetiere\frontend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configurer l'URL de l'API

Par défaut, l'application pointe vers `http://localhost:8000/api`.

Si le backend Django tourne sur une autre machine ou un autre port,
définir la variable d'environnement avant de lancer :

```powershell
$env:CIMETIERE_API_URL = "http://192.168.1.10:8000/api"
```

### 4. Lancer l'application

**Mode application de bureau (recommandé) :**
```powershell
flet run main.py
```

**Mode navigateur web :**
```powershell
flet run main.py --web
```

**Mode rechargement automatique pendant le développement :**
```powershell
flet run main.py -d
```

## Comptes de test

Créez un compte via "Créer un compte" (rôle Client par défaut), ou créez
un administrateur via Django :

```powershell
cd ..\          REM retour au dossier cimetiere
venv\Scripts\activate
python manage.py createsuperuser
```

Puis modifiez son rôle en "ADMIN" depuis l'admin Django (`/admin/`).

## Architecture

| Fichier | Rôle |
|---|---|
| `main.py` | Point d'entrée, navigation, menu latéral RBAC |
| `api_client.py` | Client HTTP (JWT, MFA, endpoints) |
| `config.py` | URL API, couleurs/codes statuts |
| `views/login_view.py` | Connexion en 2 étapes (mot de passe + code MFA email) |
| `views/register_view.py` | Inscription client |
| `views/dashboard_view.py` | Statistiques, jauge de saturation, revenus |
| `views/carte_view.py` | Carte interactive (grille colorée par statut) |
| `views/reservation_form_view.py` | Formulaire de réservation (infos défunt) |
| `views/reservations_view.py` | Liste + validation/rejet des réservations |
| `views/concessions_view.py` | Concessions, renouvellement, exhumations |
| `views/finance_view.py` | Factures, paiements multi-canal |
| `components/widgets.py` | Composants réutilisables (badges, boutons, etc.) |

## Code couleur de la carte

| Couleur | Statut |
|---|---|
| 🟢 Vert | Disponible |
| 🟠 Orange | Réservé / En attente de validation |
| 🔴 Rouge | Occupé / Validé |
| ⚪ Gris | Non exploitable |

## Permissions par rôle (RBAC)

| Rôle | Carte | Réservations | Concessions | Finance |
|---|---|---|---|---|
| **Client** | Consultation + réservation | Ses dossiers | Ses concessions, demande exhumation | Ses factures |
| **Agent terrain** | Modifier statuts | Lecture | Lecture | — |
| **Secrétariat** | Lecture | Valider/Rejeter | Renouveler | Paiements |
| **Admin** | Tout | Tout | Tout + autoriser exhumations | Tout |
