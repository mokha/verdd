from django.core.management.base import BaseCommand, CommandError
import io, csv, os
from ._private import *
from manageXML.models import *
from manageXML.utils import row_to_objects
from datetime import datetime
import logging
from django.db import IntegrityError

logger = logging.getLogger("verdd")  # Get an instance of a logger


def log_change(lexeme_id, lexeme, edit, note):
    logger.info(
        "%s (%d): [%s] %s on %s"
        % (
            lexeme,
            lexeme_id,
            edit,
            note,
            datetime.now().strftime("%d-%b-%Y (%H:%M:%S.%f)"),
        )
    )


def merge(main_lexeme: Lexeme, other_lexemes: tuple = ()):
    for ol in other_lexemes:
        for relation in ol.lexeme_from_lexeme_set.all():
            try:
                relation.lexeme_from = main_lexeme
                relation.save()
            except IntegrityError as ex:
                relation_changed = False
                main_relation = Relation.objects.get(
                    lexeme_from=relation.lexeme_from,
                    lexeme_to=relation.lexeme_to,
                    type=relation.type,
                )

                for source in relation.source_set.all():
                    try:
                        source.relation = main_relation
                        source.save()
                    except IntegrityError as ex:
                        pass  # do nothing, it already exists

                for metadata in relation.relationmetadata_set.all():
                    try:
                        metadata.relation = main_relation
                        metadata.save()
                    except IntegrityError as ex:
                        pass  # do nothing, it already exists

                for e in relation.relationexample_set.all():
                    try:
                        e.relation = main_relation
                        e.save()
                    except IntegrityError as ex:
                        pass  # do nothing, it already exists

                if relation.notes:
                    if main_relation.notes:
                        main_relation.notes = (
                            main_relation.notes + "\n" + relation.notes
                        )
                    else:
                        main_relation.notes = relation.notes
                    relation_changed = True
                if relation.checked and not main_relation.checked:
                    main_relation.checked = True
                    relation_changed = True
                if relation_changed:
                    main_relation.save()

        for relation in ol.lexeme_to_lexeme_set.all():
            try:
                relation.lexeme_to = main_lexeme
                relation.save()
            except IntegrityError as ex:
                relation_changed = False
                main_relation = Relation.objects.get(
                    lexeme_from=relation.lexeme_from,
                    lexeme_to=relation.lexeme_to,
                    type=relation.type,
                )

                for source in relation.source_set.all():
                    try:
                        source.relation = main_relation
                        source.save()
                    except IntegrityError as ex:
                        pass  # do nothing, it already exists

                for metadata in relation.relationmetadata_set.all():
                    try:
                        metadata.relation = main_relation
                        metadata.save()
                    except IntegrityError as ex:
                        pass  # do nothing, it already exists

                for e in relation.relationexample_set.all():
                    try:
                        e.relation = main_relation
                        e.save()
                    except IntegrityError as ex:
                        pass  # do nothing, it already exists

                if relation.notes:
                    if main_relation.notes:
                        main_relation.notes = (
                            main_relation.notes + "\n" + relation.notes
                        )
                    else:
                        main_relation.notes = relation.notes
                    relation_changed = True
                if relation.checked and not main_relation.checked:
                    main_relation.checked = True
                    relation_changed = True
                if relation_changed:
                    main_relation.save()

        for affiliation in ol.affiliation_set.all():
            try:
                affiliation.lexeme = main_lexeme
                affiliation.save()
            except IntegrityError as ex:
                pass  # do nothing, it already exists

        for mp in ol.miniparadigm_set.all():
            try:
                mp.lexeme = main_lexeme
                mp.save()
            except IntegrityError as ex:
                pass  # do nothing, it already exists

        for e in ol.example_set.all():
            try:
                e.lexeme = main_lexeme
                e.save()
            except IntegrityError as ex:
                pass  # do nothing, it already exists

        for s in ol.stem_set.all():
            try:
                s.lexeme = main_lexeme
                s.save()
            except IntegrityError as ex:
                pass  # do nothing, it already exists

        ol.delete()  # delete lexeme


def process(row, fields_length=4):
    try:
        lexemes = row_to_objects(Lexeme, row, fields_length, 0)
        merge(lexemes[0], tuple(lexemes[1:]))
        logger.info("Merged {}".format("\t".join(row)))
    except Exception as ex:
        logger.info(
            "Couldn't merge row {} because '{}'".format("\t".join(row), repr(ex))
        )


class Command(BaseCommand):
    """
    Example: python manage.py merge_lexemes -f ../data/duplicate-lexemes.tsv -d '\t' -l 4
    """

    help = (
        "This command merges duplicate lexemes, where the first lexeme in each row is considered as the main lexeme. "
        "The first field of each lexeme must be the lexeme's ID"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "-f",
            "--file",
            type=str,
            help="The CSV file to import.",
        )
        parser.add_argument(
            "-d",
            "--delimiter",
            type=str,
            nargs="?",
            default=";",
            help="The delimiter to use when reading the CSV file.",
        )
        parser.add_argument(
            "-l",
            "--length",
            type=int,
            nargs="?",
            default=4,
            help="The number of fields each lexeme has in the file.",
        )

    def handle(self, *args, **options):
        file_path = options["file"]
        d = options["delimiter"]
        fields_length = options["length"]

        if not os.path.isfile(file_path):
            raise CommandError('File "%s" does not exist.' % file_path)

        with io.open(file_path, "r", encoding="utf-8") as fp:
            reader = csv.reader(fp, delimiter=d)
            rows = list(reader)
            rows = [r for r in rows if len(r) > 0]
            for r in rows:
                process(r, fields_length)

        self.stdout.write(
            self.style.SUCCESS('Successfully processed the file "%s"' % (file_path,))
        )
