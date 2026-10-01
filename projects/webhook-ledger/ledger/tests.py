import hashlib
import hmac
import json
import time
from datetime import timedelta
from unittest.mock import patch
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from .models import Event, Payment
from .processing import process_event


class WebhookTests(TestCase):
    def setUp(self):
        self.payload = {'event_id': 'evt_demo_1', 'type': 'payment.captured', 'data': {'payment_id': 'pay_demo_1', 'amount_minor': 149900, 'currency': 'INR'}}

    def send(self, payload=None, timestamp=None, signature=None, raw=None):
        body = raw if raw is not None else json.dumps(self.payload if payload is None else payload).encode()
        timestamp = str(int(time.time()) if timestamp is None else timestamp)
        expected = hmac.new(settings.WEBHOOK_SECRET.encode(), timestamp.encode() + b'.' + body, hashlib.sha256).hexdigest()
        return self.client.post('/api/webhooks/', data=body, content_type='application/json', HTTP_X_WEBHOOK_TIMESTAMP=timestamp, HTTP_X_WEBHOOK_SIGNATURE=expected if signature is None else signature)

    def test_accept_and_process(self):
        self.assertEqual(self.send().status_code, 202)
        event = Event.objects.get()
        self.assertEqual(Payment.objects.count(), 0)
        self.assertTrue(process_event(event.pk))
        event.refresh_from_db()
        self.assertEqual(event.status, 'processed')
        self.assertEqual(Payment.objects.get().amount_minor, 149900)

    def test_duplicate_event(self):
        self.send()
        self.assertTrue(self.send().json()['duplicate'])
        self.assertEqual(Event.objects.count(), 1)

    def test_duplicate_key_order(self):
        self.send()
        self.assertTrue(self.send(raw=json.dumps(self.payload, sort_keys=True, indent=2).encode()).json()['duplicate'])

    def test_payload_conflict(self):
        self.send()
        self.payload['data']['amount_minor'] = 200
        self.assertEqual(self.send().status_code, 409)

    def test_bad_signature(self):
        self.assertEqual(self.send(signature='bad').status_code, 401)
        self.assertFalse(Event.objects.exists())

    def test_unicode_signature(self):
        self.assertEqual(self.send(signature='é').status_code, 401)

    def test_old_timestamp(self):
        self.assertEqual(self.send(timestamp=int(time.time()) - 301).status_code, 401)

    def test_future_timestamp(self):
        self.assertEqual(self.send(timestamp=int(time.time()) + 301).status_code, 401)

    def test_non_numeric_timestamp(self):
        self.assertEqual(self.send(timestamp='oops').status_code, 401)

    def test_invalid_json(self):
        self.assertEqual(self.send(raw=b'{').status_code, 400)

    def test_non_object_payload(self):
        self.assertEqual(self.send(payload=[]).status_code, 400)

    def test_unsupported_event(self):
        self.payload['type'] = 'other'
        self.assertEqual(self.send().status_code, 400)

    def test_invalid_fields(self):
        for key, value in [('payment_id', ''), ('amount_minor', True), ('amount_minor', 0), ('amount_minor', -1), ('amount_minor', 2**63), ('currency', 'inr'), ('currency', '€€€')]:
            with self.subTest(key=key, value=value):
                payload = json.loads(json.dumps(self.payload))
                payload['data'][key] = value
                self.assertEqual(self.send(payload).status_code, 400)
        self.assertFalse(Event.objects.exists())

    def test_invalid_event_id(self):
        for value in ['', ' ' * 5, 1, 'a' * 129]:
            self.payload['event_id'] = value
            self.assertEqual(self.send().status_code, 400)

    def test_oversize_body(self):
        self.assertEqual(self.send(raw=b'x' * 65537).status_code, 413)

    def test_worker_redelivery(self):
        self.send()
        event = Event.objects.get()
        process_event(event.pk)
        self.assertFalse(process_event(event.pk))
        self.assertEqual(Payment.objects.count(), 1)

    def test_same_payment_two_events(self):
        self.send()
        process_event(Event.objects.get().pk)
        self.payload['event_id'] = 'evt_demo_2'
        self.send()
        process_event(Event.objects.get(event_id='evt_demo_2').pk)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(Event.objects.filter(status='processed').count(), 2)

    def test_conflicting_payment_is_dead(self):
        self.send()
        process_event(Event.objects.get().pk)
        self.payload['event_id'] = 'evt_demo_2'
        self.payload['data']['amount_minor'] = 2
        self.send()
        event = Event.objects.get(event_id='evt_demo_2')
        process_event(event.pk)
        event.refresh_from_db()
        self.assertEqual(event.status, 'dead')
        self.assertEqual(Payment.objects.get().amount_minor, 149900)

    def test_transient_retry_and_recovery(self):
        self.send()
        event = Event.objects.get()
        with patch('ledger.processing.apply_payment', side_effect=TimeoutError('private info')):
            process_event(event.pk)
        event.refresh_from_db()
        self.assertEqual(event.status, 'retry')
        self.assertEqual(event.last_error, 'TimeoutError')
        self.assertFalse(process_event(event.pk))
        event.next_attempt_at = timezone.now() - timedelta(seconds=1)
        event.save()
        process_event(event.pk)
        event.refresh_from_db()
        self.assertEqual(event.status, 'processed')
        self.assertEqual(event.attempts, 2)

    def test_retry_limit(self):
        self.send()
        event = Event.objects.get()
        event.attempts = 4
        event.save()
        with patch('ledger.processing.apply_payment', side_effect=TimeoutError):
            process_event(event.pk)
        event.refresh_from_db()
        self.assertEqual(event.status, 'dead')
        self.assertFalse(process_event(event.pk))

    def test_partial_write_rolled_back(self):
        self.send()
        event = Event.objects.get()

        def failing_handler(event):
            Payment.objects.create(payment_id='partial', amount_minor=100, currency='INR', event=event)
            raise TimeoutError

        with patch('ledger.processing.apply_payment', side_effect=failing_handler):
            process_event(event.pk)
        self.assertFalse(Payment.objects.exists())
        event.refresh_from_db()
        self.assertEqual(event.status, 'retry')

    def test_event_list_permissions(self):
        self.send()
        self.assertEqual(self.client.get('/api/events/').status_code, 401)
        user = get_user_model().objects.create_user('staff', is_staff=False)
        # Basic authentication is the documented API method; use DRF's force_authenticate for permission checks.
        from rest_framework.test import APIClient
        api = APIClient()
        api.force_authenticate(user=user)
        self.assertEqual(api.get('/api/events/').status_code, 403)
        user.is_staff = True
        user.save()
        result = api.get('/api/events/?status=pending')
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()['count'], 1)
        self.assertNotIn('payload', result.json()['results'][0])

    def test_health(self):
        self.assertEqual(self.client.get('/health/').json(), {'status': 'ok'})
