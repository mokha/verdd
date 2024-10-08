import os
import io
from django.core.management.base import BaseCommand, CommandError
from manageXML.models import *
from django.conf import settings
from ._dix_common import *

ignore_affiliations = False


def create(itm: Item, lemma, pos_g, homoId, lang, datafile, stem, contlex):
    # find the lexeme or create the instance and return it

    # Handling importing Proper nouns
    prop = False
    if pos_g == "Prop":
        prop = True
        pos_g = "N"

    try:
        _l = Lexeme.objects.get(lexeme=lemma, pos=pos_g, homoId=homoId, language=lang)
    except:
        _l = Lexeme.objects.create(
            lexeme=lemma,
            pos=pos_g,
            homoId=homoId,
            language=lang,
            imported_from=datafile,
        )

    add_metadata_to_lexeme(_l, itm)

    # Handling importing Proper nouns
    if prop:
        md, created = LexemeMetadata.objects.get_or_create(
            lexeme=_l, type=LEXEME_TYPE, text="Prop"
        )

    if not ignore_affiliations:
        title = _l.find_akusanat_affiliation()
        # link it
        if title:
            a, created = Affiliation.objects.get_or_create(
                lexeme=_l,
                title=title,
                type=AKUSANAT,
                link="{}{}".format(settings.WIKI_URL, title),
            )

    if stem:
        s, created = Stem.objects.get_or_create(
            lexeme=_l, text=stem, homoId=homoId, contlex=contlex
        )


def add_element(e: DixElement, lang, datafile):
    lemma, homoId, pos, pos_g = e.pair.right.lemma_homoId_POS()
    if not lemma:
        lemma = e.attributes["lm"] if "lm" in e.attributes else ""  # is also in <r>
    stem, stem_homoId, stem_pos, stem_pos_g = e.pair.left.lemma_homoId_POS()
    if not stem and e.i:
        stem, stem_homoId, stem_pos, stem_pos_g = e.i.lemma_homoId_POS()
    contlex = e.par.attributes["n"] if e.par and "n" in e.par.attributes else ""
    if not pos:
        for pos_key in CONTLEX_TO_POS.keys():
            if pos_key in contlex:
                pos = CONTLEX_TO_POS[pos_key]
                break
        if type(pos) is list:
            for _p in pos:
                create(e.pair.right, lemma, _p, homoId, lang, datafile, stem, contlex)
        else:
            create(e.pair.right, lemma, pos_g, homoId, lang, datafile, stem, contlex)
    else:
        create(e.pair.right, lemma, pos_g, homoId, lang, datafile, stem, contlex)


class Command(BaseCommand):
    """
    Example: python manage.py import_mono_dix -f ../apertium-fin -l fin
    """

    help = "This command imports the content of a monolingual .dix file."

    def add_arguments(self, parser):
        parser.add_argument(
            "-f",
            "--file",
            type=str,
            help="The .DIX file containing the translations.",
        )
        parser.add_argument(
            "-l",
            "--language",
            type=str,
            help="The language of the monolingual file.",
        )
        parser.add_argument(
            "--ignore-affiliations", dest="ignore_affiliations", action="store_true"
        )
        parser.set_defaults(ignore_affiliations=False)

    def handle(self, *args, **options):
        global ignore_affiliations

        file_path = options["file"]  # the directory containing the XML files
        ignore_affiliations = options["ignore_affiliations"]
        lang = Language.objects.get(id=options["language"])

        if not os.path.isfile(file_path):
            raise CommandError('File "%s" does not exist.' % file_path)

        with io.open(file_path, "r", encoding="utf-8") as fp:
            dix = parse_dix(fp)

        filename = os.path.splitext(os.path.basename(file_path))[0]
        df = DataFile(lang_source=lang, lang_target=None, name=filename)
        df.save()

        for sdef, comment in dix.sdefs.items():
            try:
                Symbol.objects.get_or_create(name=sdef, comment=comment)
            except:  # exists but with different comment
                pass

        for e in dix.sections["main"].elements:
            add_element(e, lang, df)

        self.stdout.write(self.style.SUCCESS("Successfully imported the file."))
