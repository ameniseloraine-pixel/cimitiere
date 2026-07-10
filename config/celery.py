"""
Configuration Celery — Tâches asynchrones et planifiées
Lancer le worker : celery -A config worker -l info
Lancer le beat   : celery -A config beat -l info
"""

import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("cimetiere")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

# ─── Tâches planifiées (Celery Beat) ──────────────────────────────────────────
app.conf.beat_schedule = {
    # Vérification quotidienne des concessions expirant dans 90 jours
    "verifier-concessions-expirantes": {
        "task": "apps.notifications.tasks.verifier_concessions_expirantes",
        "schedule": crontab(hour=6, minute=0),  # Tous les jours à 6h
    },
    # Vérification quotidienne des factures en retard
    "verifier-retards-paiement": {
        "task": "apps.notifications.tasks.verifier_retards_paiement",
        "schedule": crontab(hour=7, minute=0),  # Tous les jours à 7h
    },
    # Vérification du seuil critique d'occupation (2x/jour)
    "verifier-seuil-places-critiques": {
        "task": "apps.notifications.tasks.verifier_seuil_places_critiques",
        "schedule": crontab(hour="6,18", minute=30),
    },
}

app.conf.timezone = "Africa/Brazzaville"


@app.task(bind=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
