from collections import defaultdict

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Exists, OuterRef
from simple_history.utils import bulk_update_with_history

from api.merge import MergeError, merge_lexemes
from api.pos_csv import (
    CLASH, INVALID, REASONS, converted_row, judge, read_approved, write_csv,
)
from manageXML.models import Lexeme

LOOKUP_CHUNK = 500  # ids per query; SQLite allows few parameters


class Command(BaseCommand):
    help = (
        "Change the POS of the lexemes on an approved list, and nothing else: e.g. convert_pos_csv approved.csv N Prop "
        "turns the listed N entries into Prop. The list is the CSV exported from Ve'rdd's lexeme search "
        "(ID, Language, Lexeme, POS, ...), with the rows you do not approve deleted. A row is converted only "
        "when its ID, language and headword still match Ve'rdd and the entry still has the source POS; an entry "
        "that would collide with another of the same headword, language and homonym number (one that already has the "
        "target POS) is left alone and listed, unless --merge-clashes is given: then it is merged into that entry. "
        "Dry run unless --apply is given."
    )

    def add_arguments(self, parser):
        parser.add_argument("csv_file", help="The approved list: CSV with ID, Language, Lexeme and POS as its first four columns.")
        parser.add_argument("from_pos", help="The POS the entries have now and are converted from (exact spelling), e.g. N.")
        parser.add_argument("to_pos", help="The POS they end up with (exact spelling), e.g. Prop.")
        parser.add_argument("--apply", action="store_true", help="Make the changes (default is a dry run).")
        parser.add_argument("--user", help="Username recorded as the author of the changes (required with --apply).")
        parser.add_argument(
            "--merge-clashes", action="store_true",
            help="Merge an entry that already exists with the target POS (same headword, language and homonym number) "
                 "instead of leaving it alone: its relations, examples and the rest move to the existing entry, equal "
                 "rows are folded together, the existing entry keeps its headword, POS and homonym number, and the "
                 "listed entry is deleted. The dry run previews it.",
        )
        parser.add_argument("--output", help="Also write the converted rows (the list with only the POS changed) to this CSV.")
        parser.add_argument("--skipped", help="Also write the rows that are not converted, with the reason, to this CSV.")
        parser.add_argument("--batch-size", type=int, default=2000)
        parser.add_argument("--no-history", action="store_true", help="Change without writing history rows.")

    def handle(self, *args, **options):
        from_pos, to_pos = options["from_pos"], options["to_pos"]
        if from_pos == to_pos:
            raise CommandError("The source and the target POS are the same: there is nothing to convert.")
        if not from_pos or not to_pos:
            raise CommandError("Name both POS values.")
        if len(to_pos) > 25:  # Lexeme.pos max_length
            raise CommandError("%r is longer than 25 characters." % to_pos)
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

        try:
            with open(options["csv_file"], encoding="utf-8-sig") as handle:
                text = handle.read()
        except OSError as error:
            raise CommandError("Cannot read %s: %s" % (options["csv_file"], error.strerror))
        except UnicodeDecodeError:
            raise CommandError("%s is not UTF-8: save the CSV as UTF-8 and run again." % options["csv_file"])
        approved = read_approved(text)
        if not approved.rows:
            raise CommandError("No row with a numeric ID in the first column was found in %s." % options["csv_file"])

        out("%s run: %s -> %s" % ("APPLY" if apply else "DRY", from_pos, to_pos))
        out("Rows on the list: %d%s" % (len(approved.rows) + len(approved.unreadable), (
            " (%d repeating an ID are ignored)" % approved.duplicates if approved.duplicates else "")))

        # why rows are left out: reason -> [(cells, detail)]
        left = defaultdict(list)
        for line, cells, detail in approved.unreadable:
            left[INVALID].append((cells, "line %d: %s" % (line, detail)))

        ids = [row.id for row in approved.rows]
        entries = {}
        for start in range(0, len(ids), LOOKUP_CHUNK):
            entries.update(Lexeme.objects.in_bulk(ids[start:start + LOOKUP_CHUNK]))
        candidates = []
        for row in approved.rows:
            reason = judge(row, entries.get(row.id), from_pos, to_pos)
            if reason:
                left[reason].append((row.raw, "line %d" % row.line))
            else:
                candidates.append(row)

        # Another entry with the same key that already has the target POS: converting would break uniqueness.
        clash = Exists(
            Lexeme.objects.filter(
                lexeme=OuterRef("lexeme"), language=OuterRef("language"), homoId=OuterRef("homoId"), pos=to_pos,
            ).exclude(pk=OuterRef("pk"))
        )
        blocked = set()
        for start in range(0, len(candidates), LOOKUP_CHUNK):
            chunk = [row.id for row in candidates[start:start + LOOKUP_CHUNK]]
            blocked.update(Lexeme.objects.filter(pk__in=chunk).annotate(clash=clash).filter(clash=True)
                           .values_list("pk", flat=True))
        convertible, merges = [], []  # merges: (row, listed entry, the existing entry with the target POS)
        for row in candidates:
            if row.id not in blocked:
                convertible.append(row)
                continue
            entry = entries[row.id]
            keeper = None
            if options["merge_clashes"]:
                keeper = Lexeme.objects.filter(
                    lexeme=entry.lexeme, language_id=entry.language_id, homoId=entry.homoId, pos=to_pos
                ).exclude(pk=entry.pk).first()
                # POS is compared exactly: a case-insensitive database could match 'prop' for 'Prop'
                if keeper is not None and keeper.pos != to_pos:
                    keeper = None
            if keeper is None:
                left[CLASH].append((row.raw, "#%d" % row.id))
            else:
                merges.append((row, entry, keeper))

        reason = "POS %s set to %s from an approved list" % (from_pos, to_pos)
        changed = 0
        if apply:
            todo = [row.id for row in convertible]
            for start in range(0, len(todo), options["batch_size"]):
                batch = todo[start:start + options["batch_size"]]
                with transaction.atomic():
                    # the POS is checked again inside the transaction: it may have changed since the list was read
                    objs = list(Lexeme.objects.filter(pk__in=batch, pos=from_pos))
                    for lexeme in objs:
                        lexeme.pos = to_pos
                        lexeme.changed_by = user
                    if options["no_history"]:
                        Lexeme.objects.bulk_update(objs, ["pos", "changed_by"], batch_size=options["batch_size"])
                    else:
                        bulk_update_with_history(
                            objs, Lexeme, ["pos", "changed_by"], batch_size=options["batch_size"],
                            default_user=user, default_change_reason=reason,
                        )
                changed += len(objs)
                out("  changed so far: %d" % changed)
        out("\n%d %s to %s." % (changed if apply else len(convertible), "set" if apply else "would be set", to_pos))
        if apply and changed != len(convertible):
            out("%d of them changed their POS while the command ran and were left alone." % (len(convertible) - changed))

        if merges:
            # merge_lexemes moves everything attached to the listed entry onto the existing one (equal rows are folded
            # together) and deletes the listed entry; a dry run does the same and rolls it back, so the preview is exact
            merged, unapproved = 0, 0
            totals = {name: defaultdict(int) for name in ("moved", "deduplicated", "dropped")}
            for row, entry, keeper in merges:
                try:
                    result = merge_lexemes(entry, keeper, user, dry_run=not apply, allow_different_pos=True)
                except MergeError as error:
                    left[CLASH].append((row.raw, "#%d into #%d: %s" % (row.id, keeper.pk, error)))
                    continue
                merged += 1
                unapproved += bool(result["keeper_unapproved"])
                for name, counts in totals.items():
                    for label, count in result[name].items():
                        counts[label] += count
            describe = lambda counts: ", ".join("%d %s" % (n, label.replace("_", " ")) for label, n in sorted(counts.items()))
            out("\n%d %s into the existing %s entr%s." % (
                merged, "merged" if apply else "would be merged", to_pos, "y" if merged == 1 else "ies"))
            for name, text in (("moved", "moved to the existing entry"), ("deduplicated", "folded into equal rows already there"),
                               ("dropped", "dropped")):
                if totals[name]:
                    out("  %s: %s" % (text, describe(totals[name])))
            if unapproved:
                out("  %d existing entr%s marked unapproved, as a merge that adds something does." % (unapproved, "y" if unapproved == 1 else "ies"))

        total_left = sum(len(rows) for rows in left.values())
        if total_left:
            out("\n%d row%s left out:" % (total_left, "" if total_left == 1 else "s"))
            for key, rows in left.items():
                out("  %d: %s" % (len(rows), REASONS[key]))
                for cells, detail in rows[:10]:
                    out("      %s  %s" % (detail, ", ".join(cells[:4])))
                if len(rows) > 10:
                    out("      ... and %d more (see --skipped)" % (len(rows) - 10))
            if CLASH in left and not options["merge_clashes"]:
                out("Add --merge-clashes to merge the entries that clash into the existing ones "
                    "(or merge them in LangJack's Merge tab, allowing different POS).")

        if options["output"]:
            write_csv(options["output"], approved.header + [converted_row(row, to_pos) for row in convertible])
            out("\nConverted rows written to %s" % options["output"])
        if options["skipped"]:
            header = [list(row) for row in approved.header]
            if header:
                header[-1].append("Reason")
            write_csv(options["skipped"], header + [
                list(cells) + ["%s (%s)" % (REASONS[key], detail)] for key, rows in left.items() for cells, detail in rows
            ])
            out("Skipped rows written to %s" % options["skipped"])

        out("\nA converted entry changes only its POS: headword, language, homonym number, Contlex, inflection type, "
            "approval, relations and examples stay as they are."
            + (" A merged entry is deleted once everything attached to it has moved to the existing entry." if merges else ""))
        if not apply:
            out("Dry run: nothing was changed. Add --apply --user NAME to make the changes.")
