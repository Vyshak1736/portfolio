from django.db import models
from django.utils import timezone


class Event(models.Model):
    event_id = models.CharField(max_length=128, unique=True)
    payload = models.JSONField()
    payload_hash = models.CharField(max_length=64)
    status = models.CharField(max_length=16, default='pending')
    attempts = models.PositiveIntegerField(default=0)
    next_attempt_at = models.DateTimeField(default=timezone.now)
    last_error = models.CharField(max_length=100, blank=True)
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True)

    class Meta:
        indexes = [models.Index(fields=['status', 'next_attempt_at'])]


class Payment(models.Model):
    payment_id = models.CharField(max_length=128, unique=True)
    amount_minor = models.PositiveBigIntegerField()
    currency = models.CharField(max_length=3)
    event = models.OneToOneField(Event, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
