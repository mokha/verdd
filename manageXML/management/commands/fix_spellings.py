from django.core.management.base import BaseCommand, CommandError
import io, csv, os
from ._private import *
from manageXML.models import *
from datetime import datetime
import logging
from .merge_lexemes import merge
from django.db import IntegrityError

logger = logging.getLogger('verdd')  # Get an instance of a logger


def log_change(lexeme_id, lexeme, edit, note):
    logger.info(
        "%s (%d): [%s] %s on %s" % (lexeme, lexeme_id, edit, note, datetime.now().strftime("%d-%b-%Y (%H:%M:%S.%f)"))
    )


def process(row):
    row = [r.strip() for r in row]
    try:
        lexeme = Lexeme.objects.get(pk=row[3])
        if lexeme.pos != row[2]:
            lexeme.pos = row[2]
        lexeme.lexeme = row[1]
        lexeme.save()
    except IntegrityError as ex:
        existing_lexeme = Lexeme.objects.get(language=row[0], lexeme=row[1], pos=row[2])
        merge(existing_lexeme, [lexeme])
    except Exception as ex:
        logger.info("Couldn't merge row {} because '{}'".format("\t".join(row), repr(ex)))


class Command(BaseCommand):
    '''
    Example: python manage.py fix_spellings -f ../data/Adj-workspace_2020-05-19b.csv -d ';'
    '''

    help = 'This command imports fixed spellings for lexemes in the database.' \
           'The format that is expected "lang;correct_spelling;POS;ID;misspelled_word;POS"'

    def add_arguments(self, parser):
        parser.add_argument('-f', '--file', type=str, help='The CSV file to import.', )
        parser.add_argument('-d', '--delimiter', type=str, nargs='?', default=';',
                            help='The delimiter to use when reading the CSV file.', )

    def handle(self, *args, **options):
        file_path = options['file']
        d = options['delimiter']

        if not os.path.isfile(file_path):
            raise CommandError('File "%s" does not exist.' % file_path)

        with io.open(file_path, 'r', encoding='utf-8') as fp:
            reader = csv.reader(fp, delimiter=d)
            rows = list(reader)
            rows = [r for r in rows if len(r) > 0]
            for r in rows:
                process(r)

        self.stdout.write(self.style.SUCCESS('Successfully processed the file "%s"' % (file_path,)))
