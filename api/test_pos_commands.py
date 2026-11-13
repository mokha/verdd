import csv
import os
import tempfile
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from manageXML.constants import TRANSLATION
from manageXML.models import Example, Language, Lexeme, Relation


def run(command, *args, **kwargs):
    out, err = StringIO(), StringIO()
    call_command(command, *args, stdout=out, stderr=err, **kwargs)
    return out.getvalue(), err.getvalue()


class PosCommandTests(TestCase):
    def setUp(self):
        for code in ("sms", "fin"):
            Language.objects.create(id=code, name=code)
        self.user = User.objects.create_user("cleaner", is_staff=True)

    def lex(self, text, pos, language="sms", homo=0):
        return Lexeme.objects.create(lexeme=text, language_id=language, pos=pos, homoId=homo)

    def build(self):
        """One of every situation the commands must tell apart."""
        data = {}
        data["alone_empty"] = self.lex("a", "")                   # no sibling: plain conversion
        data["alone_zero"] = self.lex("b", "ZERO")
        data["absorb"] = self.lex("c", "")                        # empty, one sibling: absorbed
        data["absorb_keeper"] = self.lex("c", "N")
        data["two_siblings"] = self.lex("d", "ZERO")              # empty but ambiguous: converted, not merged
        self.lex("d", "N"); self.lex("d", "V")
        data["has_children"] = self.lex("e", "ZERO")              # has a relation: left for inspection
        self.lex("e", "V")
        Relation.objects.create(lexeme_from=data["has_children"], lexeme_to=self.lex("olla", "V", "fin"), type=TRANSLATION)
        data["has_example"] = self.lex("f", "")
        self.lex("f", "A")
        Example.objects.create(lexeme=data["has_example"], text="x")
        data["clash_zero"] = self.lex("g", "ZERO")                # would collide with the existing UND
        data["clash_und"] = self.lex("g", "UND")
        data["clash_a"] = self.lex("h", "")                       # '' and ZERO with the same key collide
        data["clash_b"] = self.lex("h", "ZERO")
        data["already_und"] = self.lex("i", "UND")
        data["fine"] = self.lex("j", "N")
        return data

    def test_audit_reports_counts_without_changing_anything(self):
        self.build()
        before = list(Lexeme.objects.order_by("pk").values_list("pk", "pos"))
        out, _ = run("audit_pos")
        self.assertEqual(before, list(Lexeme.objects.order_by("pk").values_list("pk", "pos")))
        self.assertIn("Undetermined in total: 11", out)
        self.assertIn("(can be absorbed automatically): 1", out)          # only 'c'
        self.assertIn("Same headword and language as an entry with a real POS: 4", out)
        self.assertIn("ready for plain conversion to UND: 2", out)  # a, b; g and both h collide
        self.assertIn("would become, UND): 3", out)  # g(ZERO), h(''), h(ZERO)

    def test_dry_run_changes_nothing(self):
        self.build()
        before = list(Lexeme.objects.order_by("pk").values_list("pk", "pos"))
        out, _ = run("fix_undetermined_pos")
        self.assertEqual(before, list(Lexeme.objects.order_by("pk").values_list("pk", "pos")))
        self.assertIn("1 empty entry would be absorbed", out)
        self.assertIn("Dry run", out)

    def test_apply_needs_a_named_user(self):
        with self.assertRaisesMessage(CommandError, "--user"):
            run("fix_undetermined_pos", apply=True)
        with self.assertRaisesMessage(CommandError, "No such user"):
            run("fix_undetermined_pos", apply=True, user="nobody")

    def test_apply_absorbs_converts_and_skips_collisions(self):
        data = self.build()
        out, err = run("fix_undetermined_pos", apply=True, user="cleaner", batch_size=2)
        self.assertEqual(err, "")

        self.assertFalse(Lexeme.objects.filter(pk=data["absorb"].pk).exists(), "absorbed into its single sibling")
        self.assertTrue(Lexeme.objects.filter(pk=data["absorb_keeper"].pk).exists())
        pos = lambda key: Lexeme.objects.get(pk=data[key].pk).pos
        for key in ("alone_empty", "alone_zero", "two_siblings", "has_children", "has_example"):
            self.assertEqual(pos(key), "UND", key)
        self.assertEqual(pos("already_und"), "UND")
        self.assertEqual(pos("fine"), "N")
        for key, expected in (("clash_zero", "ZERO"), ("clash_und", "UND"), ("clash_a", ""), ("clash_b", "ZERO")):
            self.assertEqual(pos(key), expected, "%s is left for manual handling" % key)
        self.assertIn("3 left alone", out)

        # What still needs a person is exactly what the Merge tab shows.
        self.assertEqual(Lexeme.objects.get(pk=data["has_children"].pk).lexeme_from_lexeme_set.count(), 1)

    def test_history_names_the_user_and_the_reason(self):
        data = self.build()
        run("fix_undetermined_pos", "--skip-absorb", apply=True, user="cleaner")
        record = Lexeme.history.filter(id=data["alone_zero"].pk).order_by("-history_id").first()
        self.assertEqual(record.pos, "UND")
        self.assertEqual(record.history_user, self.user)
        self.assertIn("UND", record.history_change_reason)
        self.assertEqual(Lexeme.objects.get(pk=data["alone_zero"].pk).changed_by, self.user)

    def test_no_history_option_skips_history_rows(self):
        data = self.build()
        before = Lexeme.history.count()
        run("fix_undetermined_pos", "--skip-absorb", apply=True, user="cleaner", no_history=True)
        self.assertEqual(Lexeme.history.count(), before)
        self.assertEqual(Lexeme.objects.get(pk=data["alone_zero"].pk).pos, "UND")

    def test_second_run_finds_nothing_to_do(self):
        self.build()
        run("fix_undetermined_pos", apply=True, user="cleaner")
        out, _ = run("fix_undetermined_pos", apply=True, user="cleaner")
        self.assertIn("0 empty entries absorbed", out)
        self.assertIn("0 set to UND", out)

    def test_language_filter_and_limit(self):
        self.lex("a", "ZERO", "sms"); self.lex("a", "ZERO", "fin"); self.lex("b", "ZERO", "sms")
        run("fix_undetermined_pos", "--skip-absorb", apply=True, user="cleaner", language="fin")
        self.assertEqual(Lexeme.objects.filter(pos="ZERO").count(), 2)
        run("fix_undetermined_pos", "--skip-absorb", apply=True, user="cleaner", limit=1, batch_size=1)
        self.assertEqual(Lexeme.objects.filter(pos="ZERO").count(), 1)


