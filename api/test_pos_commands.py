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
