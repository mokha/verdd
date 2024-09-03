from django.core.mail import send_mail
from django.conf import settings


def send_file_ready_email(file_request):
    subject = "Your download is ready"
    message = f"Dear {file_request.user.username}, your requested download is now available. Please log in to your account to download the file."
    recipient_list = [file_request.user.email]
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, recipient_list)
