import os, glob
from xml.dom import minidom
from django.core.management.base import BaseCommand, CommandError
from ._private import *


class Command(BaseCommand):
    '''
    Example: python manage.py import_xml -d ../saame/ -t sms -s fin
    '''

    help = 'This command imports the content of a all XML documents in a directory.'

    def add_arguments(self, parser):
        parser.add_argument('-d', '--dir', type=str, help='The directory containing XML files.', )
        parser.add_argument('-t', '--target', type=str, help='Three letter code of target language.', )
        parser.add_argument('-s', '--source', type=str, help='Three letter code of source language.', )

    def handle(self, *args, **options):
        xml_dir = options['dir']  # the directory containing the XML files
        lang_target = options['target']  # language target (e.g. sms)
        lang_source = options['source']  # language source (e.g. fin)

        if not os.path.isdir(xml_dir):
            raise CommandError('Directory "%s" does not exist.' % xml_dir)

        for filename in glob.glob(os.path.join(xml_dir, '*.xml')):  # read each file and parse it
            # print("processing:", filename)
            filepos = filename.split('/')[-1].split('_')[:-1]
            parseXML(filename, lang_source)

        for lexeme_1, data_1 in new_xml.items():
            a = data_1['attributes']
            tg = data_1['tg']

            w1 = create_lexeme(lexeme=lexeme_1,
                               pos=a['pos'] if 'pos' in a else '',
                               type=a['type'] if 'type' in a else '',
                               language=lang_source)

            title, info, pos, contlex = query_semantic_search(lexeme_1, lang_source)
            if title:
                a = Affiliation.objects.get_or_create(lexeme=w1, title=title)

            for lexeme_2, data_2 in tg.items():
                w2 = create_lexeme(lexeme=lexeme_2,
                                   pos=data_2['pos'] if 'pos' in a else '',
                                   type=data_2['type'] if 'type' in a else '',
                                   contlex=data_2['Contlex'] if 'Contlex' in a else '',
                                   language=lang_target)

                title, info, pos, contlex = query_semantic_search(lexeme_2, lang_target)
                if title:
                    a = Affiliation.objects.get_or_create(lexeme=w2, title=title)

                r = create_relation(w1, w2, 'sms2X', '')  # create relation

        self.stdout.write(self.style.SUCCESS('Successfully flipped the files.'))
