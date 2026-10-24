from io import StringIO
from unittest import mock

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase

from api import pos_guess
from manageXML.constants import TRANSLATION
from manageXML.models import Language, Lexeme, Relation


class ParseTests(SimpleTestCase):
    def test_giella_style(self):
        self.assertEqual(pos_guess.parse_analysis("ребёнок+N+Msc+Anim+Sg+Nom"), ("ребёнок", "N"))
        self.assertEqual(pos_guess.parse_analysis("ничто+Pron+Neg+Neu+Inan+Sg+Acc"), ("ничто", "Pron"))
        self.assertEqual(pos_guess.parse_analysis("в+Pr"), ("в", "Pr"))
        self.assertEqual(pos_guess.parse_analysis("Helsinki+N+Prop+Sg+Nom"), ("Helsinki", "Prop"))
        self.assertEqual(pos_guess.parse_analysis("leeʹd+V+Aux+IV+Inf"), ("leeʹd", "Aux"))
        self.assertEqual(pos_guess.parse_analysis("leeʹd+V+IV+Inf"), ("leeʹd", "V"))

    def test_apertium_style_ignores_gender_and_number(self):
        self.assertEqual(pos_guess.parse_analysis("casa<n><f><sg>ε"), ("casa", "N"))
        self.assertEqual(pos_guess.parse_analysis("casa<n><m><pl>"), ("casa", "N"))
        self.assertEqual(pos_guess.parse_analysis("casar<vblex><pri><p3><sg>ε"), ("casar", "V"))
        self.assertEqual(pos_guess.parse_analysis("bonito<adj><m><sg>ε"), ("bonito", "A"))
        self.assertEqual(pos_guess.parse_analysis("Lisboa<np><top><sg>ε"), ("Lisboa", "Prop"))
        self.assertEqual(pos_guess.parse_analysis("poder<vbmod><inf>ε"), ("poder", "Aux"))

    def test_unknown_tags_are_unmapped(self):
        self.assertEqual(pos_guess.parse_analysis("etc<abbr>ε"), ("etc", None))
        self.assertEqual(pos_guess.parse_analysis("foo+Weird+Sg"), ("foo", None))

    def test_only_readings_of_the_headword_itself_count(self):
        casa = ["casa<n><f><sg>ε", "casar<vblex><imp><p2><sg>ε", "casar<vblex><pri><p3><sg>ε"]
        self.assertEqual(pos_guess.headword_pos("casa", [(a, 0.0) for a in casa]), ({"N"}, False))
        falar = ["falar<n><m><sg>ε", "falar<vblex><inf>ε", "falar<vblex><fts><p1><sg>ε"]
        self.assertEqual(pos_guess.headword_pos("falar", falar), ({"N", "V"}, False))
        letter = ["в+N+Neu+Inan+Sg+Nom", "в+N+Neu+Inan+Pl+Gen", "в+Pr"]
        self.assertEqual(pos_guess.headword_pos("в", letter), ({"N", "Pr"}, False))

    def test_same_pos_with_different_gender_is_one_pos(self):
        readings = ["casa<n><f><sg>", "casa<n><m><sg>"]
        self.assertEqual(pos_guess.classify(*pos_guess.headword_pos("casa", readings)), "single")

    def test_classification(self):
        self.assertEqual(pos_guess.classify(set(), False), "no reading")
        self.assertEqual(pos_guess.classify({"N"}, True), "unmapped")
        self.assertEqual(pos_guess.classify({"N", "V"}, False), "ambiguous")
        self.assertEqual(pos_guess.headword_pos("Bio", ["bio+N+Sg"]), (set(), False), "case differences do not count")


ANALYSES = {
    ("rus", "ребёнок"): ["ребёнок+N+Msc+Anim+Sg+Nom"],
    ("por", "bonito"): ["bonito<adj><m><sg>ε"],
    ("por", "casa"): ["casa<n><f><sg>ε", "casar<vblex><pri><p3><sg>ε"],
    ("por", "falar"): ["falar<n><m><sg>ε", "falar<vblex><inf>ε"],
    ("por", "lar"): ["lar<n><m><sg>ε"],
    ("por", "mesa"): ["mesa<n><f><sg>ε"],
    ("por", "livro"): ["livro<n><m><sg>ε"],
    ("por", "gato"): ["gato<n><m><sg>ε"],
    ("cat", "xyz"): [],
    ("eng", "walk"): ["walk+N+Sg", "walk+V+Inf"],
}


def fake_analyze(word, language):
    return [(a, 0.0) for a in ANALYSES.get((language, word), [])]


def run(*args, **kwargs):
    out, err = StringIO(), StringIO()
    with mock.patch("api.pos_guess.analyze_word", side_effect=fake_analyze), \
            mock.patch("api.pos_guess.models_installed", return_value=True):
        call_command("guess_pos", *args, stdout=out, stderr=err, **kwargs)
    return out.getvalue(), err.getvalue()


