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
from mikatools import *

parser = etree.HTMLParser()

new_xml = defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))
pos_files = defaultdict(list)
all_words = []
word_pos = defaultdict(list)


def parseXML(filename, lang='fin'):
    with io.open(filename, 'r', encoding='utf-8') as fp:
        tree = ET.parse(fp)
        root = tree.getroot()
        namespaces = {'xml': 'http://www.w3.org/XML/1998/namespace'}
        for e in root.findall('e'):
            for l in e.find('lg').findall('l'):
                if not l.text:
                    continue
                context = e.find('lg/stg/st')
                tg = e.find('mg/tg[@xml:lang="' + lang + '"]', namespaces)
                if not tg:
                    continue
                for t in tg.findall('t'):
                    if not t.text:
                        continue

                    context_text = context.attrib[
                        'Contlex'] if context is not None and 'Contlex' in context.attrib else l.attrib[
                                                                                                   'pos'] + '_'
                    new_xml[t.text]['tg'][l.text] = {**l.attrib, 'Contlex': context_text, }
                    new_xml[t.text]['attributes'] = t.attrib

                    POS_pred = t.attrib['pos'] if 'pos' in t.attrib and t.attrib['pos'] else l.attrib['pos']
                    POS_pred = POS_pred if ':' not in POS_pred else 'MWE'

                    all_words.append(t.text)
                    all_words.append(l.text)

                    word_pos[t.text.lower()].append(POS_pred)
                    word_pos[l.text.lower()].append(l.attrib['pos'])


def read_xmls(xml_dir, lang_target='sms', lang_source='fin'):
    for filename in glob.glob(os.path.join(xml_dir + lang_target, '*.xml')):  # read each file and parse it
        parseXML(filename, lang_source)


def old_read_tsv(filename):
    results = []

    match_ptrn = re.compile("^(.*)([ ]{2,}|\t+)(.*)$", re.IGNORECASE | re.UNICODE)

    with io.open(filename, 'r', encoding='utf-8') as fp:
        if 'Eerollemarras14' in filename:
            for line in fp.readlines()[1:]:
                line = line.rstrip("\n\r")
                row = line.split('\t')
                results.append((row[2], row[1], {
                    'semantics': row[3],
                    'etymology': row[4],
                    'sources': row[5]
                }))
        else:
            for line in fp:
                line = line.rstrip("\n\r")
                result = match_ptrn.match(line)
                if not result:
                    continue
                groups = result.groups()
                word_1 = groups[0]
                word_2 = groups[2]

                results.append((word_1, word_2, {}))
    return results


def read_csv(filename, delimiter=';'):
    with io.open(filename, 'r', encoding='utf-8') as fp:
        #     reader = csv.DictReader(fp, dialect='excel-tab')
        #     for row in reader:
        reader = csv.reader(fp, delimiter=delimiter)
        headers = next(reader, None)  # ignore header
        for row in reader:
            yield list(zip(headers, row))


match_para = re.compile('\(.*?\)')  # match parenthesis


def analyze(word, lang):
    # word = word.lower()
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

def add_termwiki():
    term_json = json_load(script_path("../../../additional_data/sms_termwiki.json"))
    for termwiki in term_json:
        sms_data = termwiki["sms"]
        for word in sms_data:
            print(word["word"])
            try:
                l = Lexeme.objects.get(lexeme=word["word"], language="sms")
                a, created = Affiliation.objects.get_or_create(lexeme=l, title="Termwiki", link=word["url"], checked=word["sanctioned"])
                a.save()
                print(l) 
            except Exception as e:
                print(e)

def process_row(row, df, lang_source, lang_target):
    row_dict = dict(row)
    word_1 = fix_encoding(row[0][1])  # first word
    word_2 = fix_encoding(row[1][1])  # second word

    if not word_1.strip() or not word_2.strip():
        return

    word_1_stripped = match_para.sub('', word_1).strip()  # remove any additional information
    word_1 = word_1_stripped if word_1_stripped else word_1  # in case the result is an empty string

    word_1_stripped = match_para.sub('', word_2).strip()  # remove any additional information
    word_2 = word_1_stripped if word_1_stripped else word_2  # in case the result is an empty string

    word_1_analysis = analyze(word_1, 'fin')
    word_1_analysis = list(filter(lambda _a: _a[0] and 'Hom' not in _a[0], word_1_analysis))
    word_1_analysis = set(map(lambda wa: wa[0], word_1_analysis))
    if not word_1_analysis:
        word_1_analysis = ['']  # @TODO: if it was a homonym, ignore this...
    lexemes_1 = [create_lexeme(lexeme=word_1,
                               pos=pos,
                               language=lang_source,
                               imported_from=df) for pos in word_1_analysis]

    word_2_analysis = analyze(word_2, 'sms')
    word_2_analysis = list(filter(lambda _a: _a[0] and 'Hom' not in _a[0], word_2_analysis))
    word_2_analysis = set(map(lambda wa: wa[0], word_2_analysis))
    if not word_2_analysis:
        word_2_analysis = ['']
    lexemes_2 = [create_lexeme(lexeme=word_2,
                               pos=pos,
                               language=lang_target,
                               imported_from=df) for pos in word_2_analysis]  # insert second word

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
    Example: python manage.py import_csv -f ../data/Suomi-koltansaame_sanakirja_v1991_30052013.csv -s fin -t sms -n smsfin2004 -d ';'
    '''

    help = 'This command imports a CSV file into the database to be edited.'

    def add_arguments(self, parser):
        parser.add_argument("-c", "--command", type=str, help="termwiki for termwiki import", default=None)
        parser.add_argument('-f', '--file', type=str, help='The CSV file to import.', )
        parser.add_argument('-t', '--target', type=str, help='Three letter code of target language.', )
        parser.add_argument('-s', '--source', type=str, help='Three letter code of source language.', )
        parser.add_argument('-n', '--name', type=str, nargs='?', default=None,
                            help='The name to give for the import.', )
        parser.add_argument('-d', '--delimiter', type=str, nargs='?', default=';',
                            help='The delimiter to use when reading the CSV file.', )

    def handle(self, *args, **options):
        if options['command'] == "termwiki":
            print("termwiki import")
            add_termwiki()
            quit()
        