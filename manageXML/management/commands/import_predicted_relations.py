from django.core.management.base import BaseCommand, CommandError
import io, csv, os
from ._private import *
import logging
from manageXML.models import *
from distutils.util import strtobool

logger = logging.getLogger('verdd')  # Get an instance of a logger


class Command(BaseCommand):
    '''
    Example: python manage.py import_predicted_relations -f ../data/to-approve.csv --approve
    '''

    help = 'This command adds the predicted relations in the file and [optionally] approve them.'

    def add_arguments(self, parser):
        parser.add_argument('-f', '--file', type=str, help='The TSV file to import.', )
        parser.add_argument('--approve', type=lambda v: bool(strtobool(v)), nargs='?', const=True, default=False, )

    def handle(self, *args, **options):
        file_path = options['file']
        approve = options['approve']

        if not os.path.isfile(file_path):
            raise CommandError('File "%s" does not exist.' % file_path)

        with io.open(file_path, 'r', encoding='utf-8') as fp:
            reader = csv.reader(fp, delimiter='\t')
            for row in reader:
                if not row:
                    continue
                lexeme_from_id = int(row[0])
                lexeme_to_id = int(row[5])
                try:
                    r = Relation.objects.create(lexeme_from_id=lexeme_from_id, lexeme_to_id=lexeme_to_id,
                                                type=TRANSLATION, checked=approve)
                except Exception as e:
                    r = Relation.objects.get(lexeme_from_id=lexeme_from_id, lexeme_to_id=lexeme_to_id, type=TRANSLATION)
                    r.checked = approve
                    r.save()

        self.stdout.write(self.style.SUCCESS('Successfully imported relations in the file "%s"' % (file_path,)))
