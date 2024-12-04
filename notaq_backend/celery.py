# celery.py
from __future__ import absolute_import, unicode_literals
import os
from celery import Celery

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'notaq_backend.settings')

app = Celery('notaq_backend')

# Load task modules from all registered Django app configs.
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

app.conf.broker_connection_retry_on_startup = True

app.conf.beat_schedule = {
    'check-upcoming-events-every-60-seconds': {
        'task': 'calendar_api_service.tasks.update_all_google_calendar_events',
        'schedule': 60.0,  
    },
}