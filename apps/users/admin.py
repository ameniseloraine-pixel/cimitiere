from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Utilisateur, CodeMFA, SessionUtilisateur


@admin.register(Utilisateur)
class UtilisateurAdmin(UserAdmin):
    model = Utilisateur
    list_display = ("email", "nom", "prenom", "role", "is_active", "mfa_activee", "date_creation")
    list_filter = ("role", "is_active", "mfa_activee")
    search_fields = ("email", "nom", "prenom")
    ordering = ("-date_creation",)
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Informations personnelles", {"fields": ("nom", "prenom", "telephone")}),
        ("Rôle & Permissions", {"fields": ("role", "is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("MFA", {"fields": ("mfa_activee",)}),
        ("Dates", {"fields": ("last_login", "date_creation", "date_modification")}),
    )
    add_fieldsets = (
        (None, {"fields": ("email", "nom", "prenom", "role", "password1", "password2")}),
    )
    readonly_fields = ("date_creation", "date_modification", "last_login")


@admin.register(CodeMFA)
class CodeMFAAdmin(admin.ModelAdmin):
    list_display = ("utilisateur", "code", "cree_le", "expire_le", "utilise", "tentatives")
    list_filter = ("utilise",)
    search_fields = ("utilisateur__email",)
    readonly_fields = ("code", "cree_le", "expire_le")


@admin.register(SessionUtilisateur)
class SessionUtilisateurAdmin(admin.ModelAdmin):
    list_display = ("utilisateur", "ip_address", "cree_le", "expire_le", "revoquee")
    list_filter = ("revoquee",)
    search_fields = ("utilisateur__email", "ip_address")
