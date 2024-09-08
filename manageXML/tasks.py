from celery import shared_task
from django.core.files.base import ContentFile
from .models import FileRequest

from .services import generate_file_for_request
from .emails import send_file_ready_email


@shared_task
def process_file_request(
    file_request_id, download_type, lang_source, lang_target=None, options={}
):
    file_request = FileRequest.objects.get(id=file_request_id)

    try:
        file_request.mark_processing()

        # Generate the file based on request parameters
        file_content = generate_file_for_request(
            download_type,
            lang1=lang_source,
            lang2=lang_target,
            approved=options["use_accepted"],
        )

        # Securely save the file to the request
        file_name = f"{download_type}_{file_request.user.id}.zip"
        file_request.file.save(file_name, ContentFile(file_content))

        # Mark as completed and send notification
        file_request.mark_completed(file_request.file.name, output="ok")

    except Exception as e:
        file_request.mark_failed(str(e))
        # Log the error for debugging

    try:
        send_file_ready_email(file_request)
    except Exception as e:
        pass
