"""
Settings — Application de Gestion de Cimetière
Stack : Django 4.2 + Django Ninja + PostgreSQL/PostGIS
"""

import os
import platform
from pathlib import Path
from decouple import config
from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config("SECRET_KEY", default="dev-secret-key-changez-moi-en-production")
DEBUG = config("DEBUG", default=True, cast=bool)
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost,127.0.0.1").split(",")

# ─── GDAL / GEOS ─────────────────────────────────────────────────────────────
# Sous Windows (dev local) : on pointe explicitement vers les DLL installées.
# Sous Linux (Render/Docker/prod) : GDAL est installé via apt-get et Django
# le détecte tout seul dans le PATH système — inutile et risqué de forcer un
# chemin Windows qui n'existe pas sur le serveur.
if platform.system() == "Windows":
    GDAL_LIBRARY_PATH = config("GDAL_LIBRARY_PATH", default=r"C:\Program Files\GDAL\gdal312.dll")
    GEOS_LIBRARY_PATH = config("GEOS_LIBRARY_PATH", default=r"C:\Program Files\GDAL\geos_c.dll")

    _gdal_bin_dir = os.path.dirname(GDAL_LIBRARY_PATH)
    if os.path.isdir(_gdal_bin_dir):
        os.environ["PATH"] = _gdal_bin_dir + os.pathsep + os.environ.get("PATH", "")
else:
    # On permet quand même une surcharge explicite via variables d'environnement
    # si jamais le serveur Linux a besoin d'un chemin précis (rare).
    GDAL_LIBRARY_PATH = config("GDAL_LIBRARY_PATH", default=None)
    GEOS_LIBRARY_PATH = config("GEOS_LIBRARY_PATH", default=None)

# ─── Applications ─────────────────────────────────────────────────────────────
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.gis",
]

THIRD_PARTY_APPS = [
    "ninja",
    "corsheaders",
    "simple_history",           # Audit trail immuable
    "django_celery_beat",       # Tâches planifiées (optionnel en dev)
    "django_filters",
]

LOCAL_APPS = [
    "apps.users",
    "apps.terrain",
    "apps.cartographie",
    "apps.reservations",
    "apps.concessions",
    "apps.finance",
    "apps.notifications",
    "apps.reporting",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# ─── Middleware ────────────────────────────────────────────────────────────────
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "simple_history.middleware.HistoryRequestMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# ─── Templates ────────────────────────────────────────────────────────────────
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ─── Base de données — PostgreSQL + PostGIS ───────────────────────────────────
# En production (Render), DATABASE_URL est fourni automatiquement par le
# service Postgres. En dev local, on retombe sur les variables DB_* du .env.
import dj_database_url  # noqa: E402

DATABASE_URL = config("DATABASE_URL", default=None)

if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            engine="django.contrib.gis.db.backends.postgis",
            conn_max_age=600,
        )
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.contrib.gis.db.backends.postgis",
            "NAME": config("DB_NAME", default="cimetiere_db"),
            "USER": config("DB_USER", default="postgres"),
            "PASSWORD": config("DB_PASSWORD", default=""),
            "HOST": config("DB_HOST", default="localhost"),
            "PORT": config("DB_PORT", default="5432"),
        }
    }

# ─── Modèle utilisateur personnalisé ──────────────────────────────────────────
AUTH_USER_MODEL = "users.Utilisateur"

# ─── JWT ──────────────────────────────────────────────────────────────────────
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(
        minutes=config("JWT_ACCESS_TOKEN_LIFETIME_MINUTES", default=60, cast=int)
    ),
    "REFRESH_TOKEN_LIFETIME": timedelta(
        days=config("JWT_REFRESH_TOKEN_LIFETIME_DAYS", default=7, cast=int)
    ),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# ─── MFA ──────────────────────────────────────────────────────────────────────
MFA_CODE_VALIDITY_MINUTES = config("MFA_CODE_VALIDITY_MINUTES", default=10, cast=int)
MFA_CODE_LENGTH = 6

# ─── Email ────────────────────────────────────────────────────────────────────
# En développement : les emails s'affichent dans la console (pas d'envoi réel)
# Mettre EMAIL_BACKEND=smtp dans .env pour activer l'envoi réel
EMAIL_BACKEND_DEV = "django.core.mail.backends.console.EmailBackend"
EMAIL_BACKEND_PROD = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_BACKEND = config("EMAIL_BACKEND", default=EMAIL_BACKEND_DEV)

EMAIL_HOST = config("EMAIL_HOST", default="smtp.gmail.com")
EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=True, cast=bool)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="noreply@cimetiere.app")
EMAIL_TIMEOUT = 10
# ─── CORS ─────────────────────────────────────────────────────────────────────
# En production, on autorise aussi le domaine Render du frontend Flet.
# Ajoute/adapte l'URL exacte une fois le frontend déployé.
CORS_ALLOWED_ORIGINS = config(
    "CORS_ALLOWED_ORIGINS",
    default="http://localhost:3000,http://127.0.0.1:3000,http://localhost:8000",
).split(",")
CORS_ALLOW_CREDENTIALS = True

# En démo/soutenance, si tu préfères ne pas te battre avec CORS_ALLOWED_ORIGINS,
# tu peux temporairement décommenter la ligne suivante pour tout autoriser :
# CORS_ALLOW_ALL_ORIGINS = True

# ─── Celery ───────────────────────────────────────────────────────────────────
# Optionnel en développement — les tâches async tournent en mode synchrone
# si Celery n'est pas démarré (les try/except dans les tasks l'absorbent)
CELERY_BROKER_URL = config("CELERY_BROKER_URL", default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND = config("CELERY_RESULT_BACKEND", default="redis://localhost:6379/0")
CELERY_TIMEZONE = "Africa/Brazzaville"
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
CELERY_TASK_ALWAYS_EAGER = config("CELERY_TASK_ALWAYS_EAGER", default=True, cast=bool)

# ─── Internationalisation ──────────────────────────────────────────────────────
LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Africa/Brazzaville"
USE_I18N = True
USE_TZ = True

# ─── Fichiers statiques & media ───────────────────────────────────────────────
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ─── Sécurité (production uniquement) ────────────────────────────────────────
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
