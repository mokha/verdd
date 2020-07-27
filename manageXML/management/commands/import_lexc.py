from manageXML.management.commands._giella_xml import GiellaXML
from django.core.management.base import BaseCommand, CommandError
import os, glob, re, io
from manageXML.models import *
from django.conf import settings
from collections import defaultdict

ignore_affiliations = False

lexc_ptrn = re.compile(
    r'^([^\s]+)(\+v(\d+))?(\+Hom(\d+))?(\+(\w+))?(\+[\w\+\/]+)?:([^\s]+)[\s+]*([\w\_\-\/]+)\s*("(.*)")?\s*?;(.*)$',
    re.UNICODE)


def parse_file(file_path, lang: Language):
    print("processing: " + file_path)

    filename = os.path.splitext(os.path.basename(file_path))[0]
    df = DataFile(lang_source=lang, lang_target=None, name=filename)
    df.save()

    with io.open(file_path, 'r', encoding='utf-8') as fp:
        for line in fp:
            line = line.rstrip('\n')
            line = re.sub(r'\%\s', '__', line)  # ignore escaped whitespaces
            line = re.sub(r'\%', '', line)  # remove all escapings

            regex_result = lexc_ptrn.match(line)
            if regex_result:
                r_grp = regex_result.groups()

                # strip and re-add spaces if they were escaped
                r_grp = [_s.strip().replace('__', ' ') if _s else '' for _s in r_grp]

                lemma, _, variation, _, homoId, _, pos, _, stem, contlex, _, comment, extra = r_grp
                homoId = int(homoId) - 1 if homoId else 0
                variation = int(variation) - 1 if variation else 0

                try:
                    _l = Lexeme.objects.get(lexeme=lemma, pos=pos, homoId=homoId, language=lang)
                except:
                    _l = Lexeme.objects.create(
                        lexeme=lemma, pos=pos, homoId=homoId, language=lang,
                        contlex=contlex,
                        imported_from=df)

                try:
                    _s = Stem.objects.get(lexeme=_l, text=stem, contlex=contlex)
                except:
                    _s = Stem.objects.create(lexeme=_l, text=stem, contlex=contlex, order=variation)

                if ignore_affiliations:
                    continue

                title = _l.find_akusanat_affiliation()
                # link it
                if title:
                    a, created = Affiliation.objects.get_or_create(lexeme=_l, title=title, type=AKUSANAT,
                                                                   link="{}{}".format(settings.WIKI_URL, title))
            else:
                print(line)


class Command(BaseCommand):
    '''
    Example: python manage.py import_lexc -d ../saame/ -f sms
    Add --ignore-affiliations when debugging and want to speed up imports.
    '''

    help = 'This command imports the content of a all Giella LEXC files in a directory.'

    def add_arguments(self, parser):
        parser.add_argument('-d', '--dir', type=str, help='The directory containing LEXC files.', )
        parser.add_argument('-l', '--language', type=str, help='The language of the monolingual file.', )
        parser.add_argument('--ignore-affiliations', dest='ignore_affiliations', action='store_true')
        parser.set_defaults(ignore_affiliations=False)

    def handle(self, *args, **options):
        global ignore_affiliations

        _dir = options['dir']  # the directory containing the XML files
        ignore_affiliations = options['ignore_affiliations']
        lang = Language.objects.get(id=options['language'])

        if not os.path.isdir(_dir):
            raise CommandError('Directory "%s" does not exist.' % _dir)

        for filename in glob.glob(os.path.join(_dir, '*.lexc')):  # read each file and parse it
            parse_file(filename, lang)

        self.stdout.write(self.style.SUCCESS('Successfully imported the files.'))
