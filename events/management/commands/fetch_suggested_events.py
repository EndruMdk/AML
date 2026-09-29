from django.core.management.base import BaseCommand

from events.services import fetch_suggested_events


class Command(BaseCommand):
    help = 'Preuzima predložene Da/Ne događaje sa Polymarket API-ja'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=100)

    def handle(self, *args, **options):
        created = fetch_suggested_events(limit=options['limit'])
        self.stdout.write(self.style.SUCCESS(f'Preuzeto je {created} novih predloženih događaja.'))
