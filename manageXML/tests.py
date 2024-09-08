from django.test import TestCase
from django.contrib.auth.models import User
from .models import FileRequest
from .tasks import process_file_request


# Create your tests here.
class FileRequestTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="12345")
        self.file_request = FileRequest.objects.create(user=self.user)

    def test_process_file_request(self):
        process_file_request(self.file_request.id)
        self.file_request.refresh_from_db()
        self.assertEqual(self.file_request.status, FileRequest.STATUS_COMPLETED)
        self.assertIsNotNone(self.file_request.file)
