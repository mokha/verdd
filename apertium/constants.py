from manageXML.constants import LEXEME_TYPE, GENDER
from collections import OrderedDict

POS_tags = {
    'vblex': 'V',
    'n': 'N',
    'adv': 'Adv',
    'adj': 'A',
    'ij': 'Interj',
    'post': 'Po',
    'num': 'Num',
    'cnjcoo': 'CC',
    'prn': 'Pron',
    'np': 'N',  # add Prop to metadata
    'part': 'Pcle',
    'vbmod': 'V+AUX',
    'vaux': 'V+AUX',
    'vbser': 'V',
    'vbhaver': 'V',
    'cnjsub': 'CS',
    'cnjadv': 'CS',
    'qst': 'Pcle',
}

POS_tags_rev = {'V': 'vblex', 'N': 'n', 'Adv': 'adv', 'A': 'adj', 'Interj': 'ij', 'Po': 'post', 'Num': 'num',
                'CC': 'cnjcoo', 'Pron': 'prn', 'Pcle': 'qst', 'V+AUX': 'vaux', 'CS': 'cnjadv'}

CONTLEX_TO_POS = OrderedDict({
    "__adj_adv": ["Adv", "A", ],
    "__adj_ord": "A",
    "__vbhaver": "V",
    "__cnjcoo": "CC",
    "__cnjsub": "CS",
    "__cnjadv": "CS",
    "__preadv": "Adv",
    "__pprep": "Po",
    "__vbser": "V",
    "__vbmod": "V",
    "__vblex": "V",
    "__vaux": "V",
    "__prn": "Pron",
    "__det": "Det",
    "__dem": "Det",
    "__adj": "A",
    "__num": "Num",
    "__adv": "Adv",
    "__atp": "Adv",
    "__ij": "Interj",
    "__np": "Prop",  # N
    "__pr": "Pr",
    "__n": "N",
})

# If needed, mappings can be taken from:
# https://github.com/giellalt/lang-myv/blob/develop/tools/mt/apertium/tagsets/gt2apertium.cg3relabel
SYMBOL_MAPS = {
    'np': (LEXEME_TYPE, 'Prop'),
    'm': (GENDER, 'm'),
    'f': (GENDER, 'f'),
    'nt': (GENDER, 'n'),
    'mf': (GENDER, ['m', 'f']),  # MF
    'mfn': (GENDER, ['m', 'f', 'n']),
}

homoIdMap = dict(zip('¹²³⁴⁵⁶⁷⁸⁹', range(9)))  # mapping from Apertium homonymn IDs to integers starting from 0
