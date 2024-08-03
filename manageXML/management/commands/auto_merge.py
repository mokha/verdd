from django.core.management.base import BaseCommand, CommandError
from manageXML.models import *
from manageXML.management.commands.merge_lexemes import merge as merge_lexemes
from manageXML.management.commands.merge_stems import merge as merge_stems
from manageXML.utils import get_duplicate_objects, contlex_to_pos, obj_to_txt


def handle_lexemes(objects):
    main_object = objects[0]
    last_object = objects[-1]

    # try to get the POS
    stem = (
        Stem.objects.filter(lexeme=last_object)
        .exclude(Q(text="") | Q(text__isnull=True))
        .first()
    )
    if stem:
        pos, metadata = contlex_to_pos(stem.contlex)
        if pos:
            # find if there is an existing one with the same POS
            for obj in objects[:-1]:
                if obj.pos == pos:
                    merge_lexemes(obj, (last_object,))
                    return True
            else:
                last_object.pos = pos
                last_object.save()
                for md_type, md_text in metadata:
                    LexemeMetadata.objects.get_or_create(
                        lexeme=last_object, type=md_type, text=md_text
                    )
            return True

    if len(objects) == 2:
        merge_lexemes(main_lexeme=main_object, other_lexemes=tuple(objects[1:]))
        return True
    return False


def handle_stems(objects):
    if len(objects) == 2:
        merge_stems(main_obj=objects[0], other_objs=tuple(objects[1:]))
        return True
    return False


class Command(BaseCommand):
    """
    Example: python manage.py auto_merge -d ;
    """

    help = "This command merges duplicate stems and lexemes."

    def add_arguments(self, parser):
        parser.add_argument(
            "-d",
            "--delimiter",
            type=str,
            nargs="?",
            default=";",
            help="The delimiter to use when joining fields of duplicate objects.",
        )

    def handle(self, *args, **options):
        delimiter = options["delimiter"]

        dup_criteria = (
            {
                "model": Lexeme,
                "unique_fields": (
                    "lexeme",
                    "language",
                ),
                "fields": ("id", "lexeme", "language", "pos"),
                "sort": "-pos",  # sort to get the empty value
                "handle_fn": handle_lexemes,
            },  # duplicate lexemes criteria
            {
                "model": Stem,
                "unique_fields": (
                    "lexeme",
                    "text",
                ),
                "fields": (
                    "id",
                    "lexeme__id",
                    "lexeme__language",
                    "lexeme__pos",
                    "text",
                    "contlex",
                ),
                "sort": "-contlex",
                "handle_fn": handle_stems,
            },  # duplicate stems criteria
        )

        # find duplicate lexemes
        for criteria in dup_criteria:
            # get duplicates
            model = criteria["model"]
            unique_fields = criteria["unique_fields"]
            fields_to_print = criteria["fields"]
            order_by = criteria["sort"]
            handle_fn = criteria["handle_fn"]

            duplicates = get_duplicate_objects(model=model, unique_fields=unique_fields)
            for dd in duplicates:  # for each duplicate values
                d_objects = model.objects.filter(
                    **{x: dd[x] for x in unique_fields}
                )  # get the objects that have them
                d_objects = list(d_objects.order_by(order_by).all())
                if not d_objects:
                    continue
                last_obj = d_objects[-1]  # last object would have the empty occurrence
                sort_attr = order_by[1:] if order_by.startswith("-") else order_by

                dup_line = []
                for _d in d_objects:
                    dup_str = obj_to_txt(
                        _d, fields=fields_to_print, delimiter=delimiter
                    )  # convert them to text
                    dup_line.append(dup_str)

                # it is actually empty and is handled
                if not getattr(last_obj, sort_attr) and handle_fn(objects=d_objects):
                    self.stdout.write("%s\n" % delimiter.join(dup_line))
                else:
                    self.stderr.write("%s\n" % delimiter.join(dup_line))
