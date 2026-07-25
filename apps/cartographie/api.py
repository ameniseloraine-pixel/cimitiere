
"""
API Cartographie — Carte interactive SIG
Endpoints : liste des caveaux géolocalisés, changement de statut, GeoJSON
Stockage spatial : PostGIS (PointField, SRID 4326)
"""

from typing import List, Optional
from ninja import Router, Schema
from django.http import HttpResponse
from django.views.decorators.clickjacking import xframe_options_exempt

from apps.users.api import auth
from apps.users.models import RoleUtilisateur, Utilisateur
from apps.users.services import verifier_token_jwt
from .models import Caveau, StatutCaveau, JournalModificationCaveau

router = Router()


class CaveauGeoSchema(Schema):
    id: int
    numero: str
    statut: str
    couleur: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    bloc_code: str
    zone_code: str
    reference: str

class ChangerStatutSchema(Schema):
    statut: str
    raison: Optional[str] = ""

class ErrorSchema(Schema):
    detail: str


def _to_schema(c: Caveau) -> CaveauGeoSchema:
    return CaveauGeoSchema(
        id=c.id,
        numero=c.numero,
        statut=c.statut,
        couleur=c.couleur_carte,
        latitude=float(c.latitude) if c.latitude is not None else None,
        longitude=float(c.longitude) if c.longitude is not None else None,
        bloc_code=c.bloc.code,
        zone_code=c.bloc.zone.code,
        reference=c.reference_complete,
    )


@router.get("/caveaux", response=List[CaveauGeoSchema], auth=auth)
def liste_caveaux(
    request,
    statut: Optional[str] = None,
    zone_code: Optional[str] = None,
    bloc_code: Optional[str] = None,
):
    """
    Retourne tous les caveaux avec leurs coordonnées GPS et couleurs.
    Utilisé pour alimenter la carte interactive.
    Filtrages optionnels par statut, zone ou bloc.
    """
    qs = Caveau.objects.select_related("bloc__zone__cimetiere").all()

    if statut:
        qs = qs.filter(statut=statut)
    if zone_code:
        qs = qs.filter(bloc__zone__code=zone_code)
    if bloc_code:
        qs = qs.filter(bloc__code=bloc_code)

    return [_to_schema(c) for c in qs]


@router.get("/caveaux/geojson", auth=auth)
def caveaux_geojson(request):
    """
    Exporte les caveaux au format GeoJSON standard.
    Compatible avec Leaflet, OpenLayers, etc.
    Seuls les caveaux disposant de coordonnées sont inclus.
    """
    caveaux = (
        Caveau.objects.select_related("bloc__zone")
        .exclude(localisation=None)
    )
    features = []
    for c in caveaux:
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [float(c.longitude), float(c.latitude)],
            },
            "properties": {
                "id": c.id,
                "numero": c.numero,
                "statut": c.statut,
                "couleur": c.couleur_carte,
                "reference": c.reference_complete,
            },
        })
    return {"type": "FeatureCollection", "features": features}


@router.get("/caveaux/{caveau_id}", response={200: CaveauGeoSchema, 404: ErrorSchema}, auth=auth)
def detail_caveau(request, caveau_id: int):
    """Détail d'un caveau spécifique."""
    try:
        c = Caveau.objects.select_related("bloc__zone__cimetiere").get(id=caveau_id)
        return 200, _to_schema(c)
    except Caveau.DoesNotExist:
        return 404, {"detail": "Caveau introuvable."}


@router.patch("/caveaux/{caveau_id}/statut", response={200: CaveauGeoSchema, 403: ErrorSchema, 404: ErrorSchema}, auth=auth)
def changer_statut_caveau(request, caveau_id: int, data: ChangerStatutSchema):
    """
    Change le statut d'un caveau (Agent terrain / Admin uniquement).
    Journalise la modification dans l'audit trail immuable.
    """
    if not request.auth.peut_modifier_carte:
        return 403, {"detail": "Permission insuffisante pour modifier la carte."}

    try:
        caveau = Caveau.objects.select_related("bloc__zone").get(id=caveau_id)
    except Caveau.DoesNotExist:
        return 404, {"detail": "Caveau introuvable."}

    ancien_statut = caveau.statut

    caveau.changer_statut(data.statut, utilisateur=request.auth, raison=data.raison)

    JournalModificationCaveau.objects.create(
        caveau=caveau,
        utilisateur=request.auth,
        ancien_statut=ancien_statut,
        nouveau_statut=data.statut,
        raison=data.raison or "",
        ip_address=request.META.get("REMOTE_ADDR"),
    )

    return 200, _to_schema(caveau)


@router.get("/statistiques", auth=auth)
def statistiques_carte(request):
    """
    Statistiques globales d'occupation pour le dashboard.
    Retourne les comptages par statut et par bloc.
    """
    from django.db.models import Count
    stats_statut = dict(
        Caveau.objects.values("statut").annotate(count=Count("id"))
        .values_list("statut", "count")
    )
    total = sum(stats_statut.values())
    taux_occupation = (
        stats_statut.get(StatutCaveau.OCCUPE, 0) / total * 100
        if total > 0 else 0
    )
    return {
        "total_caveaux": total,
        "par_statut": stats_statut,
        "taux_occupation_pct": round(taux_occupation, 1),
        "disponibles": stats_statut.get(StatutCaveau.DISPONIBLE, 0),
        "occupes": stats_statut.get(StatutCaveau.OCCUPE, 0),
        "reserves": stats_statut.get(StatutCaveau.RESERVE, 0),
    }


