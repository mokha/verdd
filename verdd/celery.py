from __future__ import absolute_import, unicode_literals
import os
from celery import Celery

# Get the environment setting from an environment variable
env = os.getenv("DEPLOYMENT_SETTINGS", "development")

if env == "production":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "verdd.settings.production")
else:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "verdd.settings.development")

app = Celery("verdd")

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Load task modules from all registered Django apps.
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
