from django.core.management.base import BaseCommand, CommandError
import io, csv, os
from manageXML.models import *
from datetime import datetime
import logging
from django.db import IntegrityError
from django.db.models import Count

logger = logging.getLogger('verdd')  # Get an instance of a logger


def log_change(lexeme_id, lexeme, edit, note):
    logger.info(
        "%s (%d): [%s] %s on %s" % (lexeme, lexeme_id, edit, note, datetime.now().strftime("%d-%b-%Y (%H:%M:%S.%f)"))
    )


def merge(main_obj, other_objs=[]):
    pass


def process(row, fields_length=4):
    lexemes = [row[x:x + fields_length] for x in range(0, len(row), fields_length)]
    try:
        lexemes = [Lexeme.objects.get(pk=_l[0]) for _l in lexemes if len(_l) == fields_length and _l[0]]
        merge(lexemes[0], lexemes[1:])
    except Exception as ex:
        logger.info("Couldn't merge row {} because '{}'".format("\t".join(row), repr(ex)))


class Command(BaseCommand):
    '''
    Example: python manage.py merge_stems
    '''

    help = 'This command merges duplicate stems'

    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options):
        lexemes = Lexeme.objects.prefetch_related('stem_set').annotate(stem_count=Count('stem')).filter(stem_count__gt=1)
        for lexeme in lexemes:
            dup_stems = lexeme.stem_set.filter
        self.stdout.write(self.style.SUCCESS('Successfully merged all duplicate stems'))
