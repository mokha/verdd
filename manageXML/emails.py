from django.core.mail import send_mail
from django.conf import settings
from manageXML.constants import DOWNLOAD_TYPES
from manageXML.models import FileRequest


def send_file_ready_email(file_request: FileRequest):
    subject = f"Your {DOWNLOAD_TYPES[file_request.type]} download for {file_request.lang_source.id}-{file_request.lang_target.id} "

    subject += (
        "is ready" if file_request.status == file_request.STATUS_COMPLETED else "failed"
    )

    message = f"Dear {file_request.user.username},\n"
    message += f"Your requested download for {DOWNLOAD_TYPES[file_request.type]} ({file_request.lang_source.id}-{file_request.lang_target.id}) "
    message += (
        "is now available. Please log in to your account to download the file."
        if file_request.status == file_request.STATUS_COMPLETED
        else "has failed. Please report it and try again later."
    )
    recipient_list = [file_request.user.email]
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, recipient_list)
