# Andrija Trnavcevic 2023/0242

from django.contrib.auth.hashers import make_password
from django.db import migrations


# Opis: Kreira podrazumevanog admin korisnika ako korisnik sa username-om admin ne postoji.
# Povratna vrednost: Nema povratnu vrednost; upisuje admin korisnika u bazu kroz migraciju.
def create_default_admin(apps, schema_editor):
    User = apps.get_model('accounts', 'User')

    if User.objects.filter(username='admin').exists():
        return

    User.objects.create(
        username='admin',
        password=make_password('admin'),
        first_name='admin',
        last_name='admin',
        email='admin',
        role=3,
        is_staff=True,
        is_superuser=True,
        is_active=True,
        is_banned=False,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_default_admin, migrations.RunPython.noop),
    ]
