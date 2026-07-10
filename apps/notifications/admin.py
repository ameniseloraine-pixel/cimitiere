from django.contrib import admin
from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("destinataire", "type_notification", "statut", "sujet", "date_creation", "date_envoi")
    list_filter = ("type_notification", "statut")
    search_fields = ("destinataire__email", "sujet")
    readonly_fields = [f.name for f in Notification._meta.fields]

    def has_add_permission(self, request):
        return False
