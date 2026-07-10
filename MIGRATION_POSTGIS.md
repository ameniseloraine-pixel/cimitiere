# Migration vers PostgreSQL + PostGIS

Quand tu es prêt à passer à la base de données spatiale complète.

## 1. Installer PostgreSQL + PostGIS sous Windows

1. Télécharger **PostgreSQL 15** sur https://www.postgresql.org/download/windows/
2. Lors de l'installation, cocher **Stack Builder**
3. Après l'installation, ouvrir Stack Builder et installer **PostGIS 3.x**
4. Ouvrir **pgAdmin** ou **psql** et créer la base :

```sql
CREATE DATABASE cimetiere_db;
\c cimetiere_db
CREATE EXTENSION postgis;
```

## 2. Installer les dépendances Python

```powershell
pip install psycopg2-binary
```

## 3. Configurer le .env

```env
USE_POSTGRES=True
DB_NAME=cimetiere_db
DB_USER=postgres
DB_PASSWORD=ton_mot_de_passe
```

## 4. Modifier settings.py

Changer le moteur PostgreSQL vers PostGIS :
```python
# Dans le bloc if USE_POSTGRES:
"ENGINE": "django.contrib.gis.db.backends.postgis",
```

Et décommenter `django.contrib.gis` dans DJANGO_APPS.

## 5. Modifier cartographie/models.py

Remplacer les deux champs `latitude`/`longitude` (DecimalField) par :
```python
from django.contrib.gis.db import models as gis_models

localisation = gis_models.PointField(srid=4326, null=True, blank=True)
```

Et faire hériter `Caveau` de `gis_models.Model` au lieu de `models.Model`.

## 6. Générer et appliquer les migrations

```powershell
python manage.py makemigrations cartographie
python manage.py migrate
```

## Note GDAL sous Windows

PostGIS nécessite GDAL. Si Django affiche une erreur GDAL :
1. Télécharger les binaires sur https://trac.osgeo.org/osgeo4w/
2. Ajouter dans settings.py (adapter le chemin) :
```python
import os
os.environ['PATH'] = r'C:\OSGeo4W\bin;' + os.environ['PATH']
GDAL_LIBRARY_PATH = r'C:\OSGeo4W\bin\gdal309.dll'
GEOS_LIBRARY_PATH = r'C:\OSGeo4W\bin\geos_c.dll'
```
