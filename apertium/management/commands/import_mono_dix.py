import os
import io
from django.core.management.base import BaseCommand, CommandError
from manageXML.models import *
from django.conf import settings
from ._dix_common import *


def add_element(e: DixElement, lang):
    lemma = e.attributes['lm'] if 'lm' in e.attributes else ''  # is also in <r>
    lemma, homoId, pos = e.pair.right.lemma_homoId_POS()
    stem, stem_homoId, stem_pos = e.pair.left.lemma_homoId_POS()
    contlext = e.par.attributes['n'].replace('__', '_').upper() if 'n' in e.par.attributes else ''

    # find the lexeme or create the instance and return it
    _l, created = Lexeme.objects.get_or_create(lexeme=lemma, homoId=homoId, pos=pos, language=lang)
    title = _l.find_akusanat_affiliation()
    # link it
    if title:
        a, created = Affiliation.objects.get_or_create(lexeme=_l, title=title, type=AKUSANAT,
                                                       link="{}{}".format(settings.WIKI_URL, title))

    if stem:
        s, created = Stem.objects.get_or_create(lexeme=_l, text=stem, homoId=homoId, contlex=contlext)


class Command(BaseCommand):
    '''
    Example: python manage.py import_mono_dix -f ../apertium-fin -l fin
    '''

    help = 'This command imports the content of a monolingual .dix file.'

    def add_arguments(self, parser):
        parser.add_argument('-f', '--file', type=str, help='The .DIX file containing the translations.', )
        parser.add_argument('-l', '--language', type=str, help='The language of the monolingual file.', )

    def handle(self, *args, **options):
        file_path = options['file']  # the directory containing the XML files
        lang = Language.objects.get(id=options['language'])

        if not os.path.isfile(file_path):
            raise CommandError('File "%s" does not exist.' % file_path)

        with io.open(file_path, 'r', encoding='utf-8') as fp:
            dix = parse_dix(fp)

        for sdef, comment in dix.sdefs.items():
            try:
                Symbol.objects.get_or_create(name=sdef, comment=comment)
            except: # exists but with different comment
                pass

        for e in dix.sections['main'].elements:
            add_element(e, lang)

        self.stdout.write(self.style.SUCCESS('Successfully imported the file.'))
