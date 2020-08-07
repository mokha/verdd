from manageXML.management.commands._giella_xml import GiellaXML
from django.core.management.base import BaseCommand, CommandError
import os, glob, sys
from manageXML.models import *
from django.conf import settings
from collections import defaultdict

ignore_affiliations = False


def create_lexeme(ll: GiellaXML.Item, lang: Language, datafile: DataFile = None):
    try:
        _l = Lexeme.objects.get(lexeme=ll.text.strip(), pos=ll.pos.strip(), homoId=ll.homoId, language=lang)
    except:
        _l = Lexeme.objects.create(
            lexeme=ll.text.strip(), pos=ll.pos.strip(), homoId=ll.homoId, language=lang,
            contlex=ll.contlex.strip(),
            imported_from=datafile)

    _filtered_attributes = ll.filtered_attributes()
    for _k, _v in _filtered_attributes.items():
        _metadata_type = None
        if _k == 'gen':
            _metadata_type = GENDER
        elif _k == 'type':
            _metadata_type = LEXEME_TYPE
        elif _l == 'ignore':
            _metadata_type = IGNORE_TAG
        else:
            _v = "{},{}".format(_k, _v.strip())
        _lmd, created = LexemeMetadata.objects.get_or_create(lexeme=_l, type=_metadata_type, text=_v)

    if ignore_affiliations:
        return _l

    title = _l.find_akusanat_affiliation()
    # link it
    if title:
        a, created = Affiliation.objects.get_or_create(lexeme=_l, title=title, type=AKUSANAT,
                                                       link="{}{}".format(settings.WIKI_URL, title))
    return _l


def parseXML(filename, filepos):
    print("processing: " + filename)
    g = GiellaXML.parse_file(filename)
    gl = Language.objects.get(id=g.lang)  # src_language

    langs = {
        g.lang: gl
    }
    filename_only = os.path.splitext(os.path.basename(filename))[0]
    df = DataFile(lang_source=gl, lang_target=None, name=filename_only)
    df.save()

    for e in g.elements:
        _ll = None
        _l = None
        try:
            for lg in e.get('lg', []):
                _l = lg.get('l', [])
                if not _l:
                    continue

                # Add ignore=fst to the lexeme
                if e.ignore:
                    _l.attributes['ignore'] = e.ignore

                _ll = create_lexeme(_l[0], gl, df)  # create the lemma

                for stg in lg.get('stg', []):
                    for st in stg.get('st', []):  # stems
                        s, created = Stem.objects.get_or_create(lexeme=_ll, text=st.text.strip(), homoId=st.homoId,
                                                                contlex=st.contlex)  # add the stems
            if not _ll:  # shouldn't happen but if it did, then we shouldn't get it there
                continue
            for mg in e.get('mg', []):
                l_relations = defaultdict(list)
                for tg in mg.get('tg', []):  # translations
                    _lang = tg.attributes.get('xml:lang')
                    if _lang and _lang not in langs:
                        try:
                            langs[_lang] = Language.objects.get(id=_lang)
                        except:
                            continue

                    for t in tg.get('t', []):
                        _t = create_lexeme(t, langs[_lang], df)
                        r, created = Relation.objects.get_or_create(lexeme_from=_ll, lexeme_to=_t)
                        l_relations[_lang].append(r)

                for xg in mg.get('xg', []):  # examples
                    x = xg.get('x', [])
                    if not x:
                        continue
                    x = x[0].text
                    _xl, created = Example.objects.get_or_create(lexeme=_ll, text=x)

                    for xt in xg.get('xt', []):
                        _lang = xt.attributes.get('xml:lang')

                        if _lang not in l_relations:
                            continue

                        _r = l_relations[_lang].pop(0)
                        re_src, created = RelationExample.objects.get_or_create(relation=_r, text=x, language=gl)

                        xtt = xt.text
                        re_tgt, created = RelationExample.objects.get_or_create(relation=_r, text=xtt,
                                                                                language=langs[_lang])

                        # add the link between the relations here
                        # RelationExampleRelation.objects.get_or_create(...)

                for semantic in mg.get('semantics', []):
                    pass

                for defNative in mg.get('defNative', []):
                    if not defNative or not defNative.text:
                        continue
                    _lmd, created = LexemeMetadata.objects.get_or_create(lexeme=_ll, type=DEF_NATIVE,
                                                                         text=defNative.text.strip())

            for source in e.get('sources', []):
                pass

        except Exception as err:
            sys.stderr.write('Error @ %s: %s' % (_l[0].text if _l and type(_l[0]) is GiellaXML.Item else '', str(err)))


class Command(BaseCommand):
    '''
    Example: python manage.py import_xml -d ../saame/
    Add --ignore-affiliations when debugging and want to speed up imports.
    '''

    help = 'This command imports the content of a all Giella XML documents in a directory.'

    def add_arguments(self, parser):
        parser.add_argument('-d', '--dir', type=str, help='The directory containing XML files.', )
        parser.add_argument('--ignore-affiliations', dest='ignore_affiliations', action='store_true')
        parser.set_defaults(ignore_affiliations=False)

    def handle(self, *args, **options):
        global ignore_affiliations

        xml_dir = options['dir']  # the directory containing the XML files
        ignore_affiliations = options['ignore_affiliations']

        if not os.path.isdir(xml_dir):
            raise CommandError('Directory "%s" does not exist.' % xml_dir)

        for filename in glob.glob(os.path.join(xml_dir, '*.xml')):  # read each file and parse it
            filepos = filename.split('/')[-1].split('_')[:-1]
            try:
                parseXML(filename, filepos)
            except:
                self.stderr.write(self.style.ERROR('Error processing %s' % filename))
        self.stdout.write(self.style.SUCCESS('Successfully imported the files.'))
