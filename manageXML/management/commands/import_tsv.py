from django.core.management.base import BaseCommand
from manageXML.models import *
import io, csv


class Command(BaseCommand):
    help = 'This command imports a TSV file into the database to be edited.'

    def add_arguments(self, parser):
        parser.add_argument('-f', '--file', type=str, help='The TSV file to import.', )

    def _create_element(self):
        e = Element(lexeme='X')
        e.save()

    def handle(self, *args, **options):
        file_path = options['file']

        with io.open(file_path, 'r', encoding='utf-8') as fp:
            reader = csv.DictReader(fp, dialect='excel-tab')
            for row in reader:
                print(row)
                self._create_element()

        self.stdout.write(self.style.SUCCESS('Successfully imported the file "%s"' % file_path))
