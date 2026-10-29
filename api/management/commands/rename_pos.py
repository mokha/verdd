from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Exists, OuterRef
from simple_history.utils import bulk_update_with_history

from manageXML.models import LanguageParadigm, Lexeme


class Command(BaseCommand):
    help = (
        "Give lexemes one POS value in place of several, e.g. rename_pos Descr Desc Ideoph sets every "
        "Desc and Ideoph entry to Descr. An entry that would collide with another of the same string, "
        "language and homonym number is left alone and listed, to be merged or numbered by hand. "
        "Dry run unless --apply is given."
    )

    def add_arguments(self, parser):
        parser.add_argument("target", help="The POS value to end up with (exact spelling), e.g. Descr.")
        parser.add_argument("sources", nargs="+", help="The POS values to replace, e.g. Desc Ideoph.")
        parser.add_argument("--apply", action="store_true", help="Make the changes (default is a dry run).")
        parser.add_argument("--user", help="Username recorded as the author of the changes (required with --apply).")
        parser.add_argument("--language", help="Only this language (ISO 639-3).")
        parser.add_argument("--batch-size", type=int, default=2000)
        parser.add_argument("--no-history", action="store_true", help="Change without writing history rows.")

    def handle(self, *args, **options):
        target, sources = options["target"], [s for s in dict.fromkeys(options["sources"]) if s != options["target"]]
        if not sources:
            raise CommandError("Name at least one POS value other than the target to replace.")
        if len(target) > 25:  # Lexeme.pos max_length
            raise CommandError("%r is longer than 25 characters." % target)
        apply = options["apply"]
        user = None
        if apply:
            if not options["user"]:
                raise CommandError("--user is required with --apply, so the history names who made the changes.")
            try:
                user = User.objects.get(username=options["user"])
            except User.DoesNotExist:
                raise CommandError("No such user: %s" % options["user"])
        out = self.stdout.write
        out("%s run%s: %s -> %s" % ("APPLY" if apply else "DRY", " for " + options["language"] if options["language"] else "",
                                    ", ".join(sources), target))

        base = Lexeme.objects.all()
        if options["language"]:
            base = base.filter(language_id=options["language"])
        # Exact spelling matters (the database may compare case-insensitively): an entry already
        # spelt exactly as the target is never touched, and a differently-cased spelling is renamed.
        candidates = base.filter(pos__in=sources).exclude(pos=target)
        # Another entry with the same key that has, or is about to get, the target value.
        clash = Exists(
            Lexeme.objects.filter(
                lexeme=OuterRef("lexeme"), language=OuterRef("language"), homoId=OuterRef("homoId"),
                pos__in=sources + [target],
            ).exclude(pk=OuterRef("pk"))
        )
        movable = candidates.annotate(clash=clash).filter(clash=False)
        blocked = candidates.annotate(clash=clash).filter(clash=True)

        out("\nPOS values to replace, by number of entries:")
        for source in sources:
            out("  %-12s %9d" % (source, candidates.filter(pos=source).count()))
        out("Already %s: %d" % (target, base.filter(pos=target).count()))

        reason = "POS %s set to %s" % ("/".join(sources), target)
        changed, last = 0, 0
        while True:
            ids = list(movable.filter(pk__gt=last).order_by("pk").values_list("pk", flat=True)[: options["batch_size"]])
            if not ids:
                break
            last = ids[-1]
            if apply:
                with transaction.atomic():
                    objs = list(Lexeme.objects.filter(pk__in=ids))
                    for lexeme in objs:
                        lexeme.pos = target
                        lexeme.changed_by = user
                    if options["no_history"]:
                        Lexeme.objects.bulk_update(objs, ["pos", "changed_by"], batch_size=options["batch_size"])
                    else:
                        bulk_update_with_history(
                            objs, Lexeme, ["pos", "changed_by"], batch_size=options["batch_size"],
                            default_user=user, default_change_reason=reason,
                        )
            changed += len(ids)
            out("  %s so far: %d" % ("changed" if apply else "to change", changed))
        out("\n%d %s to %s." % (changed, "set" if apply else "would be set", target))

        n_blocked = blocked.count()
        if n_blocked:
            out("%d left alone: another entry with the same string, language and homonym number is, or would "
                "become, %s. Merge them in LangJack's Merge tab (allow different POS) or give one a homonym number:" % (n_blocked, target))
            for lexeme in blocked.order_by("pk")[:20]:
                out("    #%d %r %s pos=%r homoId=%d" % (lexeme.pk, lexeme.lexeme, lexeme.language_id, lexeme.pos, lexeme.homoId))
            if n_blocked > 20:
                out("    ... and %d more" % (n_blocked - 20))

        paradigms = LanguageParadigm.objects.filter(pos__in=sources)
        if paradigms.exists():
            out("\nNote: %d language-paradigm row(s) use %s as POS; this command does not change them."
                % (paradigms.count(), ", ".join(sorted(set(paradigms.values_list("pos", flat=True))))))
        if not apply:
            out("\nDry run: nothing was changed. Add --apply --user NAME to make the changes.")
