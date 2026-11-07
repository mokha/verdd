"""Management command: delete the stems (and so their continuation lexicons) of all lexemes of a POS.

Install as   api/management/commands/delete_stems.py   in the Ve'rdd project, then e.g.

    python manage.py delete_stems N --language sms                         # dry run
    python manage.py delete_stems N --language sms --apply --user jack     # do it

What is deleted: Stem rows (text, contlex, notes, order, status ...) of the matching lexemes, and,
by cascade, their StemMetadata rows.
What is kept: every Lexeme row and everything hanging off it (relations, examples, lexeme metadata,
affiliations, mini-paradigms, ...). Lexeme.contlex is left alone unless --clear-lexeme-contlex is given.
"""
import csv
import os
from collections import Counter
from datetime import datetime

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from simple_history.utils import bulk_update_with_history

from manageXML.models import Language, Lexeme, Stem, StemMetadata


class Command(BaseCommand):
    help = (
        "Delete all stems (and their continuation lexicons) of the lexemes with the given POS in one "
        "language, keeping the lexemes themselves. Dry run unless --apply is given. Before deleting, "
        "every stem and its metadata is written to a CSV backup, and the deletions are recorded in the "
        "history tables under --user."
    )

    def add_arguments(self, parser):
        parser.add_argument("pos", nargs="+", help="POS value(s) to clear, exact spelling, e.g. N or N A.")
        parser.add_argument("--language", required=True, help="Language (ISO 639-3), e.g. sms. Required.")
        parser.add_argument("--apply", action="store_true", help="Delete (default is a dry run).")
        parser.add_argument("--user", help="Username recorded as author of the deletions (required with --apply).")
        parser.add_argument("--backup", help="CSV backup path (default: delete_stems_<lang>_<pos>_<time>.csv in the current directory).")
        parser.add_argument("--skip-deleted", action="store_true",
                            help="Leave alone the stems of lexemes flagged deleted (default: include them).")
        parser.add_argument("--clear-lexeme-contlex", action="store_true",
                            help="Also empty Lexeme.contlex of the matching lexemes (default: leave it).")
        parser.add_argument("--batch-size", type=int, default=500)

    def handle(self, *args, **options):
        pos_values = list(dict.fromkeys(options["pos"]))
        lang = options["language"]
        apply = options["apply"]
        out = self.stdout.write

        if not Language.objects.filter(pk=lang).exists():
            raise CommandError("No such language: %s" % lang)
        user = None
        if apply:
            if not options["user"]:
                raise CommandError("--user is required with --apply, so the history names who made the changes.")
            try:
                user = User.objects.get(username=options["user"])
            except User.DoesNotExist:
                raise CommandError("No such user: %s" % options["user"])

        lexemes = Lexeme.objects.filter(language_id=lang, pos__in=pos_values)
        if options["skip_deleted"]:
            lexemes = lexemes.filter(deleted=False)
        stems = Stem.objects.filter(lexeme__in=lexemes)

        # The database may compare case-insensitively: only lexemes spelt exactly like a requested POS count.
        def exact(stem_lexeme):
            return stem_lexeme.pos in pos_values

        out("%s run: stems of %s lexemes in %s" % ("APPLY" if apply else "DRY", "/".join(pos_values), lang))
        n_lex = lexemes.count()
        out("Lexemes matching: %d (these are kept)" % n_lex)
        out("Lexemes by POS spelling: " + ", ".join(
            "%r=%d" % (p, c) for p, c in sorted(Counter(lexemes.values_list("pos", flat=True)).items())))
        if options["skip_deleted"]:
            out("Lexemes flagged deleted are skipped.")

        backup_path = options["backup"] or "delete_stems_%s_%s_%s.csv" % (
            lang, "-".join(pos_values), datetime.now().strftime("%Y%m%d-%H%M%S"))
        backup = writer = None
        if apply:
            if os.path.exists(backup_path):
                raise CommandError("Backup file exists already: %s" % backup_path)
            backup = open(backup_path, "w", newline="", encoding="utf-8")
            writer = csv.writer(backup)
            writer.writerow(["stem_id", "lexeme_id", "lexeme", "lexeme_pos", "language", "lexeme_homoId",
                             "stem_text", "stem_homoId", "stem_contlex", "stem_notes", "stem_order",
                             "stem_status", "stem_checked", "stem_added_date",
                             "metadata (type:text; ...)"])
            out("Backup: %s" % os.path.abspath(backup_path))

        contlex_counts, n_stems, n_meta, n_lex_with_stems, last = Counter(), 0, 0, set(), 0
        reason = "Stems of %s %s deleted (delete_stems)" % (lang, "/".join(pos_values))
        try:
            while True:
                ids = list(stems.filter(pk__gt=last).order_by("pk").values_list("pk", flat=True)[: options["batch_size"]])
                if not ids:
                    break
                last = ids[-1]
                batch = [s for s in Stem.objects.filter(pk__in=ids).select_related("lexeme").order_by("pk")
                         if exact(s.lexeme)]
                meta = {}
                for m in StemMetadata.objects.filter(stem_id__in=[s.pk for s in batch]).order_by("pk"):
                    meta.setdefault(m.stem_id, []).append(m)
                for s in batch:
                    contlex_counts[s.contlex] += 1
                    n_lex_with_stems.add(s.lexeme_id)
                n_stems += len(batch)
                n_meta += sum(len(v) for v in meta.values())

                if apply and batch:
                    with transaction.atomic():
                        for s in batch:
                            writer.writerow([
                                s.pk, s.lexeme_id, s.lexeme.lexeme, s.lexeme.pos, s.lexeme.language_id,
                                s.lexeme.homoId, s.text, s.homoId, s.contlex, s.notes, s.order, s.status,
                                s.checked, s.added_date.isoformat() if s.added_date else "",
                                "; ".join("%s:%s" % (m.type, m.text) for m in meta.get(s.pk, [])),
                            ])
                        backup.flush()
                        os.fsync(backup.fileno())
                        # simple_history takes the history user from changed_by of the deleted instance.
                        # Per-object delete() so signals fire and each deletion lands in the history tables.
                        for s in batch:
                            for m in meta.get(s.pk, []):
                                m.changed_by = user
                                m._change_reason = reason
                                m.delete()
                            s.changed_by = user
                            s._change_reason = reason
                            s.delete()
                out("  %s so far: %d stems, %d metadata rows" % ("deleted" if apply else "to delete", n_stems, n_meta))
        finally:
            if backup:
                backup.close()

        out("\nStem continuation lexicons %s (top 25):" % ("deleted" if apply else "to be deleted"))
        for cl, c in contlex_counts.most_common(25):
            out("  %-30r %9d" % (cl, c))
        if len(contlex_counts) > 25:
            out("  ... and %d more continuation lexicons" % (len(contlex_counts) - 25))
        out("\n%d stems of %d lexemes (+ %d stem metadata rows) %s; %d lexemes without stems; lexemes untouched."
            % (n_stems, len(n_lex_with_stems), n_meta, "deleted" if apply else "would be deleted",
               n_lex - len(n_lex_with_stems)))

        if options["clear_lexeme_contlex"]:
            targets = [lx for lx in lexemes.exclude(contlex="") if exact(lx)]
            out("\nLexeme.contlex: %d lexemes %s emptied." % (len(targets), "are being" if apply else "would be"))
            if apply and targets:
                with transaction.atomic():
                    for lx in targets:
                        lx.contlex = ""
                        lx.changed_by = user
                    bulk_update_with_history(
                        targets, Lexeme, ["contlex", "changed_by"], batch_size=options["batch_size"],
                        default_user=user, default_change_reason=reason)
        else:
            kept = sum(1 for lx in lexemes.exclude(contlex="") if exact(lx))
            if kept:
                out("\nNote: %d of these lexemes also have a lexeme-level contlex (Lexeme.contlex); left as is. "
                    "Add --clear-lexeme-contlex to empty it too." % kept)

        if not apply:
            out("\nDry run: nothing was changed. Add --apply --user NAME to delete.")
