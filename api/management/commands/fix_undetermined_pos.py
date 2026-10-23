from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
from simple_history.utils import bulk_update_with_history

from api.management.commands.audit_pos import CONVERTIBLE, collision_filter
from api.merge import MergeError, merge_lexemes, siblings_of, undetermined_q, with_merge_info
from manageXML.models import Lexeme

REASON = "Undetermined POS (empty/ZERO) set to UND"


class Command(BaseCommand):
    help = (
        "Clean up undetermined POS values in batches. First absorbs empty entries into their "
        "single same-word entry that has a real POS, then sets the remaining empty/ZERO POS to UND. "
        "Dry run unless --apply is given. Run audit_pos first."
    )

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Make the changes (default is a dry run).")
        parser.add_argument("--user", help="Username recorded as the author of the changes (required with --apply).")
        parser.add_argument("--language", help="Only this language (ISO 639-3).")
        parser.add_argument("--skip-absorb", action="store_true", help="Do not absorb empty entries into siblings.")
        parser.add_argument("--skip-convert", action="store_true", help="Do not convert the remaining entries to UND.")
        parser.add_argument("--batch-size", type=int, default=2000)
        parser.add_argument("--limit", type=int, help="Stop after this many entries per step (for trial runs).")
        parser.add_argument("--no-history", action="store_true", help="Convert without writing history rows (much smaller log).")

    def handle(self, *args, **options):
        self.apply = options["apply"]
        self.language = options["language"]
        self.pretend_absorbed = not self.apply and not options["skip_absorb"]
        self.batch = options["batch_size"]
        self.limit = options["limit"]
        self.user = None
        if self.apply:
            if not options["user"]:
                raise CommandError("--user is required with --apply, so the history names who made the changes.")
            try:
                self.user = User.objects.get(username=options["user"])
            except User.DoesNotExist:
                raise CommandError("No such user: %s" % options["user"])
        self.stdout.write("%s run%s" % ("APPLY" if self.apply else "DRY", " for " + self.language if self.language else ""))

        if not options["skip_absorb"]:
            self.absorb_empty()
        if not options["skip_convert"]:
            self.convert(history=not options["no_history"])
        if not self.apply:
            self.stdout.write("\nDry run: nothing was changed. Add --apply --user NAME to make the changes.")

    def base(self):
        queryset = Lexeme.objects.all()
        return queryset.filter(language_id=self.language) if self.language else queryset

    def batches(self, build_queryset):
        """Yield lists of primary keys, resuming after the last one so a batch's own changes
        cannot cause rows to be skipped or revisited."""
        last, seen = 0, 0
        while True:
            ids = list(build_queryset().filter(pk__gt=last).order_by("pk").values_list("pk", flat=True)[: self.batch])
            if not ids or (self.limit and seen >= self.limit):
                return
            last = ids[-1]
            seen += len(ids)
            yield ids

    def absorb_empty(self):
        def build():
            annotated, has_children = with_merge_info(self.base().filter(undetermined_q()))
            return annotated.filter(sibling_count=1).exclude(has_children)

        done = failed = 0
        for ids in self.batches(build):
            for lexeme in Lexeme.objects.filter(pk__in=ids).order_by("pk"):
                if not self.apply:
                    done += 1
                    continue
                keeper = siblings_of(lexeme).first()
                try:
                    merge_lexemes(lexeme, keeper, self.user)
                    done += 1
                except MergeError as exc:
                    failed += 1
                    self.stderr.write("  #%d not merged: %s" % (lexeme.pk, exc))
            self.stdout.write("  absorbed so far: %d" % done)
        self.stdout.write("Absorb step: %d empty entr%s %s%s." % (
            done, "y" if done == 1 else "ies", "absorbed" if self.apply else "would be absorbed",
            ", %d failed" % failed if failed else ""))

    def convert(self, history):
        def build():
            queryset = self.base().filter(pos__in=CONVERTIBLE).annotate(collides=collision_filter()).filter(collides=False)
            if self.pretend_absorbed:
                # A dry run has not absorbed anything yet; leave those out so they are not counted twice.
                annotated, has_children = with_merge_info(queryset)
                queryset = annotated.exclude(Q(sibling_count=1) & ~has_children)
            return queryset

        converted = 0
        for ids in self.batches(build):
            if self.apply:
                with transaction.atomic():
                    objs = list(Lexeme.objects.filter(pk__in=ids))
                    for lexeme in objs:
                        lexeme.pos = "UND"
                        lexeme.changed_by = self.user
                    if history:
                        bulk_update_with_history(
                            objs, Lexeme, ["pos", "changed_by"], batch_size=self.batch,
                            default_user=self.user, default_change_reason=REASON,
                        )
                    else:
                        Lexeme.objects.bulk_update(objs, ["pos", "changed_by"], batch_size=self.batch)
            converted += len(ids)
            self.stdout.write("  converted so far: %d" % converted)

        skipped = self.base().filter(pos__in=CONVERTIBLE).annotate(collides=collision_filter()).filter(collides=True).count()
        self.stdout.write("Convert step: %d %s to UND." % (converted, "set" if self.apply else "would be set"))
        if skipped:
            self.stdout.write("  %d left alone: they would collide with an existing entry of the same string, "
                              "language and homonym (see audit_pos); give them a homonym number or merge them by hand." % skipped)
