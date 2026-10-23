from django.core.management.base import BaseCommand
from django.db.models import Count, Exists, OuterRef

from api.merge import UNDETERMINED_POS, undetermined_q, with_merge_info
from manageXML.models import Lexeme

CONVERTIBLE = ("", "ZERO")  # become UND; UND itself is already the target


def collision_filter():
    """True when another lexeme with the same key (string, language, homonym) is, or will
    become, UND, so converting this one would break the uniqueness constraint."""
    return Exists(
        Lexeme.objects.filter(
            lexeme=OuterRef("lexeme"),
            language=OuterRef("language"),
            homoId=OuterRef("homoId"),
            pos__in=UNDETERMINED_POS,
        ).exclude(pk=OuterRef("pk"))
    )


class Command(BaseCommand):
    help = "Read-only report: how many lexemes have an undetermined POS and what fixing them involves."

    def add_arguments(self, parser):
        parser.add_argument("--language", help="Only look at this language (ISO 639-3).")

    def handle(self, *args, **options):
        base = Lexeme.objects.all()
        if options["language"]:
            base = base.filter(language_id=options["language"])
        out = self.stdout.write

        out("Lexemes%s: %d" % (" in %s" % options["language"] if options["language"] else "", base.count()))

        out("\nPOS values in use (* = treated as undetermined):")
        for row in base.order_by().values("pos").annotate(n=Count("pk")).order_by("-n"):
            marker = "*" if row["pos"] in UNDETERMINED_POS else " "
            out("  %s %-12r %9d" % (marker, row["pos"], row["n"]))

        undetermined = base.filter(undetermined_q())
        out("\nUndetermined in total: %d" % undetermined.count())
        for value in UNDETERMINED_POS:
            out("  %-8r %9d" % (value, undetermined.filter(pos=value).count()))

        annotated, has_children = with_merge_info(undetermined)
        mergeable = annotated.filter(sibling_count__gt=0)
        absorbable = mergeable.filter(sibling_count=1).exclude(has_children)
        out("\nSame headword and language as an entry with a real POS: %d" % mergeable.count())
        out("  empty, exactly one such entry (can be absorbed automatically): %d" % absorbable.count())
        out("  the rest (several candidates, or relations to inspect in LangJack's Merge tab): %d"
            % (mergeable.count() - absorbable.count()))

        convertible = annotated.filter(pos__in=CONVERTIBLE).annotate(collides=collision_filter())
        lonely = convertible.filter(sibling_count=0, collides=False)
        out("\nEmpty or ZERO with no such entry, ready for plain conversion to UND: %d" % lonely.count())

        colliding = convertible.filter(collides=True)
        out("Empty or ZERO that cannot be converted yet (an entry with the same string, language and homonym "
            "is, or would become, UND): %d" % colliding.count())
        for lexeme in colliding.order_by("pk")[:10]:
            out("    #%d %r %s pos=%r homoId=%d" % (lexeme.pk, lexeme.lexeme, lexeme.language_id, lexeme.pos, lexeme.homoId))
