from django.core.management.base import BaseCommand, CommandError
from django.db.models.functions import Cast, Substr, Upper
from django.db.models import Prefetch, F, Value, When, Case
from manageXML.models import *
from manageXML.utils import *
from itertools import groupby
from django.template.loader import render_to_string
from io import open, BytesIO
from django.conf import settings
from zipfile import ZipFile
import uuid
import time
from django.db.models.functions import Cast


def export(src_lang, tgt_lang, directory_path, ignore_file=None):
    main_template = "export/latex.html"
    chapter_template = "export/latex-chapter.html"

    # get all approved relations
    # 1) get approved translation relations (e.g. fin->sms, for our case)
    # 2) group them by their first character
    # 3) order them

    to_ignore_ids = read_first_ids_from(ignore_file)

    relations = (
        Relation.objects.filter(checked=True, type=TRANSLATION)
        .exclude(pk__in=to_ignore_ids)
        .prefetch_related(
            Prefetch(
                "lexeme_from",
                queryset=Lexeme.objects.prefetch_related("miniparadigm_set"),
            ),
            Prefetch(
                "lexeme_to",
                queryset=Lexeme.objects.prefetch_related("miniparadigm_set"),
            ),
            "relationexample_set",
            "relationmetadata_set",
        )
        .filter(lexeme_from__language=src_lang, lexeme_to__language=tgt_lang)
        .annotate(
            lexeme_fc=Upper(
                Substr(Cast("lexeme_from__lexeme", models.CharField()), 1, 1)
            ),
            lexeme_fcl=Substr(
                Cast("lexeme_from__lexeme_lang", models.CharField()), 1, 1
            ),
        )
        .order_by("lexeme_fcl")
        .all()
    )

    grouped_relations = groupby(
        sorted(relations, key=lambda r: r.lexeme_fcl), key=lambda r: r.lexeme_fcl
    )

    in_memory = BytesIO()
    zip_file = ZipFile(in_memory, "a")

    keys = []
    for key, relations in grouped_relations:
        # group relations based on the lexeme_from (source)
        grouped_relations_source = groupby(
            sorted(relations, key=lambda r: r.lexeme_from.id),
            key=lambda r: r.lexeme_from.id,
        )
        grouped_relations_source = [
            (
                k,
                list(g),
            )
            for k, g in grouped_relations_source
        ]
        grouped_relations_source = list(
            sorted(
                grouped_relations_source, key=lambda k: k[1][0].lexeme_from.lexeme_lang
            )
        )
        _chapter_html = render_to_string(
            chapter_template, {"grouped_relations": grouped_relations_source}
        )

        alphabet = grouped_relations_source[0][1][0].lexeme_fc
        keys.append(alphabet)

        zip_file.writestr(
            "chapter-{}.tex".format(alphabet), _chapter_html.encode("utf-8")
        )
    _main_html = render_to_string(main_template, {"relation_keys": keys})
    zip_file.writestr("dictionary.tex", _main_html.encode("utf-8"))

    for _file in zip_file.filelist:
        _file.create_system = 0
        zip_file.close()

    _filename = "{}-{}-{}{}-LaTeX-export.zip".format(
        time.strftime("%Y%m%d-%H%M%S"), src_lang, tgt_lang, str(uuid.uuid4())[:5]
    )

    in_memory.seek(0)

    with open("{}/{}".format(directory_path, _filename), "wb") as f:
        f.write(in_memory.getvalue())


class Command(BaseCommand):
    """
    This function generates a LaTeX file to be used with Verdd's LaTeX template.
    Example: python manage.py export_latex -d ./latex/
    """

    help = "Command to export a LaTeX of the dictionary."

    def add_arguments(self, parser):
        parser.add_argument(
            "-d",
            "--dir",
            type=str,
            help="The directory path where to store the XMLs in.",
        )
        parser.add_argument(
            "-s",
            "--source",
            type=str,
            help="Three letter code of source language.",
        )
        parser.add_argument(
            "-t",
            "--target",
            type=str,
            nargs="?",
            default=None,
            help="Three letter code of target language.",
        )
        parser.add_argument(
            "-i",
            "--ignore",
            type=str,
            nargs="?",
            default=None,
            help="A file containing relations to be ignored. "
            "The first value must be the ID of the relation.",
        )

    def success_info(self, info):
        return self.stdout.write(self.style.SUCCESS(info))

    def error_info(self, info):
        return self.stdout.write(self.style.ERROR(info))

    def handle(self, *args, **options):
        dir_path = options["dir"]
        src_lang = options["source"]
        tgt_lang = options["target"]
        ignore_file = options["ignore"]

        if not os.path.isdir(dir_path):
            return self.error_info("The directory doesn't exist!")
        elif ignore_file and not os.path.isfile(ignore_file):
            return self.error_info("The ignore file doesn't exist.")

        export(src_lang, tgt_lang, dir_path, ignore_file)
