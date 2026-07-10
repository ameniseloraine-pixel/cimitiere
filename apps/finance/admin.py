from django.contrib import admin
from .models import Tarif, Facture, LigneFacture, Paiement, TransactionMobileMoney


@admin.register(Tarif)
class TarifAdmin(admin.ModelAdmin):
    list_display = ("type_tarif", "montant_fcfa", "actif", "date_modification")
    list_filter = ("actif",)


class LigneFactureInline(admin.TabularInline):
    model = LigneFacture
    extra = 0
    readonly_fields = ("montant_total",)


class PaiementInline(admin.TabularInline):
    model = Paiement
    extra = 0
    readonly_fields = ("date_paiement",)


@admin.register(Facture)
class FactureAdmin(admin.ModelAdmin):
    list_display = ("numero_facture", "client", "statut", "montant_total", "montant_paye", "solde_restant", "date_emission")
    list_filter = ("statut",)
    search_fields = ("numero_facture", "client__email")
    readonly_fields = ("numero_facture", "date_emission", "sous_total", "montant_tva", "montant_total", "montant_paye")
    inlines = [LigneFactureInline, PaiementInline]


@admin.register(Paiement)
class PaiementAdmin(admin.ModelAdmin):
    list_display = ("facture", "canal", "montant", "date_paiement", "enregistre_par")
    list_filter = ("canal",)
    search_fields = ("facture__numero_facture", "reference_transaction")
    readonly_fields = ("date_paiement",)


@admin.register(TransactionMobileMoney)
class TransactionMobileMoneyAdmin(admin.ModelAdmin):
    """
    Suivi des transactions Mobile Money / Airtel Money simulées.
    Permet de visualiser le cycle complet : initiée -> attente -> confirmée/échouée.
    """
    list_display = (
        "reference", "canal", "telephone", "montant", "statut",
        "tentatives", "date_initiation", "date_confirmation",
    )
    list_filter = ("canal", "statut")
    search_fields = ("reference", "telephone", "facture__numero_facture")
    readonly_fields = (
        "reference", "date_initiation", "date_confirmation",
        "paiement_resultant",
    )

    def has_add_permission(self, request):
        # Les transactions ne se créent que via l'API de simulation,
        # jamais manuellement depuis l'admin.
        return False
