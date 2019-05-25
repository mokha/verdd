from django.core.management.base import BaseCommand, CommandError
from manageXML.models import *
import io, csv, os, glob, re
import xml.etree.ElementTree as ET
from collections import defaultdict

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
            yield row


match_para = re.compile('\(.*?\)')  # match parenthesis


def process_row(row, df, lang_source, lang_target):
    word_1 = row[0]  # first data
    word_2 = row[1]

    if not word_1.strip() or not word_2.strip():
        return

    extra_notes = match_para.findall(word_1)  # get any extra notes
    extra_notes = list(map(lambda w: re.sub('\(|\)', '', w).strip(), extra_notes))  # remove parenthesis

    word_1 = match_para.sub('', word_1).strip()  # remove any additional information

    if len(row) > 2:
        notes = list(filter(lambda d: d, row[2:]))
        if notes:
            extra_notes += notes

    e = Element(lexeme=word_2, language=lang_source, notes="\n".join(extra_notes), imported_from=df)
    e.save()

    t = Translation(element=e, text=word_1, language=lang_target)
    t.save()


class Command(BaseCommand):
    '''
    Example: python manage.py import_csv -f ../data/Suomi-koltansaame_sanakirja_v1991_30052013.csv -s sms -t fin -n smsfin2004 -d ';'
    '''

    help = 'This command imports a CSV file into the database to be edited.'

    def add_arguments(self, parser):
        parser.add_argument('-f', '--file', type=str, help='The CSV file to import.', )
        parser.add_argument('-t', '--target', type=str, help='Three letter code of target language.', )
        parser.add_argument('-s', '--source', type=str, help='Three letter code of source language.', )
        parser.add_argument('-n', '--name', type=str, nargs='?', default=None,
                            help='The name to give for the import.', )
        parser.add_argument('-d', '--delimiter', type=str, nargs='?', default=';',
                            help='The delimiter to use when reading the CSV file.', )

    def handle(self, *args, **options):
        file_path = options['file']
        lang_target = options['target']  # language target (e.g. sms)
        lang_source = options['source']  # language source (e.g. fin)
        d = options['delimiter']

        if not os.path.isfile(file_path):
            raise CommandError('File "%s" does not exist.' % file_path)

        filename = options['name']
        if not filename:
            filename = os.path.splitext(os.path.basename(file_path))[0]  # get file name without extension

        df = DataFile(lang_source=lang_source, lang_target=lang_target, name=filename)
        df.save()

        for row in read_csv(file_path, delimiter=d):
            process_row(row, df, lang_source, lang_target)

        self.stdout.write(self.style.SUCCESS('Successfully imported the file "%s", with ID: %d' % (file_path, df.id)))
