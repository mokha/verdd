from django.core.management.base import BaseCommand, CommandError
import io, csv, os
from ._private import *
import logging
from manageXML.models import *

logger = logging.getLogger("verdd")  # Get an instance of a logger


class Command(BaseCommand):
    """
    Example: python manage.py approve_relations -f ../data/to-approve.csv -d ';'
    """

    help = "This command approves all relations in the passed file. The relation ID should be in the first column."

    def add_arguments(self, parser):
        parser.add_argument(
            "-f",
            "--file",
            type=str,
            help="The CSV file to import.",
        )
        parser.add_argument(
            "-d",
            "--delimiter",
            type=str,
            nargs="?",
            default=";",
            help="The delimiter to use when reading the CSV file.",
        )

    def handle(self, *args, **options):
        file_path = options["file"]
        d = options["delimiter"]

        if not os.path.isfile(file_path):
            raise CommandError('File "%s" does not exist.' % file_path)

        with io.open(file_path, "r", encoding="utf-8") as fp:
            reader = csv.reader(fp, delimiter=d)
            rows = list(reader)
            rows = [r for r in rows if len(r) > 0]
            ids = [r[0] for r in rows]
            Relation.objects.filter(pk__in=ids).update(checked=True)

        self.stdout.write(
            self.style.SUCCESS('Successfully processed the file "%s"' % (file_path,))
        )
