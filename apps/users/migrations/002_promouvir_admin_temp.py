"""
Migration de données : promeut un compte existant en administrateur Django
(is_staff + is_superuser) pour permettre l'accès à /admin/ sans passer
par le Shell Render (payant).

Ne plante jamais si le compte n'existe pas encore : dans ce cas, ne fait
simplement rien (utile car les migrations s'exécutent à chaque déploiement,
même avant que ce compte n'ait été créé).
"""
from django.db import migrations

EMAIL_A_PROMOUVOIR = "ameniseloraine@gmail.com"


def promouvoir(apps, schema_editor):
    Utilisateur = apps.get_model("users", "Utilisateur")
    Utilisateur.objects.filter(email__iexact=EMAIL_A_PROMOUVOIR).update(
        is_staff=True,
        is_superuser=True,
        is_active=True,
    )


def revenir_en_arriere(apps, schema_editor):
    # Volontairement neutre : on ne rétrograde jamais automatiquement
    # un compte admin lors d'un "unmigrate".
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(promouvoir, reverse_code=revenir_en_arriere),
    ]
