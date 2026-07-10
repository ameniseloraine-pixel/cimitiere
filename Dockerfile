# ════════════════════════════════════════════
# Dockerfile — Backend Django + PostGIS pour Render
# ════════════════════════════════════════════

FROM python:3.11-slim

# Empêche Python de bufferiser les logs (utile pour voir les erreurs sur Render)
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# ─── Dépendances système : GDAL, GEOS, PROJ (requis par django.contrib.gis) ───
RUN apt-get update && apt-get install -y --no-install-recommends \
    binutils \
    libproj-dev \
    gdal-bin \
    libgdal-dev \
    libgeos-dev \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# ─── Dépendances Python ─────────────────────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir dj-database-url

# ─── Code de l'application ──────────────────────────────────────────────────
COPY . .

# Collecte des fichiers statiques (admin Django, etc.) au moment du build
RUN python manage.py collectstatic --noinput || true

EXPOSE 8000

# Au démarrage : applique les migrations puis lance gunicorn.
CMD python manage.py migrate --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --timeout 120