class GuessPosCommandTests(TestCase):
    def setUp(self):
        for code in ("rus", "por", "cat", "eng", "fin"):
            Language.objects.create(id=code, name=code)
        self.user = User.objects.create_user("guesser", is_staff=True)

    def lex(self, text, language, pos="", homo=0):
        return Lexeme.objects.create(lexeme=text, language_id=language, pos=pos, homoId=homo)

    def build(self):
        d = {}
        d["merge"] = self.lex("ребёнок", "rus")                      # analyzer: N, and an N entry exists
        d["merge_keeper"] = self.lex("ребёнок", "rus", "N")
        d["set"] = self.lex("bonito", "por")                         # analyzer: A, nothing there yet
        d["other_pos"] = self.lex("casa", "por")                     # analyzer: N; only a verb entry exists
        self.lex("casa", "por", "V")
        d["ambiguous"] = self.lex("falar", "por")                    # noun and verb: left alone
        d["several"] = self.lex("lar", "por")                        # two N homonyms already exist
        self.lex("lar", "por", "N", 0); self.lex("lar", "por", "N", 1)
        d["multiword"] = self.lex("a casa", "por")
        d["no_reading"] = self.lex("xyz", "cat")
        d["other_language"] = self.lex("walk", "eng")                # not in --languages
        d["already_set"] = self.lex("gato", "por", "N")              # determined: never touched
        d["und_too"] = self.lex("mesa", "por", "UND")                # UND is re-guessed as well
        return d

    def test_dry_run_reports_and_changes_nothing(self):
        self.build()
        before = list(Lexeme.objects.order_by("pk").values_list("pk", "pos"))
        out, _ = run(languages=["rus", "por", "cat"])
        self.assertEqual(before, list(Lexeme.objects.order_by("pk").values_list("pk", "pos")))
        self.assertIn("Dry run", out)
        self.assertIn("rus: scanned 1. merge 1", out)
        self.assertIn("por: scanned 6.", out)
        self.assertIn("set 3", out)            # bonito, casa, mesa
        self.assertIn("ambiguous 1", out)
        self.assertIn("several candidates 1", out)
        self.assertIn("multiword 1", out)
        self.assertIn("cat: scanned 1. no reading 1", out)

    def test_apply_sets_merges_and_leaves_the_rest(self):
        d = self.build()
        out, err = run(languages=["rus", "por", "cat"], apply=True, user="guesser")
        self.assertEqual(err, "")
        pos = lambda key: Lexeme.objects.get(pk=d[key].pk).pos
        self.assertFalse(Lexeme.objects.filter(pk=d["merge"].pk).exists(), "absorbed into the existing noun")
        self.assertTrue(Lexeme.objects.filter(pk=d["merge_keeper"].pk).exists())
        self.assertEqual(pos("set"), "A")
        self.assertEqual(pos("other_pos"), "N")
        self.assertEqual(pos("und_too"), "N")
        self.assertEqual(pos("ambiguous"), "")
        self.assertEqual(pos("several"), "")
        self.assertEqual(pos("multiword"), "")
        self.assertEqual(pos("no_reading"), "")
        self.assertEqual(pos("other_language"), "")
        self.assertEqual(pos("already_set"), "N")

    def test_history_names_the_user_and_the_language(self):
        d = self.build()
        run(languages=["por"], apply=True, user="guesser")
        record = Lexeme.history.filter(id=d["set"].pk).order_by("-history_id").first()
        self.assertEqual(record.pos, "A")
        self.assertEqual(record.history_user, self.user)
        self.assertIn("(por)", record.history_change_reason)
        self.assertEqual(Lexeme.objects.get(pk=d["set"].pk).changed_by, self.user)

    def test_second_run_finds_nothing_new_to_assign(self):
        self.build()
        run(languages=["rus", "por", "cat"], apply=True, user="guesser")
        out, _ = run(languages=["rus", "por", "cat"], apply=True, user="guesser")
        self.assertNotIn("POS assigned", out)

    def test_duplicate_undetermined_entries_do_not_break_the_unique_key(self):
        self.lex("livro", "por", "", 0)
        self.lex("livro", "por", "UND", 0)       # same key once both become N
        out, _ = run(languages=["por"], apply=True, user="guesser")
        self.assertIn("would collide 1", out)
        self.assertEqual(Lexeme.objects.filter(lexeme="livro", pos="N").count(), 1)

    def test_apply_needs_a_named_user(self):
        with self.assertRaisesMessage(CommandError, "--user"):
            run(languages=["por"], apply=True)
        with self.assertRaisesMessage(CommandError, "No such user"):
            run(languages=["por"], apply=True, user="nobody")

    def test_missing_models_give_a_download_hint(self):
        with mock.patch("api.pos_guess.models_installed", side_effect=lambda l: l != "cat"):
            with self.assertRaisesMessage(CommandError, "uralicApi.download"):
                call_command("guess_pos", languages=["por", "cat"], stdout=StringIO(), stderr=StringIO())

    def test_limit_and_batching(self):
        for word in ("bonito", "mesa", "livro", "gato"):
            self.lex(word, "por")
        run(languages=["por"], apply=True, user="guesser", batch_size=1, limit=2)
        self.assertEqual(Lexeme.objects.filter(language_id="por").exclude(pos="").count(), 2)
