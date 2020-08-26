from django.core.management.base import BaseCommand, CommandError
import io, csv, os
from manageXML.models import *
from datetime import datetime
import logging
from django.db import IntegrityError
from manageXML.utils import row_to_objects

logger = logging.getLogger('verdd')  # Get an instance of a logger


def log_change(lexeme_id, lexeme, edit, note):
    logger.info(
        "%s (%d): [%s] %s on %s" % (lexeme, lexeme_id, edit, note, datetime.now().strftime("%d-%b-%Y (%H:%M:%S.%f)"))
    )


def merge(main_obj: Stem, other_objs: tuple = ()):
    for oo in other_objs:
        if oo.contlex and not main_obj.contlex:
            main_obj.notes = oo.contlex
            main_obj.save()
        oo.delete()  # delete duplicate stem


def process(row, fields_length=4):
    try:
        objects = row_to_objects(Stem, row, fields_length, 0)
        merge(objects[0], tuple(objects[1:]))
        logger.info("Merged {}".format("\t".join(row)))
    except Exception as ex:
        logger.info("Couldn't merge row {} because '{}'".format("\t".join(row), repr(ex)))


class Command(BaseCommand):
    '''
    Example: python manage.py merge_stems -f ../data/duplicate-stems.tsv -d '\t' -l 6
    '''

    help = 'This command merges duplicate stems. The first stem in each row is considered the main stem.'

    def add_arguments(self, parser):
        parser.add_argument('-f', '--file', type=str, help='The CSV file to import.', )
        parser.add_argument('-d', '--delimiter', type=str, nargs='?', default=';',
                            help='The delimiter to use when reading the CSV file.', )
        parser.add_argument('-l', '--length', type=int, nargs='?', default=4,
                            help='The number of fields each stem has in the file.')

    def handle(self, *args, **options):
        file_path = options['file']
        d = options['delimiter']
        fields_length = options['length']

        if not os.path.isfile(file_path):
            raise CommandError('File "%s" does not exist.' % file_path)

        with io.open(file_path, 'r', encoding='utf-8') as fp:
            reader = csv.reader(fp, delimiter=d)
            rows = list(reader)
            rows = [r for r in rows if len(r) > 0]
            for r in rows:
                process(r, fields_length)

        self.stdout.write(self.style.SUCCESS('Successfully merged all duplicate stems'))
