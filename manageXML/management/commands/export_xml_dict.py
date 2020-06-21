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


def export(src_lang, tgt_lang, directory_path, ignore_file=None):
    relations = Relation.objects.filter(checked=True, type=TRANSLATION)
    if ignore_file:
        to_ignore_ids = read_first_ids_from(os.path.join(settings.BASE_DIR, '../local/data/approved_relations.csv'))
        relations = relations.exclude(pk__in=to_ignore_ids)

    relations = relations \
        .prefetch_related(
        Prefetch('lexeme_from', queryset=Lexeme.objects.prefetch_related('miniparadigm_set')),
        Prefetch('lexeme_to', queryset=Lexeme.objects.prefetch_related('miniparadigm_set')),
        'relationexample_set', 'relationmetadata_set') \
        .filter(lexeme_from__language=src_lang)

    if tgt_lang:
        relations = relations.filter(lexeme_to__language='sms')
    else:
        tgt_lang = 'X'

    relations = relations \
        .annotate(
        pos=Case(
            When(lexeme_to__contlex__icontains='PROP_', then=Value('N_Prop')),
            default=F('lexeme_from__pos')),
        pos_U=Upper('pos')) \
        .order_by('pos_U') \
        .all()

    grouped_relations = groupby(relations, key=lambda r: r.pos_U)

    in_memory = BytesIO()
    zip_file = ZipFile(in_memory, "a")

    for key, relations in grouped_relations:
        grouped_relations_source = groupby(sorted(relations, key=lambda r: r.lexeme_from.id),
                                           key=lambda r: r.lexeme_from.id)
        grouped_relations_source = [(k, list(g),) for k, g in grouped_relations_source]
        grouped_relations_source = list(sorted(grouped_relations_source, key=lambda k: k[1][0].lexeme_from.lexeme_lang))
        _chapter_html = render_to_string("export/dict_xml.html", {
            'grouped_relations': grouped_relations_source,
            'src_lang': src_lang,
            'tgt_lang': tgt_lang,
            'pos': key,
        })
        zip_file.writestr("{}_{}{}.xml".format(grouped_relations_source[0][1][0].pos, src_lang, tgt_lang),
                          _chapter_html.encode('utf-8'))

    for _file in zip_file.filelist:
        _file.create_system = 0
        zip_file.close()

    _filename = "{}-{}-{}{}-XML-export.zip".format(
        time.strftime("%Y%m%d-%H%M%S"),
        src_lang,
        tgt_lang,
        str(uuid.uuid4())[:5]
    )

    in_memory.seek(0)

    with open("{}/{}".format(directory_path, _filename), 'wb') as f:
        f.write(in_memory.getvalue())


class Command(BaseCommand):
    '''
    This function generates the XML following the format in https://victorio.uit.no/langtech/trunk/words/dicts/finsms/
    The output is expected to be used in an online dictionary.
    Example: python manage.py export_xml_dict -d ../xml_src/
    '''

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
