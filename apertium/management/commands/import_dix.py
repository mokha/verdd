import os
import io
import re
from django.core.management.base import BaseCommand, CommandError
import xml.etree.ElementTree as ET
from collections import defaultdict
from manageXML.models import *
from apertium.constants import *
from django.conf import settings


class TranslationText(object):
    def __init__(self):
        self.text = ''
        self._attributes = []

    def __repr__(self):
        return self.text

    @property
    def attributes(self):
        return list(sorted(self._attributes))

    @attributes.setter
    def attributes(self, value):
        self._attributes = value

    def unique_str(self):
        return "{}__{}".format(self.text, "_".join(self.attributes))


class TranslationPair(object):
    def __init__(self):
        self.left = TranslationText()
        self.right = TranslationText()

    def __repr__(self):
        return "{} - {}".format(self.left, self.right)


class DixElement(object):
    def __init__(self):
        self.comment = ''
        self.pair = TranslationPair()
        self.direction = None  # r="RL" | r="LR" | default = bidirectional
        self.re = ''

    def __repr__(self):
        return self.pair.__repr__()


class ParDef(object):
    def __init__(self):
        self.type = ''
        self._elements = []

    @property
    def elements(self):
        return list(sorted(self._elements))

    @elements.setter
    def elements(self, value):
        self._elements = value


def parse_e(_e):
    e = DixElement()
    e.comment = _e.attrib['c'].strip() if 'c' in _e.attrib else ''
    e.direction = _e.attrib['r'].strip() if 'r' in _e.attrib else None

    _pair = _e.find('p')
    _left = _pair.find('l')
    e.pair.left.text = _left.text.strip() if _left.text else ''
    e.pair.left.attributes = [_s.attrib['n'] for _s in _left.findall('s') if 'n' in _s.attrib]

    _right = _pair.find('r')
    e.pair.right.text = _right.text.strip() if _right.text else ''
    e.pair.right.attributes = [_s.attrib['n'] for _s in _right.findall('s') if 'n' in _s.attrib]

    _re = _e.find('re')
    if _re:
        e.re = _re.text.strip()

    return e


def parse_dix(file_path):
    with io.open(file_path, 'r', encoding='utf-8') as fp:
        tree = ET.parse(fp)
        root = tree.getroot()

        alphabet = root.find('alphabet').text

        sdefs = defaultdict(str)
        for sdef in root.find('sdefs').findall('sdef'):
            sdefs[sdef.attrib['n']] = sdef.attrib['n'].strip()

        pardefs = defaultdict(str)
        _pardefs = root.find('pardefs')
        if _pardefs:
            for _pardef in _pardefs.findall('pardef'):
                pardef = ParDef()
                pardef.type = _pardef.attrib['n'] if 'n' in _pardef.attrib else ''

                _elements = [parse_e(_e) for _e in _pardef.findall('e')]
                pardef.elements = _elements

        elements = []
        for _e in root.find('section').findall('e'):
            elements.append(parse_e(_e))

        return alphabet, sdefs, pardefs, elements


def get_lexeme(e: TranslationText, language):
    homoId = 0
    res = re.match(r'^([^¹²³⁴⁵⁶⁷⁸⁹]+)([¹²³⁴⁵⁶⁷⁸⁹])?$', e.text).groups()
    if res[1]:  # has homoId
        homoId = homoIdMap[res[1]]
    text = res[0]
    for attr in list(e.attributes):
        if attr in POS_tags:
            pos = POS_tags[attr]
            e.attributes.remove(attr)
            break
    else:
        pos = ''

    # find the lexeme or create the instance and return it
    _l, created = Lexeme.objects.get_or_create(lexeme=text, homoId=homoId, pos=pos, language=language)
    title = _l.find_akusanat_affiliation()
    # link it
    if title:
        a, created = Affiliation.objects.get_or_create(lexeme=_l, title=title, type=AKUSANAT,
                                                       link="{}{}".format(settings.WIKI_URL, title))
    return _l


def add_attributes_to_relation(r: Relation, attributes: list, language: str):
    if attributes:
        for attr in attributes:
            md, created = RelationMetadata.objects.get_or_create(relation=r, language=language, text=attr,
                                                                 type=GENERIC_METADATA)


def add_element(e: DixElement, src_lang, tgt_lang):
    _ll = get_lexeme(e.pair.left, src_lang)
    _rl = get_lexeme(e.pair.right, tgt_lang)

    if e.direction is None or e.direction == "RL":
        r, created = Relation.objects.get_or_create(lexeme_from=_ll, lexeme_to=_rl)
        add_attributes_to_relation(r, e.pair.left.attributes, src_lang)
        add_attributes_to_relation(r, e.pair.right.attributes, tgt_lang)

    if e.direction is None or e.direction == "LR":
        r, created = Relation.objects.get_or_create(lexeme_from=_rl, lexeme_to=_ll)
        add_attributes_to_relation(r, e.pair.left.attributes, src_lang)
        add_attributes_to_relation(r, e.pair.right.attributes, tgt_lang)


class Command(BaseCommand):
    '''
    Example: python manage.py import_dix -f ../apertium-myv-fin -s myv -t fin
    '''

    help = 'This command imports the content of a all relations in DIX file.'

    def add_arguments(self, parser):
        parser.add_argument('-f', '--file', type=str, help='The .DIX file containing the translations.', )
        parser.add_argument('-t', '--target', type=str, help='Three letter code of target language.', )
        parser.add_argument('-s', '--source', type=str, help='Three letter code of source language.', )

    def handle(self, *args, **options):
        file_path = options['file']  # the directory containing the XML files
        lang_target = options['target']  # language target (e.g. sms)
        lang_source = options['source']  # language source (e.g. fin)

        if not os.path.isfile(file_path):
            raise CommandError('File "%s" does not exist.' % file_path)

        alphabet, sdefs, pardefs, elements = parse_dix(file_path)

        for e in elements:
            add_element(e, lang_source, lang_target)

        self.stdout.write(self.style.SUCCESS('Successfully imported the file.'))
