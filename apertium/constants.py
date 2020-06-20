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
    'np': 'Prop',
    'part': 'Pcle',
    'vbmod': 'V+AUX',
    'vaux': 'V+AUX',
    'vbser': 'V',
    'vbhaver': 'V',
    'cnjsub': 'CS',
    'cnjadv': 'CS',
    'qst': 'Pcle',
}

homoIdMap = dict(zip('¹²³⁴⁵⁶⁷⁸⁹', range(9)))  # mapping from Apertium homonymn IDs to integers starting from 0
