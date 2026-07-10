# Application de Gestion de Cimetière — GI2 2026

## Stack technique
- **Backend** : Django 4.2 + Django Ninja (API RESTful typée)
- **Base de données** : PostgreSQL + PostGIS (coordonnées GPS des caveaux)
- **Frontend** : Flet (Python/Flutter multiplateforme)
- **Async** : Celery + Redis (emails, alertes automatiques)
- **Déploiement** : Gunicorn + Whitenoise

## Installation rapide

### 1. Prérequis système
```bash
# Ubuntu/Debian
sudo apt install postgresql postgis gdal-bin libgdal-dev python3-gdal redis-server
```

### 2. Base de données PostgreSQL + PostGIS
```sql
CREATE DATABASE cimetiere_db;
\c cimetiere_db
CREATE EXTENSION postgis;
```

### 3. Environnement Python
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4. Configuration
```bash
cp .env.example .env
# Éditer .env avec vos paramètres (DB, email, etc.)
```

### 5. Migrations & lancement
```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

### 6. Celery (dans un terminal séparé)
```bash
celery -A config worker -l info
celery -A config beat -l info  # Pour les tâches planifiées
```

## Documentation API
- Swagger UI : http://localhost:8000/api/docs
- Admin Django : http://localhost:8000/admin/

## Architecture des modules

| Module | Description |
|--------|-------------|
| `apps/users` | RBAC, MFA, JWT |
| `apps/terrain` | Cimetière, Zones, Blocs |
| `apps/cartographie` | Caveaux PostGIS, Audit trail |
| `apps/reservations` | Workflow réservation |
| `apps/concessions` | Contrats, Exhumations |
| `apps/finance` | Factures, Paiements multi-canal |
| `apps/notifications` | Emails automatiques |
| `apps/reporting` | Dashboard, Exports CSV/Excel |

## Flux principal
```
Client → Login (email/pwd) → Code MFA par email → Token JWT
       → Sélection caveau (carte) → Formulaire réservation
       → Admin valide → Facture PDF auto-générée → Email client
       → Caveau passe Vert → Orange → Rouge
```

## Date limite : 30 juin 2026
