import os
import io
from django.core.management.base import BaseCommand, CommandError
from manageXML.models import *
from django.conf import settings
from ._dix_common import *


def add_attributes_to_relation(r: Relation, attributes: list, language: str):
    if attributes:
        for attr in attributes:
            if attr not in POS_tags:
                md, created = RelationMetadata.objects.get_or_create(relation=r, language=language, text=attr,
                                                                     type=GENERIC_METADATA)


def add_element(e: DixElement, src_lang, tgt_lang, datafile):
    if not e:
        return

    _ll, _ll_homoId, _ll_pos = e.pair.left.lemma_homoId_POS()
    _rr, _rr_homoId, _rr_pos = e.pair.right.lemma_homoId_POS()

    _l, _r = None, None  # the default

    if _ll:
        try:
            _l = Lexeme.objects.get(lexeme=_ll, pos=_ll_pos, homoId=_ll_homoId, language=src_lang)
        except:
            _l = Lexeme.objects.create(
                lexeme=_ll, pos=_ll_pos, homoId=_ll_homoId, language=src_lang,
                imported_from=datafile)

    if _rr:
        try:
            _r = Lexeme.objects.get(lexeme=_rr, pos=_rr_pos, homoId=_rr_homoId, language=tgt_lang)
        except:
            _r = Lexeme.objects.create(
                lexeme=_rr, pos=_rr_pos, homoId=_rr_homoId, language=tgt_lang,
                imported_from=datafile)

    if e.direction is None or e.direction == "RL":
        r, created = Relation.objects.get_or_create(lexeme_from=_l, lexeme_to=_r)
        add_attributes_to_relation(r, e.pair.left.symbol, src_lang)
        add_attributes_to_relation(r, e.pair.right.symbol, tgt_lang)

    if e.direction is None or e.direction == "LR":
        r, created = Relation.objects.get_or_create(lexeme_from=_r, lexeme_to=_l)
        add_attributes_to_relation(r, e.pair.left.symbol, src_lang)
        add_attributes_to_relation(r, e.pair.right.symbol, tgt_lang)


class Command(BaseCommand):
    '''
    Example: python manage.py import_dix -f ../apertium-myv-fin -s myv -t fin
    '''

    help = 'This command imports the content of a all relations in DIX file.'

    def add_arguments(self, parser):
        parser.add_argument('-f', '--file', type=str, help='The .DIX file containing the translations.', )
        parser.add_argument('-t', '--target', type=str, help='Three letter code of target language.', )
        parser.add_argument('-s', '--source', type=str, help='Three letter code of source language.', )

    def handle(self, *args, **options):
        file_path = options['file']  # the directory containing the XML files
        lang_target = Language.objects.get(id=options['target'])  # language target (e.g. sms)
        lang_source = Language.objects.get(id=options['source'])  # language source (e.g. fin)

        if not os.path.isfile(file_path):
            raise CommandError('File "%s" does not exist.' % file_path)

        with io.open(file_path, 'r', encoding='utf-8') as fp:
            dix = parse_dix(fp)

        filename = os.path.splitext(os.path.basename(file_path))[0]
        df = DataFile(lang_source=lang_target, lang_target=lang_source, name=filename)
        df.save()

        for sdef, comment in dix.sdefs.items():
            try:
                Symbol.objects.get_or_create(name=sdef, comment=comment)
            except:  # exists but with different comment
                pass

        for e in dix.sections['main'].elements:
            add_element(e, lang_source, lang_target, df)

        self.stdout.write(self.style.SUCCESS('Successfully imported the file.'))
