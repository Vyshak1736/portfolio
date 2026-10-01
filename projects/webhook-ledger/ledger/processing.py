from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from .models import Event, Payment

MAX_ATTEMPTS = 5


class PermanentFailure(Exception):
    pass


def apply_payment(event):
    data = event.payload['data']
    payment, created = Payment.objects.get_or_create(
        payment_id=data['payment_id'],
        defaults={'amount_minor': data['amount_minor'], 'currency': data['currency'], 'event': event},
    )
    if not created and (payment.amount_minor != data['amount_minor'] or payment.currency != data['currency']):
        raise PermanentFailure('payment_id_payload_conflict')


def process_event(event_pk):
    # Lock and ledger write share a transaction: a crash rolls back both.
    # PostgreSQL supports concurrent workers; use only one worker with SQLite.
    with transaction.atomic():
        event = Event.objects.select_for_update().get(pk=event_pk)
        if event.status not in ('pending', 'retry') or event.next_attempt_at > timezone.now():
            return False
        event.attempts += 1
        try:
            # Savepoint rolls back any partial handler writes on failure.
            with transaction.atomic():
                apply_payment(event)
        except PermanentFailure as exc:
            event.status = 'dead'
            event.last_error = str(exc)
        except Exception as exc:
            event.status = 'dead' if event.attempts >= MAX_ATTEMPTS else 'retry'
            event.last_error = type(exc).__name__
            event.next_attempt_at = timezone.now() + timedelta(seconds=min(2 ** event.attempts, 60))
        else:
            event.status = 'processed'
            event.processed_at = timezone.now()
            event.last_error = ''
        event.save()
        return True
