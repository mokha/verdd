from collections import defaultdict
import re
from apertium.constants import *
import xml.etree.ElementTree as ET
from manageXML.models import Lexeme, LexemeMetadata


def parse_text(text):
    homoId = 0
    if text:
        try:
            res = re.match(r'^([^¹²³⁴⁵⁶⁷⁸⁹]+)([¹²³⁴⁵⁶⁷⁸⁹])?$', text).groups()
            if res[1]:  # has homoId
                homoId = homoIdMap[res[1]]
            text = res[0]
        except:
            text = text
    return text, homoId


class Item(object):
    def __init__(self):
        self.text = ''
        self._symbol = []
        self.attributes = defaultdict(str)

    def __repr__(self):
        return self.text

    @property
    def symbol(self):
        return list(sorted(self._symbol))

    @symbol.setter
    def symbol(self, value):
        self._symbol = value

    def unique_str(self):
        return "{}__{}".format(self.text, "_".join(self._symbol))

    def lemma_homoId_POS(self):
        pos, pos_giella = '', ''
        for attr in list(self.symbol):
            if attr in POS_tags:
                pos = attr
                pos_giella = POS_tags[attr]
                break
        lemma, homoId = parse_text(self.text)
        return lemma, homoId, pos, pos_giella,


class TranslationPair(object):
    def __init__(self):
        self.left = Item()
        self.right = Item()

    def __repr__(self):
        return "{} - {}".format(self.left, self.right)


class DixElement(object):
    def __init__(self):
        self.comment = ''
        self.pair = TranslationPair()
        self.direction = None  # r="RL" | r="LR" | default = bidirectional
        self.attributes = defaultdict(str)
        self.re = None
        self.ig = None
        self.par = None
        self.i = None

    def __repr__(self):
        return self.pair.__repr__()


class ParDef(object):
    def __init__(self):
        self.type = ''
        self.comment = ''
        self._elements = []

    @property
    def elements(self):
        return self._elements

    @elements.setter
    def elements(self, value):
        self._elements = value


class Section(ParDef):
    def __init__(self):
        self.id = ''
        super(ParDef, self).__init__()


class Dix(object):
    def __init__(self):
        self.alphabet = ''
        self.sdefs = defaultdict(str)
        self.pardefs = []
        self.sections = defaultdict(Section)


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


def parse_dix(fp):
    dix = Dix()
    tree = ET.parse(fp)
    root = tree.getroot()

    dix.alphabet = root.find('alphabet').text

    for sdef in root.find('sdefs').findall('sdef'):
        dix.sdefs[sdef.attrib['n']] = sdef.attrib['c'].strip() if 'c' in sdef.attrib else ''

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


def add_metadata_to_lexeme(lexeme: Lexeme, item: Item):
    for attr in list(item.symbol):
        if attr in SYMBOL_MAPS:
            _type, attr_g = SYMBOL_MAPS[attr]
            if isinstance(attr_g, list):
                for _attr_g in attr_g:
                    md, created = LexemeMetadata.objects.get_or_create(lexeme=lexeme, type=_type, text=_attr_g)
            else:
                md, created = LexemeMetadata.objects.get_or_create(lexeme=lexeme, type=_type, text=attr_g)
