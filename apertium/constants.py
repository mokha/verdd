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
    'abbr': 'ABBR',
    'np': 'Prop'
}

homoIdMap = dict(zip('¹²³⁴⁵⁶⁷⁸⁹', range(9)))  # mapping from Apertium homonymn IDs to integers starting from 0
