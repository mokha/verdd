from manageXML.models import *
from collections import defaultdict
import xml.etree.ElementTree as ET
from wiki.semantic_api import SemanticAPI
import io

semAPI = SemanticAPI()

new_xml = defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))
pos_files = defaultdict(list)


def query_semantic_search(lexeme, lang):
    r1 = semAPI.ask(query=(
        '[[%s:%s]]' % (lang.capitalize(), lexeme), '?Category', '?POS', '?Lang', '?Contlex')
    )

    if not r1['query']['results']:
        return (None,) * 4

    title, info = r1['query']['results'].popitem()
    info = info['printouts']
    pos = info['POS'][0]['fulltext']
    contlex = [i['fulltext'] for i in info['Contlex']]  # using the first contlex
    return title, info, pos, contlex


def parseXML(filename, lang='fin'):
    with io.open(filename, 'r', encoding='utf-8') as fp:
        tree = ET.parse(fp)
        root = tree.getroot()
        namespaces = {'xml': 'http://www.w3.org/XML/1998/namespace'}
        for e in root.findall('e'):
            for l in e.find('lg').findall('l'):
                if not l.text:
                    continue
                context = e.find('lg/stg/st')
                tg = e.find('mg/tg[@xml:lang="' + lang + '"]', namespaces)
                if not tg:
                    continue
                for t in tg.findall('t'):
                    if not t.text:
                        continue

                    context_text = context.attrib[
                        'Contlex'] if context is not None and 'Contlex' in context.attrib else l.attrib[
                                                                                                   'pos'] + '_'
                    new_xml[t.text]['tg'][l.text] = {**l.attrib, 'Contlex': context_text, }
                    new_xml[t.text]['attributes'] = t.attrib

                    POS_pred = t.attrib['pos'] if 'pos' in t.attrib and t.attrib['pos'] else l.attrib['pos']
                    POS_pred = POS_pred if ':' not in POS_pred else 'MWE'
                    pos_files[POS_pred].append(t.text)


def create_lexeme(**args):
    data = args.copy()
    data.pop('lexeme', None)
    data.pop('pos', None)
    data.pop('language', None)
    data.pop('homoId', None)

    l, created = Lexeme.objects.get_or_create(lexeme=args['lexeme'], pos=args['pos'], language=args['language'],
                                              homoId=args['homoId'] if 'homoId' in args else 0,
                                              defaults=data)
    return l


def create_relation(l1, l2, notes, source, source_type='book'):
    r, created = Relation.objects.get_or_create(lexeme_from=l1, lexeme_to=l2, type=0, defaults={'notes': notes})
    s, created = Source.objects.get_or_create(relation=r, name=source, defaults={'type': source_type})
    return r
