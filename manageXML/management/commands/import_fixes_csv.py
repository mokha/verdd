import django
from django.core.management.base import BaseCommand, CommandError
import io, csv, os, glob, re
import xml.etree.ElementTree as ET
from collections import defaultdict
from uralicNLP import uralicApi
from wiki.semantic_api import SemanticAPI
import json, html, re
from lxml import etree
from io import StringIO
from ._private import *
from manageXML.constants import VARIATION

parser = etree.HTMLParser()


def analyze(word, lang):
    try:
        a = uralicApi.analyze(word, lang)
        a = map(lambda r: r[0].split('+'), a)
        a = list(filter(lambda r: r[0] == word, a))
        if not a:
            return [[None]]
        a = list(map(lambda r: r[1:], a))
        a = list(filter(lambda r: r, a))
        return a
    except:
        pass
    return [[None]]


def process_row(row):
    # data in the row
    id = int(row[0])  # the id of the original lexeme
    new_replacement = row[2]
    additiona_replacements = row[3:]

    # get original lexeme
    original_lexeme = Lexeme.objects.get(pk=id)  # get original lexeme
    pos = original_lexeme.pos
    language = original_lexeme.language
    homoId = original_lexeme.homoId
    df = original_lexeme.imported_from

    # fix encoding
    new_replacement = fix_encoding(new_replacement)
    additiona_replacements = [fix_encoding(w) for w in additiona_replacements]

    original_lexeme.lexeme = new_replacement
    try:
        original_lexeme.save()  # try to fix the new changes
    except django.db.utils.IntegrityError as e:  # the lexeme already exists
        original_lexeme = Lexeme.objects.get(lexeme=new_replacement,
                                             pos=pos,
                                             language=language, homoId=homoId)

    new_lexemes = [create_lexeme(lexeme=w,
                                 pos=pos,
                                 language=language,
                                 imported_from=df) for w in additiona_replacements]

    for w in new_lexemes:
        r = Relation.objects.get_or_create(lexeme_from=original_lexeme, lexeme_to=w, type=VARIATION,
                                           notes="Imported from fixed variations by Jack")


class Command(BaseCommand):
    '''
    Example: python manage.py import_fixes_csv -f ../data/lexemes-not-lexemes_2019-09-25_reduced_02.tsv -d '\t'
    '''

    help = 'This command imports a CSV file into the database by updating existing lexemes and adding new ones.'

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
            for row in reader:
                if len(row) > 0:  # the row has some information
                    process_row(list(row))

        self.stdout.write(self.style.SUCCESS('Successfully imported the file "%s"' % (file_path,)))
