import time
from django.core.management.base import BaseCommand
from django.utils import timezone
from ledger.models import Event
from ledger.processing import process_event


class Command(BaseCommand):
    help = 'Process the durable webhook inbox. Use --once for one batch.'

    def add_arguments(self, parser):
        parser.add_argument('--once', action='store_true')

    def handle(self, *args, **options):
        while True:
            ids = list(Event.objects.filter(status__in=['pending', 'retry'], next_attempt_at__lte=timezone.now()).order_by('next_attempt_at', 'pk').values_list('pk', flat=True)[:100])
            count = sum(process_event(pk) for pk in ids)
            if options['once']:
                self.stdout.write(f'Processed {count} event(s).')
                return
            if not ids:
                time.sleep(1)
