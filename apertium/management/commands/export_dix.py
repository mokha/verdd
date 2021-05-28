from django.core.management.base import (BaseCommand, CommandError)
from itertools import groupby
from django.template.loader import render_to_string
from io import open, BytesIO
import os
from django.conf import settings
from zipfile import ZipFile
import uuid
import time
from django.db.models.functions import Cast, Substr, Upper, Concat
from django.db.models import Prefetch, F, Value, When, Case
from manageXML.models import *
from manageXML.utils import *
import operator
from functools import reduce
from distutils.util import strtobool


def export_monodix(src_lang, tgt_lang, directory_path, ignore_file=None, *args, **kwargs):
    raise NotImplementedError("Not implemented yet.")


def export_bidix(left_lang, right_lang, directory_path, ignore_file=None, *args, **kwargs):
    checked = kwargs.get('approved', None)
    sdef_flag = kwargs.get('sdef')

    left_relations = Relation.objects.filter(type=TRANSLATION) \
        .filter(Q(lexeme_from__language=left_lang) & Q(lexeme_to__language=right_lang))
    right_relations = Relation.objects.filter(type=TRANSLATION) \
        .filter(Q(lexeme_from__language=right_lang) & Q(lexeme_to__language=left_lang))

    if checked is not None:
        left_relations = left_relations.filter(checked=checked)
        right_relations = right_relations.filter(checked=checked)

    if ignore_file:
        to_ignore_ids = read_first_ids_from(ignore_file)
        left_relations = left_relations.exclude(pk__in=to_ignore_ids)
        right_relations = right_relations.exclude(pk__in=to_ignore_ids)

    left_relations = left_relations.annotate(lexeme_from_to_str=Concat('lexeme_from', Value('_'), 'lexeme_to'))
    right_relations = right_relations.annotate(lexeme_from_to_str=Concat('lexeme_to', Value('_'), 'lexeme_from'))

    _lr = dict(left_relations.values_list('lexeme_from_to_str', 'id'))
    _rr = dict(right_relations.values_list('lexeme_from_to_str', 'id'))
    common_ids = set(_lr.keys()) & set(_rr.keys())
    left_common_ids = [_lr[_k] for _k in common_ids]
    right_common_ids = [_rr[_k] for _k in common_ids]

    right_relations = right_relations.exclude(pk__in=right_common_ids)
    common_ids = left_common_ids + right_common_ids

    l_ids = list(left_relations.values_list('pk', flat=True))
    r_ids = list(right_relations.values_list('pk', flat=True))
    _ids = l_ids + r_ids

    relations = Relation.objects.filter(pk__in=_ids).prefetch_related(
        Prefetch('lexeme_from', queryset=Lexeme.objects.prefetch_related('miniparadigm_set', 'lexememetadata_set')),
        Prefetch('lexeme_to', queryset=Lexeme.objects.prefetch_related('miniparadigm_set', 'lexememetadata_set')),
        'relationexample_set', 'relationmetadata_set') \
        .order_by('lexeme_from__pos', 'lexeme_from__lexeme_lang') \
        .all()

    # alphabets
    alphabet = set()
    # sdefs
    sdefs = dict()
    symbols = set()

    for r in relations:
        r.dir = ''
        if r.pk not in common_ids:  # not bidirectional
            if r.pk in r_ids:
                r.lexeme_from, r.lexeme_to = r.lexeme_to, r.lexeme_from  # swap them
                r.dir = 'RL'
            else:
                r.dir = 'LR'

        alphabet |= set(r.lexeme_from.lexeme)
        alphabet |= set(r.lexeme_to.lexeme)

        if sdef_flag:
            symbols |= set(r.lexeme_from.symbols()) | set(r.lexeme_to.symbols())

    alphabet = ''.join(sorted(alphabet))

    if sdef_flag:
        system_symbols = Symbol.all_dict()
        sdefs = {s: system_symbols[s] for s in symbols if s in system_symbols}

    # save
    xml = render_to_string("export/bidix_xml.html", {'alphabet': alphabet, 'sdefs': sdefs, 'relations': relations})
    _filename = "apertium-{}-{}.{}-{}-{}.dix".format(
        left_lang,
        right_lang,
        left_lang,
        right_lang,
        time.strftime("%Y%m%d-%H%M")
    )
    with open("{}/{}".format(directory_path, _filename), 'w', encoding='utf-8') as f:
        f.write(xml)


def export(left_lang, right_lang, directory_path, ignore_file=None, *args, **kwargs):
    export_fn = export_bidix if right_lang else export_monodix
    return export_fn(left_lang, right_lang, directory_path, ignore_file, *args, **kwargs)


class Command(BaseCommand):
    """

    """

    help = 'Command to export an XML version of the dictionary.'

    def add_arguments(self, parser):
        parser.add_argument('-d', '--dir', type=str, help='The directory path where to store the XMLs in.', )
        parser.add_argument('-l', '--left', type=str, help='Three letter code of left language.', )
        parser.add_argument('-r', '--right', type=str,
                            nargs='?', default=None, help='Three letter code of right language.', )
        parser.add_argument('-i', '--ignore', type=str, nargs='?', default=None,
                            help='A file containing relations to be ignored. '
                                 'The first value must be the ID of the relation.', )

        parser.add_argument('--approved', type=lambda v: bool(strtobool(v)), nargs='?', const=True, default=None, )

        parser.add_argument('--sdef', dest='sdef', action='store_true')
        parser.set_defaults(sdef=False)

    def success_info(self, info):
        return self.stdout.write(self.style.SUCCESS(info))

    def error_info(self, info):
        return self.stdout.write(self.style.ERROR(info))

    def handle(self, *args, **options):
        dir_path = options['dir']
        left_lang = options['left']
        right_lang = options['right']
        ignore_file = options['ignore']

        if not os.path.isdir(dir_path):
            return self.error_info("The directory doesn't exist!")
        elif ignore_file and not os.path.isfile(ignore_file):
            return self.error_info("The ignore file doesn't exist.")

        export(left_lang, right_lang, dir_path, ignore_file, **options)
