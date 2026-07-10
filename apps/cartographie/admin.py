from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin
from .models import Caveau, JournalModificationCaveau


@admin.register(Caveau)
class CaveauAdmin(GISModelAdmin):
    list_display = ("numero", "bloc", "statut", "rangee", "colonne", "date_modification")
    list_filter = ("statut", "bloc__zone")
    search_fields = ("numero",)
    readonly_fields = ("date_creation", "date_modification")


@admin.register(JournalModificationCaveau)
class JournalModificationCaveauAdmin(admin.ModelAdmin):
    list_display = ("caveau", "ancien_statut", "nouveau_statut", "utilisateur", "horodatage", "ip_address")
    list_filter = ("ancien_statut", "nouveau_statut")
    search_fields = ("caveau__numero", "utilisateur__email")
    readonly_fields = [f.name for f in JournalModificationCaveau._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
