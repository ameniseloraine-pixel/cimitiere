"""
API Terrain — Gestion spatiale : Cimetière, Zones, Blocs
CRUD complet + calcul automatique des capacités
"""

from typing import List, Optional
from ninja import Router, Schema
from django.shortcuts import get_object_or_404

from apps.users.api import auth
from .models import Cimetiere, Zone, Bloc

router = Router()


# ─── Schemas ─────────────────────────────────────────────────────────────────

class CimetiereOutSchema(Schema):
    id: int
    nom: str
    adresse: str
    ville: str
    superficie_totale_m2: float
    tombeau_longueur_m: float
    tombeau_largeur_m: float
    pourcentage_chemins: float
    surface_exploitable_m2: float
    superficie_zones_exploitables_m2: float
    superficie_zones_non_exploitables_m2: float
    calcul_base_sur_zones: bool
    surface_tombeau_m2: float
    capacite_theorique_totale: int
    telephone: str
    email_contact: str

class CimetiereCreateSchema(Schema):
    nom: str
    adresse: str
    ville: str
    superficie_totale_m2: float
    tombeau_longueur_m: float = 2.50
    tombeau_largeur_m: float = 1.20
    pourcentage_chemins: float = 20.0
    telephone: str = ""
    email_contact: str = ""

class ZoneOutSchema(Schema):
    id: int
    cimetiere_id: int
    nom: str
    code: str
    type_zone: str
    superficie_m2: float
    description: str
    ordre_affichage: int
    nombre_blocs: int

class ZoneCreateSchema(Schema):
    nom: str
    code: str
    type_zone: str = "EXPLOIT"
    superficie_m2: float
    description: str = ""
    ordre_affichage: int = 0

class BlocOutSchema(Schema):
    id: int
    zone_id: int
    zone_code: str
    nom: str
    code: str
    nombre_rangees: int
    nombre_colonnes: int
    capacite_theorique: int
    nombre_caveaux_reels: int

class BlocCreateSchema(Schema):
    nom: str
    code: str
    nombre_rangees: int = 1
    nombre_colonnes: int = 1

class ErrorSchema(Schema):
    detail: str

class MessageSchema(Schema):
    message: str


# ─── Cimetière ───────────────────────────────────────────────────────────────

def _build_cimetiere_out(c: Cimetiere) -> CimetiereOutSchema:
    return CimetiereOutSchema(
        id=c.id, nom=c.nom, adresse=c.adresse, ville=c.ville,
        superficie_totale_m2=float(c.superficie_totale_m2),
        tombeau_longueur_m=float(c.tombeau_longueur_m),
        tombeau_largeur_m=float(c.tombeau_largeur_m),
        pourcentage_chemins=float(c.pourcentage_chemins),
        surface_exploitable_m2=round(c.surface_exploitable_m2, 2),
        superficie_zones_exploitables_m2=round(c.superficie_zones_exploitables_m2, 2),
        superficie_zones_non_exploitables_m2=round(c.superficie_zones_non_exploitables_m2, 2),
        calcul_base_sur_zones=c.zones.exists(),
        surface_tombeau_m2=round(c.surface_tombeau_m2, 2),
        capacite_theorique_totale=c.capacite_theorique_totale,
        telephone=c.telephone,
        email_contact=c.email_contact,
    )


@router.get("/cimetiere", response=List[CimetiereOutSchema], auth=auth)
def liste_cimetieres(request):
    """Liste tous les cimetières avec leurs capacités calculées."""
    return [_build_cimetiere_out(c) for c in Cimetiere.objects.all()]


@router.post("/cimetiere", response={201: CimetiereOutSchema, 403: ErrorSchema}, auth=auth)
def creer_cimetiere(request, data: CimetiereCreateSchema):
    """Créer un cimetière (Admin uniquement)."""
    if not request.auth.est_admin:
        return 403, {"detail": "Seul un administrateur peut créer un cimetière."}
    c = Cimetiere.objects.create(**data.dict())
    return 201, _build_cimetiere_out(c)


@router.put("/cimetiere/{cimetiere_id}", response={200: CimetiereOutSchema, 403: ErrorSchema, 404: ErrorSchema}, auth=auth)
def modifier_cimetiere(request, cimetiere_id: int, data: CimetiereCreateSchema):
    """Modifier les paramètres d'un cimetière (Admin uniquement)."""
    if not request.auth.est_admin:
        return 403, {"detail": "Permission insuffisante."}
    c = get_object_or_404(Cimetiere, id=cimetiere_id)
    for attr, value in data.dict().items():
        setattr(c, attr, value)
    c.save()
    return 200, _build_cimetiere_out(c)


# ─── Zones ───────────────────────────────────────────────────────────────────

@router.get("/cimetiere/{cimetiere_id}/zones", response=List[ZoneOutSchema], auth=auth)
def liste_zones(request, cimetiere_id: int):
    """Liste toutes les zones d'un cimetière."""
    zones = Zone.objects.filter(cimetiere_id=cimetiere_id).prefetch_related("blocs")
    return [
        ZoneOutSchema(
            id=z.id, cimetiere_id=z.cimetiere_id,
            nom=z.nom, code=z.code, type_zone=z.type_zone,
            superficie_m2=float(z.superficie_m2),
            description=z.description,
            ordre_affichage=z.ordre_affichage,
            nombre_blocs=z.blocs.count(),
        )
        for z in zones
    ]


