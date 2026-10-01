"""Send synthetic payment data only. WEBHOOK_SECRET must match the server."""
import hashlib
import hmac
import json
import os
import time
import urllib.request

body = json.dumps({'event_id': 'evt_demo_1', 'type': 'payment.captured', 'data': {'payment_id': 'pay_demo_1', 'amount_minor': 149900, 'currency': 'INR'}}).encode()
timestamp = str(int(time.time()))
signature = hmac.new(os.environ['WEBHOOK_SECRET'].encode(), timestamp.encode() + b'.' + body, hashlib.sha256).hexdigest()
request = urllib.request.Request('http://127.0.0.1:8000/api/webhooks/', data=body, headers={'Content-Type': 'application/json', 'X-Webhook-Timestamp': timestamp, 'X-Webhook-Signature': signature})
with urllib.request.urlopen(request, timeout=10) as response:
    print(response.read().decode())
