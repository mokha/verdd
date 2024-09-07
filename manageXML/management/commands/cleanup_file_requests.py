from django.core.management.base import BaseCommand
from datetime import timedelta
from django.utils import timezone
from manageXML.models import FileRequest


class Command(BaseCommand):
    help = "Clean up old file requests from the database."

    def handle(self, *args, **kwargs):
        old_requests = FileRequest.objects.filter(deleted=False)
        count = old_requests.count()

        for old_request in old_requests:
            old_request.deleted = True
        FileRequest.objects.bulk_update(old_requests, ["deleted"])

        for old_request in old_requests:
            old_request.file.delete(save=False)

        self.stdout.write(
            self.style.SUCCESS(f"Successfully cleaned up {count} file requests.")
        )
