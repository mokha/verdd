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


def mediawiki_query(word, lexeme):
    '''
    Queries MediaWiki to retrieve information stored there.

    :param word: Skolt Sami word
    :param lexeme: Finnish word
    :return:
    '''
    # Contlex (can download XMLs and parse them later using https://github.com/mikahama/saame_testi/blob/master/download_sanat.py)

    title, pos, translations, contlex, miniparam = (None,) * 5

    title, info, pos, contlex_ignored = query_semantic_search(word, 'sms')
    if not title:
        return title, pos, translations, contlex, miniparam

    r2 = semAPI.parse(title)
    if "error" not in r2:
        r2 = r2['parse']

        lines = ''.join(r2['text']['*'].split('\n'))  # combine everything

        lines = re.findall(r'<span style="display:none" class="json_data">(.+?)</span>', lines,
                           re.UNICODE | re.IGNORECASE)  # get the json data only

        lines = map(lambda t: re.sub(r'<audio>(.+?)</audio>', '', html.unescape(t.replace('\\n', '')),
                                     re.UNICODE | re.IGNORECASE), lines)  # audios aren't imported in the JSON properly
        try:
            data = list(map(lambda t: json.loads(t), lines))
            for d in data:
                translations = d['translations']
                if 'fin' in translations:
                    translations = translations['fin']  # [{'word':..., 'pos':...}]
                    translations = list(map(lambda t:
                                            (t['word'].strip() if 'word' in t and t['word'] else '',
                                             t['pos'] if 'pos' in t else '',),
                                            translations))
                    if lexeme not in dict(translations):
                        continue

                # Contlex is taken from semantic search now
                # In case multiple existed, take varId=1. If not possible, take the first one
                try:
                    morph = html.unescape(d['morph']['lg']['stg'])
                    tree = etree.parse(StringIO(morph), parser=parser)
                    sts = tree.xpath("//st")
                    contlex = [{**st.attrib, 'text': st.text.strip()} for st in sts]
                except:
                    pass

                try:
                    mini_paradigm = html.unescape(
                        d['morph']['lg']['mini_paradigm'])
                    tree = etree.parse(StringIO(mini_paradigm), parser=parser)
                    analysis = tree.findall("//analysis")
                    miniparam = [(a.find('wordform').text, a.attrib['ms'].replace('.', '+')) for a in analysis]
                except:
                    pass

                return title, pos, translations, contlex, miniparam
        except:
            pass

    return title, pos, translations, contlex, miniparam


def process_row(row):
    row_dict = dict(row)

    # data in the row
    id = int(row[0])  # the id of the original lexeme
    new_replacement = row[2]
    additiona_replacements = row[2:]

    # get original lexeme
    original_lexeme = Lexeme.objects.get(pk=id)  # get original lexeme

    # fix encoding
    new_replacement = fix_encoding(new_replacement)
    additiona_replacements = [fix_encoding(w) for w in additiona_replacements]

    word_1_analysis = analyze(word_1, 'fin')
    word_1_analysis = list(filter(lambda _a: _a[0] and 'Hom' not in _a[0], word_1_analysis))
    word_1_analysis = set(map(lambda wa: wa[0], word_1_analysis))
    if not word_1_analysis:
        word_1_analysis = ['']  # @TODO: if it was a homonym, ignore this...
    lexemes_1 = [create_lexeme(lexeme=word_1,
                               pos=pos,
                               language=lang_source,
                               imported_from=df) for pos in word_1_analysis]

    mediawiki_data = mediawiki_query(word_2, word_1)
    title, pos, translations, contlex, miniparam = mediawiki_data

    extra_notes = map(lambda v: ': '.join(v), row)  # convert the row into (k:v)
    notes = "\n".join(extra_notes)
    if title:
        for w2 in lexemes_2:
            a, created = Affiliation.objects.get_or_create(lexeme=w2, title=title)

    for w1 in lexemes_1:
        for w2 in lexemes_2:
            r = create_relation(w1, w2, notes, row_dict['teâttkäivv'])  # create relation

    for w2 in lexemes_2:
        pos = w2.pos

        # add its translation
        c = list(filter(lambda c: 'contlex' in c and c['contlex'].startswith(pos + '_'), contlex)) if contlex else []
        c = list(filter(lambda _c: 'varid' not in _c or _c['varid'] != '1', c))

        if c:
            c = c[0]
            if 'contlex' in c:
                w2.contlex = c['contlex']
            if 'inflexid' in c:
                w2.inflexId = c['inflexid']
            w2.save()

        # add mini paradigms
        if miniparam:
            for wordform, msd in miniparam:
                if wordform != '=':
                    m = MiniParadigm(lexeme=w2, wordform=wordform, msd=w2.pos + '+' + msd.replace('_', '+'))
                    m.save()


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
                process_row(list(row))

        self.stdout.write(self.style.SUCCESS('Successfully imported the file "%s"' % (file_path,)))
