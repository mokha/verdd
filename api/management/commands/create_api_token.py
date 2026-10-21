from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from rest_framework.authtoken.models import Token


class Command(BaseCommand):
    help = "Print the API token of a user, creating it if needed."

    def add_arguments(self, parser):
        parser.add_argument("username")
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Replace the existing token with a new one.",
        )

    def handle(self, *args, **options):
        try:
            user = User.objects.get(username=options["username"])
        except User.DoesNotExist:
            raise CommandError("No such user: %s" % options["username"])

        if not (user.is_staff or user.is_superuser):
            self.stderr.write(
                "Warning: %s is not staff, so the API will refuse this token."
                % user.username
            )

        if options["reset"]:
            Token.objects.filter(user=user).delete()
        token, _ = Token.objects.get_or_create(user=user)
        self.stdout.write(token.key)
