from django.urls import path
from ledger.views import EventList, health, webhook

urlpatterns = [
    path('health/', health),
    path('api/webhooks/', webhook),
    path('api/events/', EventList.as_view()),
]