@router.post("/cimetiere/{cimetiere_id}/zones", response={201: ZoneOutSchema, 403: ErrorSchema, 404: ErrorSchema}, auth=auth)
def creer_zone(request, cimetiere_id: int, data: ZoneCreateSchema):
    """Créer une zone dans un cimetière (Admin/Agent terrain)."""
    if not request.auth.peut_modifier_carte:
        return 403, {"detail": "Permission insuffisante pour modifier le terrain."}
    cimetiere = get_object_or_404(Cimetiere, id=cimetiere_id)
    z = Zone.objects.create(cimetiere=cimetiere, **data.dict())
    return 201, ZoneOutSchema(
        id=z.id, cimetiere_id=z.cimetiere_id,
        nom=z.nom, code=z.code, type_zone=z.type_zone,
        superficie_m2=float(z.superficie_m2),
        description=z.description,
        ordre_affichage=z.ordre_affichage,
        nombre_blocs=0,
    )


@router.delete("/zones/{zone_id}", response={200: MessageSchema, 403: ErrorSchema, 404: ErrorSchema}, auth=auth)
def supprimer_zone(request, zone_id: int):
    """Supprimer une zone (Admin uniquement, si aucun caveau occupé)."""
    if not request.auth.est_admin:
        return 403, {"detail": "Seul un administrateur peut supprimer une zone."}
    zone = get_object_or_404(Zone, id=zone_id)
    from apps.cartographie.models import Caveau, StatutCaveau
    caveaux_occupes = Caveau.objects.filter(
        bloc__zone=zone, statut=StatutCaveau.OCCUPE
    ).count()
    if caveaux_occupes > 0:
        return 403, {"detail": f"Impossible : {caveaux_occupes} caveau(x) occupé(s) dans cette zone."}
    zone.delete()
    return 200, {"message": f"Zone '{zone.nom}' supprimée."}


# ─── Blocs ───────────────────────────────────────────────────────────────────

@router.get("/zones/{zone_id}/blocs", response=List[BlocOutSchema], auth=auth)
def liste_blocs(request, zone_id: int):
    """Liste tous les blocs d'une zone avec leur occupation réelle."""
    blocs = Bloc.objects.filter(zone_id=zone_id).prefetch_related("caveaux")
    return [
        BlocOutSchema(
            id=b.id, zone_id=b.zone_id, zone_code=b.zone.code,
            nom=b.nom, code=b.code,
            nombre_rangees=b.nombre_rangees,
            nombre_colonnes=b.nombre_colonnes,
            capacite_theorique=b.capacite_theorique,
            nombre_caveaux_reels=b.caveaux.count(),
        )
        for b in blocs
    ]


@router.post("/zones/{zone_id}/blocs", response={201: BlocOutSchema, 403: ErrorSchema, 404: ErrorSchema}, auth=auth)
def creer_bloc(request, zone_id: int, data: BlocCreateSchema):
    """Créer un bloc dans une zone (Admin/Agent terrain)."""
    if not request.auth.peut_modifier_carte:
        return 403, {"detail": "Permission insuffisante."}
    zone = get_object_or_404(Zone, id=zone_id)
    b = Bloc.objects.create(zone=zone, **data.dict())
    return 201, BlocOutSchema(
        id=b.id, zone_id=b.zone_id, zone_code=zone.code,
        nom=b.nom, code=b.code,
        nombre_rangees=b.nombre_rangees,
        nombre_colonnes=b.nombre_colonnes,
        capacite_theorique=b.capacite_theorique,
        nombre_caveaux_reels=0,
    )


@router.post("/blocs/{bloc_id}/generer-caveaux", response={201: MessageSchema, 403: ErrorSchema, 404: ErrorSchema, 400: ErrorSchema}, auth=auth)
def generer_caveaux_bloc(request, bloc_id: int, latitude_origine: float = -4.7761, longitude_origine: float = 11.8636, espacement_m: float = 0.5):
    """
    Génère automatiquement tous les caveaux d'un bloc
    selon sa configuration rangées × colonnes.
    Positionne les caveaux avec un espacement GPS calculé.
    Par défaut, centré sur Pointe-Noire si aucune coordonnée n'est précisée.
    """
    if not request.auth.peut_modifier_carte:
        return 403, {"detail": "Permission insuffisante."}
    bloc = get_object_or_404(Bloc, id=bloc_id)

    from apps.cartographie.models import Caveau
    from django.contrib.gis.geos import Point

    if bloc.caveaux.exists():
        return 400, {"detail": f"Le bloc {bloc.code} contient déjà des caveaux. Supprimez-les d'abord."}

    espacement_lat = espacement_m / 111000
    espacement_lon = espacement_m / 111000

    caveaux_a_creer = []
    for rangee in range(1, bloc.nombre_rangees + 1):
        for colonne in range(1, bloc.nombre_colonnes + 1):
            numero = f"{bloc.zone.code}{bloc.code}-{rangee:02d}{colonne:02d}"
            lat = latitude_origine + (rangee - 1) * espacement_lat
            lon = longitude_origine + (colonne - 1) * espacement_lon
            caveaux_a_creer.append(Caveau(
                bloc=bloc,
                numero=numero,
                rangee=rangee,
                colonne=colonne,
                localisation=Point(round(lon, 7), round(lat, 7), srid=4326),
            ))

    Caveau.objects.bulk_create(caveaux_a_creer)
    total = len(caveaux_a_creer)
    return 201, {"message": f"{total} caveau(x) générés pour le bloc {bloc.code}."}