# ─────────────────────────────────────────────────────────────────────────────
# NOUVEAU : page HTML de la carte GPS, servie par une vraie URL (corrige le bug
# où les navigateurs bloquent le chargement d'URL "data:" dans une WebView)
# ─────────────────────────────────────────────────────────────────────────────

def _generer_html_carte(caveaux_geo: list) -> str:
    if not caveaux_geo:
        return """
        <html><body style="font-family:sans-serif;text-align:center;
        padding-top:60px;color:#6b7280">
        Aucun caveau ne possède de coordonnées GPS pour le moment.
        </body></html>
        """

    lat_centre = caveaux_geo[0]["latitude"]
    lng_centre = caveaux_geo[0]["longitude"]

    LIBELLES = {
        "DISPO": "Disponible", "RESERVE": "Réservé", "OCCUPE": "Occupé",
        "NON_EXP": "Non exploitable", "MAINT": "En maintenance",
    }

    markers_js = ""
    for c in caveaux_geo:
        libelle = LIBELLES.get(c["statut"], c["statut"])
        popup = (
            f"<div style='font-family:sans-serif;min-width:140px'>"
            f"<strong>{c['reference']}</strong><br>"
            f"<span style='display:inline-block;width:9px;height:9px;border-radius:50%;"
            f"background:{c['couleur']};margin-right:5px'></span>{libelle}"
            f"</div>"
        ).replace('"', "'").replace("\n", "")
        markers_js += f"""
        L.circleMarker([{c['latitude']}, {c['longitude']}], {{
            radius: 10, color: "#ffffff", fillColor: "{c['couleur']}", fillOpacity: 0.95, weight: 2
        }}).addTo(map).bindPopup("{popup}");
        """

    legende_html = "".join(
        f"""<div style="display:flex;align-items:center;gap:6px;margin:3px 0">
              <span style="width:11px;height:11px;border-radius:50%;background:{couleur};
                           border:1.5px solid #fff;box-shadow:0 0 0 1px #d1d5db"></span>
              <span style="font-size:12px;color:#374151">{libelle}</span>
            </div>"""
        for couleur, libelle in [
            ("#22c55e", "Disponible"), ("#f97316", "Réservé"),
            ("#ef4444", "Occupé"), ("#9ca3af", "Non exploitable"),
        ]
    )

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <link rel="stylesheet" href="https://unpkg.com/leaflet/dist/leaflet.css"/>
      <script src="https://unpkg.com/leaflet/dist/leaflet.js"></script>
      <style>
        html, body {{ margin: 0; height: 100%; font-family: sans-serif; }}
        #map {{ height: 100vh; width: 100%; }}
        .legende-carte {{
          position: absolute; top: 12px; right: 12px; z-index: 1000;
          background: #ffffffee; padding: 10px 14px; border-radius: 10px;
          box-shadow: 0 2px 10px rgba(0,0,0,0.15);
        }}
        .legende-titre {{ font-size: 12px; font-weight: 700; color: #1f2937; margin-bottom: 6px; }}
        .compteur-carte {{
          position: absolute; top: 12px; left: 50px; z-index: 1000;
          background: #ffffffee; padding: 6px 14px; border-radius: 20px;
          box-shadow: 0 2px 10px rgba(0,0,0,0.15); font-size: 12px; color: #1f2937;
        }}
        .leaflet-popup-content-wrapper {{ border-radius: 10px; }}
      </style>
    </head>
    <body>
      <div id="map"></div>
      <div class="legende-carte">
        <div class="legende-titre">Légende</div>
        {legende_html}
      </div>
      <div class="compteur-carte">📍 {len(caveaux_geo)} caveau(x) géolocalisé(s)</div>
      <script>
        var map = L.map('map', {{ zoomControl: true }}).setView([{lat_centre}, {lng_centre}], 18);
        L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
          maxZoom: 20,
          attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        }}).addTo(map);
        L.control.scale({{ metric: true, imperial: false }}).addTo(map);
        {markers_js}
      </script>
    </body>
    </html>
    """


@router.get("/carte-html", auth=None)
@xframe_options_exempt
def carte_html(
    request,
    token: str,
    statut: Optional[str] = None,
    zone_code: Optional[str] = None,
    bloc_code: Optional[str] = None,
):
    """
    Sert la carte GPS en HTML autonome, via une vraie URL.
    Exemptée de X-Frame-Options : elle doit pouvoir être intégrée dans la
    WebView du frontend Flet, hébergé sur un domaine différent (Render).
    Le token JWT est passé en paramètre d'URL (le contrôle WebView ne peut
    pas envoyer de header Authorization), et vérifié manuellement ici.
    """
    payload = verifier_token_jwt(token)
    if not payload:
        return HttpResponse(
            "<html><body style='font-family:sans-serif;text-align:center;padding-top:60px'>"
            "Session expirée. Reconnectez-vous puis réessayez.</body></html>",
            content_type="text/html", status=401,
        )
    if not Utilisateur.objects.filter(id=payload["user_id"]).exists():
        return HttpResponse("Utilisateur introuvable.", content_type="text/html", status=401)

    qs = Caveau.objects.select_related("bloc__zone__cimetiere").exclude(localisation=None)
    if statut:
        qs = qs.filter(statut=statut)
    if zone_code:
        qs = qs.filter(bloc__zone__code=zone_code)
    if bloc_code:
        qs = qs.filter(bloc__code=bloc_code)

    caveaux_geo = [
        {
            "reference": c.reference_complete,
            "statut": c.statut,
            "couleur": c.couleur_carte,
            "latitude": float(c.latitude),
            "longitude": float(c.longitude),
        }
        for c in qs
        if c.latitude is not None and c.longitude is not None
    ]

    html = _generer_html_carte(caveaux_geo)
    return HttpResponse(html, content_type="text/html")