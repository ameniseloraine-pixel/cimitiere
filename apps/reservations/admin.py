from django.contrib import admin
from .models import Reservation, Defunt


@admin.register(Defunt)
class DefuntAdmin(admin.ModelAdmin):
    list_display = ("nom", "prenom", "date_naissance", "date_deces", "age_au_deces")
    search_fields = ("nom", "prenom")


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ("numero_dossier", "client", "caveau", "statut", "date_soumission", "validee_par")
    list_filter = ("statut", "date_soumission")
    search_fields = ("numero_dossier", "client__email", "defunt__nom")
    readonly_fields = ("numero_dossier", "date_soumission", "date_validation")
    autocomplete_fields = ["client", "caveau", "defunt"]
