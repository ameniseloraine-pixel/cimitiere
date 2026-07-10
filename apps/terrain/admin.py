from django.contrib import admin
from .models import Cimetiere, Zone, Bloc


@admin.register(Cimetiere)
class CimetiereAdmin(admin.ModelAdmin):
    list_display = ("nom", "ville", "superficie_totale_m2", "capacite_theorique_totale")
    search_fields = ("nom", "ville")


class BlocInline(admin.TabularInline):
    model = Bloc
    extra = 0


@admin.register(Zone)
class ZoneAdmin(admin.ModelAdmin):
    list_display = ("code", "nom", "cimetiere", "type_zone", "superficie_m2", "ordre_affichage")
    list_filter = ("type_zone", "cimetiere")
    search_fields = ("nom", "code")
    inlines = [BlocInline]


@admin.register(Bloc)
class BlocAdmin(admin.ModelAdmin):
    list_display = ("code", "nom", "zone", "nombre_rangees", "nombre_colonnes", "capacite_theorique")
    list_filter = ("zone__cimetiere", "zone")
    search_fields = ("nom", "code")
