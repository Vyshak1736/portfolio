import hashlib
import hmac
import json
import time

from django.conf import settings
from django.core.exceptions import RequestDataTooBig
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from rest_framework import generics, serializers
from .models import Event


@require_GET
def health(request):
    return JsonResponse({'status': 'ok'})


@csrf_exempt
@require_POST
def webhook(request):
    try:
        body = request.body
    except RequestDataTooBig:
        return JsonResponse({'error': 'payload_too_large'}, status=413)
    if len(body) > 65536:
        return JsonResponse({'error': 'payload_too_large'}, status=413)
    timestamp = request.headers.get('X-Webhook-Timestamp', '')
    signature = request.headers.get('X-Webhook-Signature', '')
    try:
        valid_time = abs(time.time() - int(timestamp)) <= 300
    except ValueError:
        valid_time = False
    expected = hmac.new(settings.WEBHOOK_SECRET.encode(), timestamp.encode() + b'.' + body, hashlib.sha256).hexdigest()
    if not valid_time or not hmac.compare_digest(signature.encode(), expected.encode()):
        return JsonResponse({'error': 'invalid_signature_or_timestamp'}, status=401)
    try:
        payload = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({'error': 'invalid_json'}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse({'error': 'expected_object'}, status=400)
    event_id = payload.get('event_id')
    if not isinstance(event_id, str) or not event_id.strip() or len(event_id) > 128:
        return JsonResponse({'error': 'invalid_event_id'}, status=400)
    if payload.get('type') != 'payment.captured':
        return JsonResponse({'error': 'unsupported_event_type'}, status=400)
    data = payload.get('data')
    if not isinstance(data, dict):
        return JsonResponse({'error': 'invalid_payment'}, status=400)
    payment_id, amount, currency = data.get('payment_id'), data.get('amount_minor'), data.get('currency')
    if (not isinstance(payment_id, str) or not payment_id.strip() or len(payment_id) > 128
            or type(amount) is not int or not 0 < amount <= 9223372036854775807
            or not isinstance(currency, str) or len(currency) != 3
            or not currency.isascii() or not currency.isalpha() or currency != currency.upper()):
        return JsonResponse({'error': 'invalid_payment'}, status=400)
    # A semantic hash permits redelivery with different JSON whitespace/key order.
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    event, created = Event.objects.get_or_create(event_id=event_id, defaults={'payload': payload, 'payload_hash': digest})
    if not created and event.payload_hash != digest:
        return JsonResponse({'error': 'event_id_payload_conflict'}, status=409)
    return JsonResponse({'event_id': event.event_id, 'duplicate': not created, 'status': event.status}, status=202)


class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = ['event_id', 'status', 'attempts', 'last_error', 'received_at', 'processed_at']


class EventList(generics.ListAPIView):
    serializer_class = EventSerializer

    def get_queryset(self):
        events = Event.objects.order_by('-received_at', '-id')
        status = self.request.query_params.get('status')
        return events.filter(status=status) if status else events
