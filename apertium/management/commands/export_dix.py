from django.core.management.base import (BaseCommand, CommandError)
from itertools import groupby
from django.template.loader import render_to_string
from io import open, BytesIO
import os
from django.conf import settings
from zipfile import ZipFile
import uuid
import time
from django.db.models.functions import Cast, Substr, Upper
from django.db.models import Prefetch, F, Value, When, Case
from manageXML.models import *
from manageXML.utils import *
import operator
from functools import reduce


def export_monodix(src_lang, tgt_lang, directory_path, ignore_file=None):
    raise NotImplementedError("Not implemented yet.")


def export_bidix(src_lang, tgt_lang, directory_path, ignore_file=None):
    relations = Relation.objects.filter(type=TRANSLATION)
    if ignore_file:
        to_ignore_ids = read_first_ids_from(ignore_file)
        relations = relations.exclude(pk__in=to_ignore_ids)

    relations = relations \
        .prefetch_related(
        Prefetch('lexeme_from', queryset=Lexeme.objects.prefetch_related('miniparadigm_set')),
        Prefetch('lexeme_to', queryset=Lexeme.objects.prefetch_related('miniparadigm_set')),
        'relationexample_set', 'relationmetadata_set') \
        .filter(lexeme_from__language=src_lang, lexeme_to__language=tgt_lang) \
        .order_by('lexeme_from__lexeme_lang') \
        .all()

    # alphabets
    alphabet = ''

    # sdefs
    lexemes = Lexeme.objects.filter(Q(language='myv') | Q(language='mdf')).prefetch_related('lexememetadata_set').all()
    symbols = set(reduce(operator.add, [_l.symbols() for _l in lexemes]))
    system_symbols = Symbol.all_dict()
    sdefs = {s: system_symbols[s] for s in symbols if s in system_symbols}

    # save
    xml = render_to_string("export/bidix_xml.html", {'alphabet': alphabet, 'sdefs': sdefs, 'relations': relations})
    _filename = "apertium-{}-{}.{}-{}-{}.dix".format(
        src_lang,
        tgt_lang,
        src_lang,
        tgt_lang,
        time.strftime("%Y%m%d-%H%M")
    )
    with open("{}/{}".format(directory_path, _filename), 'w') as f:
        f.write(xml)


def export(src_lang, tgt_lang, directory_path, ignore_file=None):
    export_fn = export_bidix if tgt_lang else export_monodix
    return export_fn(src_lang, tgt_lang, directory_path, ignore_file)


class Command(BaseCommand):
    """

    """

    help = 'Command to export an XML version of the dictionary.'

    def add_arguments(self, parser):
        parser.add_argument('-d', '--dir', type=str, help='The directory path where to store the XMLs in.', )
        parser.add_argument('-s', '--source', type=str, help='Three letter code of source language.', )
        parser.add_argument('-t', '--target', type=str, nargs='?', default=None,
                            help='Three letter code of target language.', )
        parser.add_argument('-i', '--ignore', type=str, nargs='?', default=None,
                            help='A file containing relations to be ignored. '
                                 'The first value must be the ID of the relation.', )

    def success_info(self, info):
        return self.stdout.write(self.style.SUCCESS(info))

    def error_info(self, info):
        return self.stdout.write(self.style.ERROR(info))

    def handle(self, *args, **options):
        dir_path = options['dir']
        src_lang = options['source']
        tgt_lang = options['target']
        ignore_file = options['ignore']

        if not os.path.isdir(dir_path):
            return self.error_info("The directory doesn't exist!")
        elif ignore_file and not os.path.isfile(ignore_file):
            return self.error_info("The ignore file doesn't exist.")

        export(src_lang, tgt_lang, dir_path, ignore_file)