class RenamePosTests(TestCase):
    def setUp(self):
        for code in ("sms", "fin"):
            Language.objects.create(id=code, name=code)
        self.user = User.objects.create_user("cleaner", is_staff=True)

    def lex(self, text, pos, language="sms", homo=0):
        return Lexeme.objects.create(lexeme=text, language_id=language, pos=pos, homoId=homo)

    def pos(self, lexeme):
        return Lexeme.objects.get(pk=lexeme.pk).pos

    def test_dry_run_changes_nothing(self):
        a, b = self.lex("a", "Desc"), self.lex("b", "Ideoph")
        out, _ = run("rename_pos", "Descr", "Desc", "Ideoph")
        self.assertEqual((self.pos(a), self.pos(b)), ("Desc", "Ideoph"))
        self.assertIn("2 would be set to Descr", out)
        self.assertIn("Dry run", out)

    def test_apply_needs_a_named_user(self):
        with self.assertRaisesMessage(CommandError, "--user"):
            run("rename_pos", "Descr", "Desc", apply=True)
        with self.assertRaisesMessage(CommandError, "No such user"):
            run("rename_pos", "Descr", "Desc", apply=True, user="nobody")

    def test_apply_unifies_and_leaves_other_values_alone(self):
        desc, ideoph, descr = self.lex("a", "Desc"), self.lex("b", "Ideoph"), self.lex("c", "Descr")
        noun, other = self.lex("d", "N"), self.lex("e", "Desc", "fin")
        run("rename_pos", "Descr", "Desc", "Ideoph", apply=True, user="cleaner", batch_size=2)
        for lexeme in (desc, ideoph, descr, other):
            self.assertEqual(self.pos(lexeme), "Descr")
        self.assertEqual(self.pos(noun), "N")
        self.assertEqual(Lexeme.objects.get(pk=desc.pk).changed_by, self.user)
        self.assertEqual(Lexeme.objects.get(pk=descr.pk).changed_by, None, "an entry already Descr is not touched")

    def test_collisions_are_left_alone_and_listed(self):
        clash_desc, clash_descr = self.lex("a", "Desc"), self.lex("a", "Descr")   # Descr exists already
        two_a, two_b = self.lex("b", "Desc"), self.lex("b", "Ideoph")             # both would become Descr
        numbered = self.lex("c", "Desc"); self.lex("c", "Descr", homo=1)           # told apart by homonym number
        other_lang = self.lex("d", "Desc"); self.lex("d", "Descr", "fin")
        out, _ = run("rename_pos", "Descr", "Desc", "Ideoph", apply=True, user="cleaner")
        self.assertEqual(self.pos(clash_desc), "Desc")
        self.assertEqual((self.pos(two_a), self.pos(two_b)), ("Desc", "Ideoph"))
        self.assertEqual(self.pos(numbered), "Descr")
        self.assertEqual(self.pos(other_lang), "Descr")
        self.assertIn("3 left alone", out)

    def test_history_names_the_user_and_the_reason(self):
        lexeme = self.lex("a", "Ideoph")
        run("rename_pos", "Descr", "Desc", "Ideoph", apply=True, user="cleaner")
        record = Lexeme.history.filter(id=lexeme.pk).order_by("-history_id").first()
        self.assertEqual(record.pos, "Descr")
        self.assertEqual(record.history_user, self.user)
        self.assertIn("Descr", record.history_change_reason)

    def test_language_filter_and_second_run(self):
        sms, fin = self.lex("a", "Desc", "sms"), self.lex("a", "Desc", "fin")
        run("rename_pos", "Descr", "Desc", apply=True, user="cleaner", language="fin")
        self.assertEqual((self.pos(sms), self.pos(fin)), ("Desc", "Descr"))
        run("rename_pos", "Descr", "Desc", apply=True, user="cleaner")
        out, _ = run("rename_pos", "Descr", "Desc", apply=True, user="cleaner")
        self.assertIn("0 set to Descr", out)

    def test_target_among_sources_is_ignored_and_nothing_to_replace_is_an_error(self):
        lexeme = self.lex("a", "Desc")
        run("rename_pos", "Descr", "Descr", "Desc", apply=True, user="cleaner")
        self.assertEqual(self.pos(lexeme), "Descr")
        with self.assertRaisesMessage(CommandError, "at least one"):
            run("rename_pos", "Descr", "Descr")


