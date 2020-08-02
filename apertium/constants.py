from manageXML.constants import LEXEME_TYPE, GENDER

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
