"""
URLs principales — Router Django Ninja
Documentation Swagger : /api/docs
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from ninja import NinjaAPI
from ninja.security import HttpBearer

# Import des routers par module
from apps.users.api import router as users_router
from apps.terrain.api import router as terrain_router
from apps.cartographie.api import router as cartographie_router
from apps.reservations.api import router as reservations_router
from apps.concessions.api import router as concessions_router
from apps.finance.api import router as finance_router
from apps.reporting.api import router as reporting_router

# ─── API principale ────────────────────────────────────────────────────────────
api = NinjaAPI(
    title="API Gestion de Cimetière",
    version="1.0.0",
    description="""
    ## API REST — Application de Gestion de Cimetière
    
    ### Authentification
    Utiliser le endpoint `/api/auth/login` pour obtenir un token JWT.  
    Inclure dans le header : `Authorization: Bearer <token>`
    
    ### MFA Obligatoire
    Après login, un code à 6 chiffres est envoyé par email.  
    Valider via `/api/auth/verify-mfa` pour obtenir le token final.
    """,
    csrf=False,
    docs_url="/docs",
)

# ─── Enregistrement des routers ───────────────────────────────────────────────
api.add_router("/auth/", users_router, tags=["Authentification & Utilisateurs"])
api.add_router("/terrain/", terrain_router, tags=["Terrain & Inventaire"])
api.add_router("/carte/", cartographie_router, tags=["Cartographie SIG"])
api.add_router("/reservations/", reservations_router, tags=["Réservations"])
api.add_router("/concessions/", concessions_router, tags=["Concessions & Exhumations"])
api.add_router("/finance/", finance_router, tags=["Finance & Facturation"])
api.add_router("/reporting/", reporting_router, tags=["Reporting & Statistiques"])

# ─── URLs Django ──────────────────────────────────────────────────────────────
urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", api.urls),
]

# Servir les fichiers media en développement
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
