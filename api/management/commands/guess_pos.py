import re
from collections import Counter, defaultdict

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from simple_history.utils import bulk_update_with_history

from api import pos_guess
from api.merge import UNDETERMINED_POS, MergeError, merge_lexemes
from manageXML.models import Lexeme

OUTCOMES = (
    "set", "merge", "ambiguous", "no reading", "unmapped", "multiword",
    "several candidates", "would collide",
)


class Command(BaseCommand):
    help = (
        "Assign a POS to undetermined (empty/ZERO/UND) lexemes when the UralicNLP analyzer of their "
        "language gives the headword exactly one POS. If an entry of that language, headword and POS "
        "already exists, the undetermined entry is merged into it. Dry run unless --apply is given."
    )

    def add_arguments(self, parser):
        parser.add_argument("--languages", nargs="+", required=True, help="ISO 639-3 codes, e.g. rus por cat.")
        parser.add_argument("--apply", action="store_true", help="Make the changes (default is a dry run).")
        parser.add_argument("--user", help="Username recorded as the author (required with --apply).")
        parser.add_argument("--batch-size", type=int, default=2000)
        parser.add_argument("--limit", type=int, help="Stop after this many entries per language (trial runs).")
        parser.add_argument("--sample", type=int, default=5, help="Examples to print per language and outcome.")

    def handle(self, *args, **options):
        self.apply = options["apply"]
        self.batch = options["batch_size"]
        self.limit = options["limit"]
        self.sample = options["sample"]
        self.user = None
        if self.apply:
            if not options["user"]:
                raise CommandError("--user is required with --apply, so the history names who made the changes.")
            try:
                self.user = User.objects.get(username=options["user"])
            except User.DoesNotExist:
                raise CommandError("No such user: %s" % options["user"])

        missing = [l for l in options["languages"] if not pos_guess.models_installed(l)]
        if missing:
            raise CommandError(
                "No UralicNLP analyzer installed for: %s. Download with: venv/bin/python -c "
                "\"from uralicNLP import uralicApi; [uralicApi.download(l) for l in (%s)]\""
                % (", ".join(missing), ", ".join(repr(l) for l in missing))
            )

        self.stdout.write("%s run" % ("APPLY" if self.apply else "DRY"))
        totals = Counter()
        for language in options["languages"]:
            totals.update(self.run_language(language))
        self.stdout.write("\nAll languages: " + self.summary(totals))
        if not self.apply:
            self.stdout.write("Dry run: nothing was changed. Add --apply --user NAME to make the changes.")

    def summary(self, counts):
        return ", ".join("%s %d" % (name, counts[name]) for name in OUTCOMES if counts[name]) or "nothing to do"

    def run_language(self, language):
        counts, assigned = Counter(), Counter()
        samples = defaultdict(list)
        planned = set()
        last, seen = 0, 0
        base = Lexeme.objects.filter(language_id=language, pos__in=UNDETERMINED_POS)

        while True:
            ids = list(base.filter(pk__gt=last).order_by("pk").values_list("pk", flat=True)[: self.batch])
            if not ids or (self.limit and seen >= self.limit):
                break
            last, seen = ids[-1], seen + len(ids)
            entries = list(Lexeme.objects.filter(pk__in=ids).order_by("pk"))

            real = defaultdict(list)
            determined = Lexeme.objects.filter(language_id=language, lexeme__in={e.lexeme for e in entries})
            for other in determined.exclude(pos__in=UNDETERMINED_POS):
                real[other.lexeme].append(other)

            to_set = []
            for entry in entries:
                outcome, pos, keeper = self.decide(entry, language, real.get(entry.lexeme, []), planned)
                counts[outcome] += 1
                if outcome in ("set", "merge"):
                    assigned[pos] += 1
                if len(samples[outcome]) < self.sample:
                    samples[outcome].append("    #%d %r -> %s" % (entry.pk, entry.lexeme, self.describe(outcome, pos, keeper)))
                if outcome == "set":
                    to_set.append((entry, pos))
                elif outcome == "merge" and self.apply:
                    try:
                        merge_lexemes(entry, keeper, self.user)
                    except MergeError as exc:
                        counts["merge"] -= 1
                        counts["several candidates"] += 1
                        self.stderr.write("  #%d not merged: %s" % (entry.pk, exc))

            if to_set and self.apply:
                self.write_pos(to_set, language)

        self.stdout.write("\n%s: scanned %d. %s" % (language, seen, self.summary(counts)))
        if assigned:
            self.stdout.write("  POS %s: %s" % ("assigned" if self.apply else "that would be assigned",
                                               ", ".join("%s %d" % kv for kv in assigned.most_common())))
        for outcome in OUTCOMES:
            if samples[outcome]:
                self.stdout.write("  %s:" % outcome)
                self.stdout.write("\n".join(samples[outcome]))
        return counts

    def describe(self, outcome, pos, keeper):
        if outcome == "set":
            return "POS %s" % pos
        if outcome == "merge":
            return "merge into #%d (%s)" % (keeper.pk, pos)
        return outcome

    def decide(self, entry, language, candidates, planned):
        """Return (outcome, pos, keeper)."""
        if not entry.lexeme or re.search(r"\s", entry.lexeme):
            return "multiword", None, None
        found, unmapped = pos_guess.headword_pos(entry.lexeme, pos_guess.analyze_word(entry.lexeme, language))
        kind = pos_guess.classify(found, unmapped)
        if kind != "single":
            return kind, None, None

        pos = next(iter(found))
        same_pos = [c for c in candidates if c.pos == pos]
        if len(same_pos) == 1:
            return "merge", pos, same_pos[0]
        if len(same_pos) > 1:
            return "several candidates", pos, None

        key = (entry.lexeme, pos, entry.homoId)
        if key in planned:
            return "would collide", pos, None
        planned.add(key)
        return "set", pos, None

    def write_pos(self, to_set, language):
        with transaction.atomic():
            objs = []
            for entry, pos in to_set:
                entry.pos = pos
                entry.changed_by = self.user
                objs.append(entry)
            bulk_update_with_history(
                objs, Lexeme, ["pos", "changed_by"], batch_size=self.batch, default_user=self.user,
                default_change_reason="POS from UralicNLP analyzer (%s)" % language,
            )
