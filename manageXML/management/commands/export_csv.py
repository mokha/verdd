from django.core.management.base import (BaseCommand, CommandError)
from io import open, BytesIO, StringIO
from zipfile import ZipFile
import uuid
import time
from manageXML.models import *
from distutils.util import strtobool
import csv


def export(src_lang, directory_path, *args, **kwargs):
    checked = kwargs.get('approved', None)

    lexemes_data = Lexeme.objects.filter(language=src_lang, checked=checked) \
        .order_by('lexeme_lang').values_list('id', 'lexeme', 'pos', )

    relations = Relation.objects.filter(type=TRANSLATION)

    if checked is not None:
        relations = relations.filter(checked=checked)

    relations_data = relations.filter(lexeme_from__language=src_lang).values_list('id', 'lexeme_from', 'lexeme_to')

    in_memory = BytesIO()
    zip_file = ZipFile(in_memory, "a")

    lexeme_output = StringIO()
    lexeme_csv = csv.writer(lexeme_output, )
    lexeme_csv.writerow(['id', 'lexeme', 'pos'])
    lexeme_csv.writerows(lexemes_data)
    zip_file.writestr("lexemes.csv", lexeme_output.getvalue())

    relation_output = StringIO()
    relation_csv = csv.writer(relation_output, )
    relation_csv.writerow(['from_id', 'to_id'])
    relation_csv.writerows(relations_data)
    zip_file.writestr("relations.csv", relation_output.getvalue())

    for _file in zip_file.filelist:
        _file.create_system = 0
        zip_file.close()

    _filename = "{}-{}-{}-csv-export.zip".format(
        time.strftime("%Y%m%d-%H%M%S"),
        src_lang,
        str(uuid.uuid4())[:5]
    )

    in_memory.seek(0)

    with open("{}/{}".format(directory_path, _filename), 'wb') as f:
        f.write(in_memory.getvalue())


class Command(BaseCommand):
    help = 'Command to export a CSV file for a source language.'

    def add_arguments(self, parser):
        parser.add_argument('-d', '--dir', type=str, help='The directory path where to store the CSV file in.', )
        parser.add_argument('-s', '--source', type=str, help='Three letter code of source language.', )
        parser.add_argument('--approved', type=lambda v: bool(strtobool(v)), nargs='?', const=True, default=None, )

    def success_info(self, info):
        return self.stdout.write(self.style.SUCCESS(info))

    def error_info(self, info):
        return self.stdout.write(self.style.ERROR(info))

    def handle(self, *args, **options):
        dir_path = options['dir']
        src_lang = options['source']

        export(src_lang, dir_path, **options)
