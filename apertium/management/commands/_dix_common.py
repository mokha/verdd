from collections import defaultdict
import re
from apertium.constants import *


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
        pos = ''
        for attr in list(self.symbol):
            if attr in POS_tags:
                pos = POS_tags[attr]
                break
        lemma, homoId = parse_text(self.text)
        return lemma, homoId, pos,


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
