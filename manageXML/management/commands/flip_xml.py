import xml.etree.ElementTree as ET
import io, os, glob
from collections import defaultdict
from xml.dom import minidom
from django.core.management.base import BaseCommand, CommandError

new_xml = defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))
pos_files = defaultdict(list)


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


def createXML(xml_dir, lang, namespace):
    new_dir = xml_dir + namespace + '/'
    if not os.path.exists(new_dir):
        os.makedirs(new_dir)
    for pos, ts in pos_files.items():
        filename = new_dir + pos + '_' + namespace + '.xml'

        root = ET.Element('r')
        root.set('xml', 'http://www.w3.org/XML/1998/namespace')
        root.set('xml:lang', lang)
        root.set('xmlns:xsi', 'http://www.w3.org/2001/XMLSchema-instance')
        root.set('xmlns:xs', 'http://www.w3.org/2001/XMLSchema')
        root.set('xmlns:hfp', 'http://www.w3.org/2001/XMLSchema-hasFacetAndProperty')
        root.set('xmlns:fn', 'http://www.w3.org/2005/02/xpath-functions')
        root.set('xsi:noNamespaceSchemaLocation', '../../../../../gtcore/schemas/fiu-dict-schema.xsd')

        for l_text in set(ts):
            data = new_xml[l_text]
            e = ET.SubElement(root, 'e')
            lg = ET.SubElement(e, 'lg')

            l_elem = ET.SubElement(lg, 'l')
            l_elem.text = l_text

            for attr, val in data['attributes'].items():
                l_elem.set(attr, val)

            for attr in data['tg'].values():
                if 'Contlex' in attr and 'PROP' in attr['Contlex'].upper():
                    l_elem.set('type', 'Prop')

            mg_elem = ET.SubElement(e, 'mg', relId='0')
            tg_elem = ET.SubElement(mg_elem, 'tg')
            tg_elem.set('xml:lang', lang)
            for t_txt, t_attr in data['tg'].items():
                t_elem = ET.SubElement(tg_elem, 't')
                t_elem.text = t_txt
                for _k, _v in t_attr.items():
                    t_elem.set(_k, _v)

        with open(filename, 'w', encoding='utf-8') as xml:
            xmlstr = minidom.parseString(ET.tostring(root, method='xml', encoding='utf-8')).toprettyxml(indent="   ")
            xml.write(xmlstr)


class Command(BaseCommand):
    '''
    Example: python manage.py flip_xml ./saame/XML/ -t sms -s fin -n finsms -o ./saame/flippedXML/
    '''

    help = 'This command flips the content of a all XML documents in a directory.'

    def add_arguments(self, parser):
        parser.add_argument('-d', '--dir', type=str, help='The directory containing XML files.', )
        parser.add_argument('-o', '--output', type=str, help='The directory that will contain the new XML files.', )
        parser.add_argument('-t', '--target', type=str, help='Three letter code of target language.', )
        parser.add_argument('-s', '--source', type=str, help='Three letter code of source language.', )
        parser.add_argument('-n', '--namespace', type=str, help='The namespace to assign to the new XMLs.', )

    def handle(self, *args, **options):
        xml_dir = options['dir']  # the directory containing the XML files
        output_dir = options['output']  # the directory containing the XML files
        lang_target = options['target']  # language target (e.g. sms)
        lang_source = options['source']  # language source (e.g. fin)
        namespace = options['namespace']  # new namespace

        if not os.path.isdir(xml_dir):
            raise CommandError('Directory "%s" does not exist.' % xml_dir)

        for filename in glob.glob(os.path.join(xml_dir, '*.xml')):  # read each file and parse it
            # print("processing:", filename)
            filepos = filename.split('/')[-1].split('_')[:-1]
            # print("POS:", filepos)
            parseXML(filename, lang_source)
        createXML(output_dir, lang_target, namespace)

        self.stdout.write(self.style.SUCCESS('Successfully flipped the files.'))
