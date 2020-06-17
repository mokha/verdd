import os
import io
import re
from django.core.management.base import BaseCommand, CommandError
import xml.etree.ElementTree as ET
from manageXML.models import *
from django.conf import settings
from ._dix_common import *


def parse_item(_i):
    if _i is None:
        return _i
    i = Item()
    i.attributes = {k: v.strip() for k, v in _i.attrib.items()}
    i.text = _i.text.strip() if _i.text else None
    i.symbol = [_s.attrib['n'] for _s in _i.findall('s') if 'n' in _s.attrib]
    return i


def parse_e(_e):
    e = DixElement()
    e.comment = _e.attrib['c'].strip() if 'c' in _e.attrib else ''
    e.direction = _e.attrib['r'].strip() if 'r' in _e.attrib else None

    _pair = _e.find('p')
    if _pair:
        e.pair.left = parse_item(_pair.find('l'))
        e.pair.right = parse_item(_pair.find('r'))

    e.re = parse_item(_e.find('re'))
    e.ig = parse_item(_e.find('ig'))
    e.par = parse_item(_e.find('par'))
    e.i = parse_item(_e.find('i'))
    e.attributes = _e.attrib

    return e


def parse_dix(file_path):
    dix = Dix()
    with io.open(file_path, 'r', encoding='utf-8') as fp:
        tree = ET.parse(fp)
        root = tree.getroot()

        dix.alphabet = root.find('alphabet').text

        for sdef in root.find('sdefs').findall('sdef'):
            dix.sdefs[sdef.attrib['n']] = sdef.attrib['n'].strip()

        _pardefs = root.find('pardefs')
        if _pardefs:
            for _pardef in _pardefs.findall('pardef'):
                pardef = ParDef()
                pardef.type = _pardef.attrib['n'] if 'n' in _pardef.attrib else ''
                pardef.comment = _pardef.attrib['n'] if 'n' in _pardef.attrib else ''

                _elements = [parse_e(_e) for _e in _pardef.findall('e')]
                pardef.elements = _elements
                dix.pardefs.append(pardef)

        for _section in root.findall('section'):
            section = Section()
            section.id = _section.attrib['id'] if 'id' in _section.attrib else ''
            section.type = _section.attrib['type'] if 'type' in _section.attrib else ''
            elements = []
            for _e in _section.findall('e'):
                elements.append(parse_e(_e))
            section.elements = elements
            dix.sections[section.id] = section

        return dix


def add_element(e: DixElement, lang):
    lemma = e.attributes['lm'] if 'lm' in e.attributes else ''  # is also in <r>
    lemma, homoId, pos = e.pair.right.lemma_homoId_POS()
    stem, stem_homoId, stem_pos = e.pair.left.lemma_homoId_POS()

    # find the lexeme or create the instance and return it
    _l, created = Lexeme.objects.get_or_create(lexeme=lemma, homoId=homoId, pos=pos, language=lang)
    title = _l.find_akusanat_affiliation()
    # link it
    if title:
        a, created = Affiliation.objects.get_or_create(lexeme=_l, title=title, type=AKUSANAT,
                                                       link="{}{}".format(settings.WIKI_URL, title))

    s, created = Stem.objects.get_or_create(lexeme=_l, text=stem, homoId=homoId)


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
        lang = options['language']

        if not os.path.isfile(file_path):
            raise CommandError('File "%s" does not exist.' % file_path)

        dix = parse_dix(file_path)
        for e in dix.sections['main'].elements:
            add_element(e, lang)

        self.stdout.write(self.style.SUCCESS('Successfully imported the file.'))
