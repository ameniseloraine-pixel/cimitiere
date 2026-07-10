from django.contrib import admin
from .models import Concession, Exhumation


@admin.register(Concession)
class ConcessionAdmin(admin.ModelAdmin):
    list_display = ("numero_contrat", "titulaire", "type_concession", "statut", "date_debut", "date_fin")
    list_filter = ("statut", "type_concession")
    search_fields = ("numero_contrat", "titulaire__email")
    readonly_fields = ("numero_contrat", "date_signature")


@admin.register(Exhumation)
class ExhumationAdmin(admin.ModelAdmin):
    list_display = ("numero_demande", "concession", "demandeur", "statut", "date_demande")
    list_filter = ("statut",)
    search_fields = ("numero_demande", "demandeur__email")
    readonly_fields = ("numero_demande", "date_demande")
