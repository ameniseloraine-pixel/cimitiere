# Guide de test complet — Windows

## Prérequis déjà couverts dans ce guide
- Python 3.10+
- PostgreSQL 15+ avec extension PostGIS activée
- GDAL pour Windows (ex: via OSGeo4W, généralement installé dans `C:\Program Files\GDAL\`)

---

## Étape 1 — Préparer le backend Django

```powershell
cd chemin\vers\cimetiere
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

---

## Étape 2 — Configurer l'environnement

```powershell
copy .env.example .env
notepad .env
```

Renseigne dans `.env` :
- `DB_NAME`, `DB_USER`, `DB_PASSWORD` : tes identifiants PostgreSQL
- `DB_PORT` : le port de TON instance PostgreSQL (vérifier avec `netstat -ano | findstr "5432 5433"` si tu as plusieurs versions installées)
- `GDAL_LIBRARY_PATH` / `GEOS_LIBRARY_PATH` : chemins vers tes DLL GDAL (par défaut `C:\Program Files\GDAL\...`)
- `EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend` → les codes MFA et codes de paiement Mobile Money s'affichent dans le terminal Django au lieu d'être envoyés par un vrai email

⚠️ **Important** : le fichier `.env` ne doit contenir AUCUN caractère accentué (même dans les commentaires), sous peine d'erreur `UnicodeDecodeError` lors de la connexion à PostgreSQL sous Windows.

---

## Étape 3 — Initialiser la base de données

```powershell
python manage.py makemigrations
python manage.py migrate
python manage.py init_tarifs
python manage.py createsuperuser
```

---

## Étape 4 — Lancer le serveur Django

```powershell
python manage.py runserver
```

Vérifications dans le navigateur :
- http://127.0.0.1:8000/api/docs → Documentation Swagger
- http://127.0.0.1:8000/admin/ → Interface d'administration

---

## Étape 5 — Lancer l'interface Flet (nouveau terminal)

```powershell
cd chemin\vers\cimetiere\frontend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
flet run main.py
```

---

## Créer des données de test (via Swagger, authentifié en Admin)

1. `POST /api/auth/login` puis `POST /api/auth/verify-mfa` (code visible dans le terminal Django) → récupérer le token
2. Cliquer **Authorize** en haut de Swagger, coller le token
3. `POST /api/terrain/cimetiere` → créer le cimetière
4. `POST /api/terrain/cimetiere/{id}/zones` → créer une zone
5. `POST /api/terrain/zones/{id}/blocs` → créer un bloc
6. `POST /api/terrain/blocs/{id}/generer-caveaux` → génère automatiquement tous les caveaux du bloc (géolocalisés via PostGIS)

---

## Tester le parcours complet dans l'app Flet

1. **Créer un compte Client** (différent du compte Admin) via "Créer un compte"
2. Se connecter avec ce compte client → coller le code MFA depuis le terminal Django
3. Aller sur **Carte** → cliquer sur un caveau vert → soumettre une réservation
4. Se reconnecter en Admin → **Réservations** → Valider la demande (génère la facture automatiquement)
5. Se reconnecter en Client → **Mes factures** → cliquer sur la facture → **Payer via Mobile Money**
6. Choisir l'opérateur, saisir un numéro fictif et le montant → cliquer **Lancer le paiement**
7. Récupérer le code à 6 chiffres dans le terminal Django → le saisir → **Confirmer le paiement**
8. La facture passe en statut "Payée" (ou un échec simulé peut survenir ~5% du temps, comme un vrai opérateur — relancer dans ce cas)

---

## Résolution des problèmes courants

### ❌ `UnicodeDecodeError` lors de `makemigrations`/`migrate`
Le fichier `.env` contient un caractère accentué (même dans un commentaire). Le réécrire entièrement sans accents.

### ❌ Connexion à PostgreSQL échoue alors que le mot de passe est correct
Vérifier que `DB_PORT` correspond bien à l'instance PostgreSQL qui contient `cimetiere_db` (utiliser `netstat -ano | findstr "5432 5433"` puis `Get-Process -Id <PID>` pour identifier quelle version écoute sur quel port si plusieurs versions de PostgreSQL sont installées).

### ❌ `django.core.exceptions.ImproperlyConfigured: WSGI application ... could not be loaded`
Le fichier `config/wsgi.py` ou `config/asgi.py` est vide — vérifier qu'il contient bien le code de chargement Django.

### ❌ `AttributeError: module 'flet' has no attribute 'Icons'`
Cette version de Flet utilise `ft.icons` (minuscule), pas `ft.Icons`. Déjà corrigé dans ce zip.

### ❌ `TypeError: Tooltip.__init__() got an unexpected keyword argument 'content'`
Cette version de Flet utilise `tooltip="texte"` directement sur un `Container`, pas un widget `ft.Tooltip(content=...)` séparé. Déjà corrigé dans ce zip.

### ❌ Le code MFA ne s'affiche pas dans le terminal
Vérifier dans `.env` : `EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend`

### ❌ Le menu Flet est identique pour Client et Admin
Le RBAC du menu dépend de `client.role` dans `frontend/main.py`. Déjà corrigé dans ce zip (menus différenciés Client / Agent / Admin-Secrétariat).

### ❌ Port 8000 déjà utilisé
```powershell
python manage.py runserver 8001
```
Et modifier `frontend/config.py` : `API_BASE_URL = "http://localhost:8001/api"`

---

## Notes sur la simulation Mobile Money / Airtel Money

N'étant pas une entreprise enregistrée auprès de MTN ou Airtel, ce projet
simule le flux de paiement mobile via une API de test interne
(`apps/finance/mobile_money_simulator.py`) qui reproduit fidèlement le
comportement réel d'un agrégateur de paiement :
1. Le client initie le paiement (numéro + montant)
2. Un code de confirmation à 6 chiffres est généré et envoyé (notification push simulée par email)
3. Le client confirme avec le code dans les 5 minutes
4. ~95% de réussite simulée, ~5% d'échec réaliste (solde insuffisant, opérateur indisponible...)
5. En cas de succès, le paiement est automatiquement enregistré et la facture mise à jour

Cette architecture est conçue pour être facilement substituée par un vrai
SDK MTN MoMo / Airtel Money API le jour où un compte marchand réel est
disponible — il suffirait de remplacer le contenu de
`mobile_money_simulator.py` par les vrais appels API, sans toucher au
reste de l'application (modèles, endpoints, frontend).
