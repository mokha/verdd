from django.conf import settings
from django.core.files.storage import FileSystemStorage
import tempfile


class TemporaryFileStorage(FileSystemStorage):
    def __init__(self, *args, **kwargs):
        # Use tempfile.gettempdir() to ensure it's cross-platform
        tmp_dir = getattr(settings, "GENERATED_FILES_TMP_DIR", tempfile.gettempdir())
        kwargs["location"] = tmp_dir
        super().__init__(*args, **kwargs)
