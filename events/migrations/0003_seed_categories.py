from django.db import migrations

CATEGORIES = [
    'Sport',
    'Politika',
    'Tehnologija',
    'Kripto',
    'Ekonomija',
    'Zabava',
    'Nauka',
    'Svet',
]


def seed_categories(apps, schema_editor):
    Category = apps.get_model('events', 'Category')
    for name in CATEGORIES:
        Category.objects.get_or_create(name=name)


def remove_categories(apps, schema_editor):
    Category = apps.get_model('events', 'Category')
    Category.objects.filter(name__in=CATEGORIES).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0002_suggestedevent_event_external_source_id'),
    ]

    operations = [
        migrations.RunPython(seed_categories, remove_categories),
    ]