class ConvertPosCsvTests(TestCase):
    """convert_pos_csv: the listed entries change POS, nothing else does."""

    def setUp(self):
        for code in ("sms", "fin"):
            Language.objects.create(id=code, name=code)
        self.user = User.objects.create_user("cleaner", is_staff=True)
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)

    def lex(self, text, pos="N", language="fin", homo=0, **extra):
        return Lexeme.objects.create(lexeme=text, language_id=language, pos=pos, homoId=homo, **extra)

    def pos(self, lexeme):
        return Lexeme.objects.get(pk=lexeme.pk).pos

    def csv(self, *lexemes, header=True, name="approved.csv"):
        path = os.path.join(self.folder.name, name)
        with open(path, "w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            if header:
                writer.writerow(["ID", "Language", "Lexeme", "POS", "Contlex", "Inflex Type"])
            for item in lexemes:
                if isinstance(item, Lexeme):
                    item = [item.pk, item.language_id, item.lexeme, item.pos, item.contlex, ""]
                writer.writerow(item)
        return path

    def test_dry_run_changes_nothing(self):
        a = self.lex("Aatu")
        out, _ = run("convert_pos_csv", self.csv(a), "N", "Prop")
        self.assertEqual(self.pos(a), "N")
        self.assertIn("1 would be set to Prop", out)
        self.assertIn("Dry run", out)

    def test_apply_needs_a_named_user(self):
        path = self.csv(self.lex("Aatu"))
        with self.assertRaisesMessage(CommandError, "--user"):
            run("convert_pos_csv", path, "N", "Prop", apply=True)
        with self.assertRaisesMessage(CommandError, "No such user"):
            run("convert_pos_csv", path, "N", "Prop", apply=True, user="root")

    def test_bad_arguments_and_files(self):
        path = self.csv(self.lex("Aatu"))
        with self.assertRaisesMessage(CommandError, "same"):
            run("convert_pos_csv", path, "N", "N")
        with self.assertRaisesMessage(CommandError, "Cannot read"):
            run("convert_pos_csv", os.path.join(self.folder.name, "missing.csv"), "N", "Prop")
        with self.assertRaisesMessage(CommandError, "numeric ID"):
            run("convert_pos_csv", self.csv(), "N", "Prop")

    def test_apply_changes_only_the_pos_of_the_listed_entries(self):
        listed = self.lex("Aatu", contlex="PROPER_NOUN", notes="kept", checked=True)
        unlisted = self.lex("Eero")
        other_pos = self.lex("juosta", "V")
        before = Lexeme.objects.get(pk=listed.pk)
        run("convert_pos_csv", self.csv(listed), "N", "Prop", apply=True, user="cleaner")
        after = Lexeme.objects.get(pk=listed.pk)
        self.assertEqual(after.pos, "Prop")
        for field in ("lexeme", "language_id", "homoId", "contlex", "notes", "checked", "inflexType"):
            self.assertEqual(getattr(after, field), getattr(before, field), field)
        self.assertEqual(self.pos(unlisted), "N")
        self.assertEqual(self.pos(other_pos), "V")
        self.assertEqual(after.changed_by, self.user)

    def test_rows_that_do_not_match_ve_rdd_are_left_out_and_reported(self):
        good = self.lex("Aatu")
        wrong_lexeme, wrong_language = self.lex("Eero"), self.lex("Ilmari")
        changed_since, already = self.lex("Kalle", "V"), self.lex("Pekka", "Prop")
        rows = [
            good,
            [wrong_lexeme.pk, "fin", "Eerop", "N", "", ""],
            [wrong_language.pk, "sms", "Ilmari", "N", "", ""],
            [changed_since.pk, "fin", "Kalle", "N", "", ""],       # the list says N, Ve'rdd has V now
            [already.pk, "fin", "Pekka", "N", "", ""],
            [999999, "fin", "Nobody", "N", "", ""],
            ["abc", "fin", "Bad", "N", "", ""],
        ]
        skipped = os.path.join(self.folder.name, "skipped.csv")
        out, _ = run("convert_pos_csv", self.csv(*rows), "N", "Prop", apply=True, user="cleaner", skipped=skipped)
        self.assertEqual(self.pos(good), "Prop")
        self.assertEqual((self.pos(wrong_lexeme), self.pos(wrong_language)), ("N", "N"))
        self.assertEqual(self.pos(changed_since), "V")
        self.assertIn("1 set to Prop", out)
        self.assertIn("6 rows left out", out)
        with open(skipped, encoding="utf-8-sig") as handle:
            lines = list(csv.reader(handle))
        self.assertEqual(lines[0][-1], "Reason")
        self.assertEqual(len(lines), 1 + 6)

    def test_an_entry_that_would_collide_is_left_alone(self):
        clash, existing = self.lex("Pietari"), self.lex("Pietari", "Prop")
        numbered = self.lex("Aatu"); self.lex("Aatu", "Prop", homo=1)   # told apart by homonym number
        other_language = self.lex("Eero"); self.lex("Eero", "Prop", "sms")
        out, _ = run("convert_pos_csv", self.csv(clash, numbered, other_language), "N", "Prop", apply=True, user="cleaner")
        self.assertEqual((self.pos(clash), self.pos(existing)), ("N", "Prop"))
        self.assertEqual((self.pos(numbered), self.pos(other_language)), ("Prop", "Prop"))
        self.assertIn("1 row left out", out)
        self.assertIn("Merge tab", out)

    def test_output_is_the_list_with_only_the_pos_changed(self):
        a, b = self.lex("Aatu", contlex="PROPER_NOUN"), self.lex("Eero", contlex="PROPER_NOUN")
        target = os.path.join(self.folder.name, "converted.csv")
        run("convert_pos_csv", self.csv(a, b), "N", "Prop", output=target)   # a dry run still writes it
        with open(target, encoding="utf-8-sig") as handle:
            lines = list(csv.reader(handle))
        self.assertEqual(lines[0][:4], ["ID", "Language", "Lexeme", "POS"])
        self.assertEqual(lines[1], [str(a.pk), "fin", "Aatu", "Prop", "PROPER_NOUN", ""])
        self.assertEqual(self.pos(a), "N", "the dry run changed nothing in the database")

    def test_history_names_the_user_and_the_reason(self):
        lexeme = self.lex("Aatu")
        run("convert_pos_csv", self.csv(lexeme), "N", "Prop", apply=True, user="cleaner")
        record = Lexeme.history.filter(id=lexeme.pk).order_by("-history_id").first()
        self.assertEqual(record.pos, "Prop")
        self.assertEqual(record.history_user, self.user)
        self.assertIn("approved list", record.history_change_reason)

    def test_no_history_option_and_a_second_run(self):
        lexeme = self.lex("Aatu")
        path = self.csv(lexeme)
        before = Lexeme.history.count()
        run("convert_pos_csv", path, "N", "Prop", apply=True, user="cleaner", no_history=True)
        self.assertEqual(Lexeme.history.count(), before)
        out, _ = run("convert_pos_csv", path, "N", "Prop", apply=True, user="cleaner")
        self.assertIn("0 set to Prop", out)
        self.assertIn("already has the target POS", out)

    def test_batches_cover_every_row(self):
        lexemes = [self.lex("Nimi%d" % n) for n in range(7)]
        run("convert_pos_csv", self.csv(*lexemes), "N", "Prop", apply=True, user="cleaner", batch_size=3)
        self.assertEqual([self.pos(l) for l in lexemes], ["Prop"] * 7)

    # --- --merge-clashes: an entry that already exists with the target POS is merged into it ---

    def clash_pair(self, text="Pietari", **listed_extra):
        """The listed N entry and the Prop entry it would collide with."""
        return self.lex(text, "N", **listed_extra), self.lex(text, "Prop")

    def translation(self, source, text="Peter", language="sms"):
        return Relation.objects.create(lexeme_from=source, lexeme_to=self.lex(text, "N", language), type=TRANSLATION)

    def test_a_clash_is_left_alone_unless_merging_is_asked_for(self):
        listed, existing = self.clash_pair()
        run("convert_pos_csv", self.csv(listed), "N", "Prop", apply=True, user="cleaner")
        self.assertTrue(Lexeme.objects.filter(pk=listed.pk).exists())
        self.assertEqual((self.pos(listed), self.pos(existing)), ("N", "Prop"))

    def test_merge_dry_run_previews_and_changes_nothing(self):
        listed, existing = self.clash_pair()
        relation = self.translation(listed)
        out, _ = run("convert_pos_csv", self.csv(listed), "N", "Prop", merge_clashes=True)
        self.assertIn("1 would be merged into the existing Prop entry", out)
        self.assertIn("1 relations", out)
        self.assertTrue(Lexeme.objects.filter(pk=listed.pk).exists(), "the dry run deletes nothing")
        self.assertEqual(Relation.objects.get(pk=relation.pk).lexeme_from_id, listed.pk)

    def test_merge_moves_everything_to_the_existing_entry_and_deletes_the_listed_one(self):
        listed, existing = self.clash_pair()
        relation = self.translation(listed)
        example = Example.objects.create(lexeme=listed, text="Pietari tuli.")
        out, _ = run("convert_pos_csv", self.csv(listed), "N", "Prop", merge_clashes=True, apply=True, user="cleaner")
        self.assertIn("1 merged into the existing Prop entry", out)
        self.assertFalse(Lexeme.objects.filter(pk=listed.pk).exists())
        self.assertEqual(Relation.objects.get(pk=relation.pk).lexeme_from_id, existing.pk)
        self.assertEqual(Example.objects.get(pk=example.pk).lexeme_id, existing.pk)
        kept = Lexeme.objects.get(pk=existing.pk)
        self.assertEqual((kept.pos, kept.lexeme, kept.homoId), ("Prop", "Pietari", 0), "the existing entry keeps its own identity")

    def test_equal_relations_are_folded_not_duplicated(self):
        listed, existing = self.clash_pair()
        target = self.lex("Peter", "N", "sms")
        for source in (listed, existing):
            Relation.objects.create(lexeme_from=source, lexeme_to=target, type=TRANSLATION)
        out, _ = run("convert_pos_csv", self.csv(listed), "N", "Prop", merge_clashes=True, apply=True, user="cleaner")
        self.assertEqual(Relation.objects.filter(lexeme_from=existing, lexeme_to=target).count(), 1)
        self.assertEqual(Relation.objects.filter(lexeme_to=target).count(), 1)
        self.assertIn("folded into equal rows", out)

    def test_an_approved_existing_entry_that_receives_something_is_unapproved(self):
        listed, existing = self.clash_pair()
        Lexeme.objects.filter(pk=existing.pk).update(checked=True)
        self.translation(listed)
        out, _ = run("convert_pos_csv", self.csv(listed), "N", "Prop", merge_clashes=True, apply=True, user="cleaner")
        self.assertFalse(Lexeme.objects.get(pk=existing.pk).checked)
        self.assertIn("marked unapproved", out)

    def test_merging_and_converting_in_one_list(self):
        clash_listed, existing = self.clash_pair("Pietari")
        plain = self.lex("Aatu")
        out, _ = run("convert_pos_csv", self.csv(clash_listed, plain), "N", "Prop", merge_clashes=True, apply=True, user="cleaner")
        self.assertEqual(self.pos(plain), "Prop")
        self.assertFalse(Lexeme.objects.filter(pk=clash_listed.pk).exists())
        self.assertIn("1 set to Prop", out)
        self.assertIn("1 merged", out)

    def test_a_homonym_number_keeps_two_entries_apart_even_when_merging(self):
        listed = self.lex("Pietari", "N", homo=1)
        other = self.lex("Pietari", "Prop", homo=0)          # another homonym, not a clash
        run("convert_pos_csv", self.csv(listed), "N", "Prop", merge_clashes=True, apply=True, user="cleaner")
        self.assertEqual(self.pos(listed), "Prop", "converted, not merged")
        self.assertTrue(Lexeme.objects.filter(pk=other.pk).exists())
