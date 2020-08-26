import re
import io


def gt2ap(gt2ap_file):
    '''
    This function takes in an gt2ap file and returns a dictionary mapping between the tags
    (e.g. https://github.com/giellalt/lang-fin/blob/develop/tools/mt/apertium/tagsets/gt2apertium.cg3relabel)
    :param file:
    :return: A dictionary mapping a key from Gt tags to 1-* of Apertium tags
    '''

    with io.open(gt2ap_file, 'r', encoding='utf-8') as gt2ap_f:
        mappings = gt2ap_f.readlines()

        map_pattern = re.compile(r'\(([^)]+)\)')

        mappings = [_l.strip() for _l in mappings if _l.startswith('MAP ')]  # ignore comments and clean the line
        mappings = [map_pattern.findall(_l) for _l in mappings]

        return dict([(_l[0], _l[1:],) for _l in mappings])
