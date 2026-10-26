from unittest import mock

from rest_framework.authtoken.models import Token

from django.contrib.auth.models import User
from manageXML.constants import LEXEME_TYPE, SYNONYM, TRANSLATION
from manageXML.models import (
    Affiliation,
    Example,
    Lexeme,
    LexemeMetadata,
    MiniParadigm,
    Relation,
    RelationExample,
    RelationExampleRelation,
    Source,
    Stem,
    StemMetadata,
)

from .tests import ApiTestCase


class MergeTestCase(ApiTestCase):
    def lex(self, text, language="sms", pos="N", homo=0, **kwargs):
        return Lexeme.objects.create(lexeme=text, language_id=language, pos=pos, homoId=homo, **kwargs)

    def rel(self, a, b, type=TRANSLATION, **kwargs):
        return Relation.objects.create(lexeme_from=a, lexeme_to=b, type=type, **kwargs)

    def merge(self, absorbed, into, dry_run=False, **extra):
        return self.client.post(
            f"/api/v1/lexemes/{absorbed.pk}/merge/", {"into": into.pk, "dry_run": dry_run, **extra}, format="json"
        )


class CandidateTests(MergeTestCase):
    def test_lists_undetermined_lexemes_that_have_a_determined_sibling(self):
        zero = self.lex("leeʹd", pos="ZERO")
        und = self.lex("kuõʹsk", pos="UND")
        empty_pos = self.lex("tääʹrr", pos="")
        verb = self.lex("leeʹd", pos="V")
        noun = self.lex("kuõʹsk", pos="N", homo=1)
        self.lex("alone", pos="ZERO")                       # no sibling at all
        self.lex("tääʹrr", pos="UND", homo=2)               # sibling is also undetermined
        self.lex("leeʹd", language="fin", pos="V")          # other language does not count
        self.rel(zero, self.lex("olla", "fin", "V"))

        results = self.client.get("/api/v1/lexemes/merge-candidates/").data["results"]
        found = {g["undetermined"]["id"]: g for g in results}
        self.assertEqual(set(found), {zero.pk, und.pk})
        self.assertNotIn(empty_pos.pk, found, "no determined sibling for tääʹrr")

        group = found[zero.pk]
        self.assertEqual([c["id"] for c in group["candidates"]], [verb.pk])
        self.assertFalse(group["undetermined"]["empty"])
        self.assertEqual(group["undetermined"]["translations"], ["olla"])
        self.assertTrue(found[und.pk]["undetermined"]["empty"])
        self.assertEqual(found[und.pk]["candidates"][0]["id"], noun.pk)

    def test_language_filter_and_paging(self):
        self.lex("a", pos="ZERO"); self.lex("a", pos="N")
        self.lex("b", "fin", pos="ZERO"); self.lex("b", "fin", pos="N")
        body = self.client.get("/api/v1/lexemes/merge-candidates/", {"language": "fin"}).data
        self.assertEqual(body["count"], 1)
        self.assertEqual(body["results"][0]["undetermined"]["language"], "fin")


class MergeTests(MergeTestCase):
    def test_empty_entry_is_absorbed_without_touching_the_keeper(self):
        absorbed, keeper = self.lex("leeʹd", pos="ZERO"), self.lex("leeʹd", pos="V", checked=True)
        response = self.merge(absorbed, keeper)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data["absorbed"]["empty"])
        self.assertEqual(response.data["moved"], {})
        self.assertFalse(Lexeme.objects.filter(pk=absorbed.pk).exists())
        keeper.refresh_from_db()
        self.assertTrue(keeper.checked, "nothing was added, so the approval stands")
        gone = Lexeme.history.filter(id=absorbed.pk, history_type="-").get()
        self.assertEqual(gone.history_user, self.staff)

    def test_dry_run_reports_but_changes_nothing(self):
        absorbed, keeper = self.lex("leeʹd", pos="ZERO"), self.lex("leeʹd", pos="V", checked=True)
        target = self.lex("olla", "fin", "V")
        relation = self.rel(absorbed, target)
        Example.objects.create(lexeme=absorbed, text="Son lij.")
        before = (Lexeme.objects.count(), Relation.objects.count(), Lexeme.history.count(), Relation.history.count())

        response = self.merge(absorbed, keeper, dry_run=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["dry_run"])
        self.assertEqual(response.data["moved"], {"examples": 1, "relations": 1})
        self.assertTrue(response.data["keeper_unapproved"])
        self.assertEqual(before, (Lexeme.objects.count(), Relation.objects.count(), Lexeme.history.count(), Relation.history.count()))
        relation.refresh_from_db()
        self.assertEqual(relation.lexeme_from_id, absorbed.pk)
        keeper.refresh_from_db()
        self.assertTrue(keeper.checked)

        real = self.merge(absorbed, keeper)
        self.assertEqual(real.data["moved"], response.data["moved"], "the preview is the real thing")

    def test_translations_and_examples_move_to_the_keeper(self):
        absorbed, keeper = self.lex("leeʹd", pos="ZERO"), self.lex("leeʹd", pos="V", checked=True)
        olla, kuusi = self.lex("olla", "fin", "V"), self.lex("tulla", "fin", "V")
        moved = self.rel(absorbed, olla)
        own = self.rel(keeper, kuusi)
        src = RelationExample.objects.create(relation=moved, language_id="sms", text="Son lij.")
        tgt = RelationExample.objects.create(relation=moved, language_id="fin", text="Hän on.")
        link = RelationExampleRelation.objects.create(example_from=src, example_to=tgt)
        incoming = self.rel(self.lex("stem", "fin", "N"), absorbed)

        response = self.merge(absorbed, keeper)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["moved"], {"relations": 2})
        self.assertEqual(
            set(keeper.lexeme_from_lexeme_set.values_list("lexeme_to__lexeme", flat=True)), {"olla", "tulla"}
        )
        moved.refresh_from_db(); incoming.refresh_from_db(); link.refresh_from_db()
        self.assertEqual(moved.lexeme_from_id, keeper.pk)
        self.assertEqual(incoming.lexeme_to_id, keeper.pk)
        self.assertEqual((link.example_from_id, link.example_to_id), (src.pk, tgt.pk))
        self.assertEqual(moved.changed_by, self.staff)
        keeper.refresh_from_db()
        self.assertFalse(keeper.checked, "content was added, so the entry is reviewed again")
        self.assertTrue(response.data["keeper_unapproved"])
        own.refresh_from_db()
        self.assertEqual(own.lexeme_from_id, keeper.pk)

    def test_equal_relations_are_folded_together(self):
        absorbed, keeper = self.lex("leeʹd", pos="ZERO"), self.lex("leeʹd", pos="V")
        olla = self.lex("olla", "fin", "V")
        mine, theirs = self.rel(absorbed, olla), self.rel(keeper, olla)
        Source.objects.create(relation=mine, name="Book A", type="x")
        Source.objects.create(relation=mine, name="Book B", type="x")
        Source.objects.create(relation=theirs, name="Book B", type="x")
        shared = RelationExample.objects.create(relation=mine, language_id="sms", text="Son lij.")
        shared_tgt = RelationExample.objects.create(relation=mine, language_id="fin", text="Hän on.")
        RelationExampleRelation.objects.create(example_from=shared, example_to=shared_tgt)
        kept = RelationExample.objects.create(relation=theirs, language_id="sms", text="Son lij.")

        response = self.merge(absorbed, keeper)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["deduplicated"]["relations"], 1)
        self.assertFalse(Relation.objects.filter(pk=mine.pk).exists())
        self.assertEqual(Relation.objects.filter(lexeme_from=keeper, lexeme_to=olla).count(), 1)
        self.assertEqual(sorted(Source.objects.filter(relation=theirs).values_list("name", flat=True)), ["Book A", "Book B"])
        self.assertEqual(RelationExample.objects.filter(relation=theirs, language_id="sms").count(), 1)
        link = RelationExampleRelation.objects.get()
        self.assertEqual(link.example_from_id, kept.pk, "the pair still links, now through the surviving example")
        self.assertEqual(link.example_to.text, "Hän on.")
        self.assertEqual(link.example_to.relation_id, theirs.pk)

    def test_relation_between_the_two_entries_is_dropped(self):
        absorbed, keeper = self.lex("leeʹd", pos="ZERO"), self.lex("leeʹd", pos="V")
        self.rel(absorbed, keeper, type=SYNONYM)
        response = self.merge(absorbed, keeper)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["dropped"], {"relations_between_the_two": 2})
        self.assertFalse(Relation.objects.exists())

    def test_symmetric_relations_do_not_double_up(self):
        absorbed, keeper = self.lex("leeʹd", pos="ZERO"), self.lex("leeʹd", pos="V")
        other = self.lex("lie", "sms", "V")
        self.rel(absorbed, other, type=SYNONYM)             # saving also created other -> absorbed
        self.assertEqual(Relation.objects.count(), 2)
        response = self.merge(absorbed, keeper)
        self.assertEqual(response.status_code, 200, response.data)
        pairs = sorted(Relation.objects.values_list("lexeme_from_id", "lexeme_to_id"))
        self.assertEqual(pairs, sorted([(keeper.pk, other.pk), (other.pk, keeper.pk)]))

    def test_other_children_move_or_fold(self):
        absorbed, keeper = self.lex("leeʹd", pos="UND"), self.lex("leeʹd", pos="V")
        for owner, text in ((absorbed, "Son lij."), (absorbed, "Mon lie."), (keeper, "Son lij.")):
            Example.objects.create(lexeme=owner, text=text)
        for owner in (absorbed, keeper):
            LexemeMetadata.objects.create(lexeme=owner, type=LEXEME_TYPE, text="Prop")
        LexemeMetadata.objects.create(lexeme=absorbed, type=LEXEME_TYPE, text="Sem")
        MiniParadigm.objects.create(lexeme=absorbed, msd="Sg+Nom", wordform="leeʹd")
        MiniParadigm.objects.create(lexeme=keeper, msd="Sg+Nom", wordform="leeʹd")
        MiniParadigm.objects.create(lexeme=absorbed, msd="Sg+Gen", wordform="leeʹd")
        Affiliation.objects.create(lexeme=absorbed, title="Akusanat", link="https://a.example/x", type=1)
        old_stem = Stem.objects.create(lexeme=absorbed, text="leeʹd", contlex="V_X")
        StemMetadata.objects.create(stem=old_stem, type=None, text="a")
        twin_stem = Stem.objects.create(lexeme=keeper, text="leeʹd", contlex="V_X")
        StemMetadata.objects.create(stem=twin_stem, type=None, text="b")
        Stem.objects.create(lexeme=absorbed, text="lie", contlex="V_Y")

        response = self.merge(absorbed, keeper)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(sorted(keeper.example_set.values_list("text", flat=True)), ["Mon lie.", "Son lij."])
        self.assertEqual(sorted(keeper.lexememetadata_set.values_list("text", flat=True)), ["Prop", "Sem"])
        self.assertEqual(keeper.miniparadigm_set.count(), 2)
        self.assertEqual(keeper.affiliation_set.count(), 1)
        self.assertEqual(keeper.stem_set.count(), 2)
        self.assertEqual(sorted(twin_stem.stemmetadata_set.values_list("text", flat=True)), ["a", "b"])
        self.assertEqual(response.data["deduplicated"]["examples"], 1)
        self.assertEqual(response.data["deduplicated"]["stems"], 1)

    def test_blank_fields_are_filled_and_conflicts_reported(self):
        absorbed = self.lex("leeʹd", pos="ZERO", contlex="V_BE", notes="old note")
        keeper = self.lex("leeʹd", pos="V", notes="kept note")
        response = self.merge(absorbed, keeper)
        self.assertEqual(response.data["fields_copied"], ["contlex"])
        self.assertTrue(any("notes" in n and "kept note" in n for n in response.data["notes"]))
        keeper.refresh_from_db()
        self.assertEqual((keeper.contlex, keeper.notes), ("V_BE", "kept note"))


class GeneralMergeTests(MergeTestCase):
    """Any two entries of a language can be joined when their POS is compatible."""

    def test_decorated_headword_folds_into_the_clean_one(self):
        decorated = self.lex("( ) pӧla", "sms", pos="ZERO")
        clean = self.lex("pӧla", "sms", pos="N", checked=True)
        borrowed = self.lex("борт", "fin", "N")
        relation = self.rel(borrowed, decorated)

        refused = self.merge(decorated, clean)
        self.assertEqual(refused.status_code, 400)
        self.assertIn("same headword", str(refused.data["into"]))
        self.assertTrue(Lexeme.objects.filter(pk=decorated.pk).exists())

        response = self.merge(decorated, clean, allow_different_headword=True)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["headword_dropped"], "( ) pӧla")
        self.assertIsNone(response.data["pos_set"])
        relation.refresh_from_db()
        self.assertEqual(relation.lexeme_to_id, clean.pk, "the incoming translation follows")
        clean.refresh_from_db()
        self.assertEqual((clean.lexeme, clean.pos), ("pӧla", "N"))
        self.assertFalse(Lexeme.objects.filter(pk=decorated.pk).exists())

    def test_equal_pos_duplicates_merge(self):
        a, b = self.lex("pӧla", pos="N", homo=0), self.lex("pӧla", pos="N", homo=1)
        self.rel(a, self.lex("olla", "fin", "V"))
        response = self.merge(b, a)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(Lexeme.objects.filter(lexeme="pӧla").count(), 1)

    def test_keeper_without_pos_takes_the_absorbed_pos(self):
        keeper = self.lex("pӧla", pos="UND", checked=True)
        absorbed = self.lex("pӧla", pos="N", homo=5)
        response = self.merge(absorbed, keeper)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["pos_set"], "N")
        self.assertTrue(response.data["keeper_unapproved"])
        keeper.refresh_from_db()
        self.assertEqual((keeper.pos, keeper.homoId, keeper.checked), ("N", 0, False))

    def test_same_homonym_slot_adopts_pos_after_the_absorbed_is_gone(self):
        keeper, absorbed = self.lex("pӧla", pos="UND"), self.lex("pӧla", pos="N")  # both homonym 0
        response = self.merge(absorbed, keeper)
        self.assertEqual(response.status_code, 200, response.data)
        keeper.refresh_from_db()
        self.assertEqual(keeper.pos, "N")

    def test_adopted_pos_must_not_clash_with_a_third_entry(self):
        keeper = self.lex("pӧla", pos="UND", homo=2)
        absorbed = self.lex("pӧla", pos="N", homo=5)
        third = self.lex("pӧla", pos="N", homo=2)
        response = self.merge(absorbed, keeper)
        self.assertEqual(response.status_code, 400)
        self.assertIn(f"#{third.pk}", str(response.data["into"]))
        self.assertTrue(Lexeme.objects.filter(pk=absorbed.pk).exists())

    def test_two_undetermined_entries_merge(self):
        a, b = self.lex("pӧla", pos="ZERO"), self.lex("pӧla", pos="UND")
        self.assertEqual(self.merge(a, b).status_code, 200)

    def test_dry_run_with_different_headwords_changes_nothing(self):
        decorated, clean = self.lex("( ) pӧla", pos="UND"), self.lex("pӧla", pos="N")
        response = self.merge(decorated, clean, dry_run=True, allow_different_headword=True)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data["dry_run"])
        self.assertTrue(Lexeme.objects.filter(pk=decorated.pk).exists())
        clean.refresh_from_db()
        self.assertEqual(clean.pos, "N")


class MergeGuardTests(MergeTestCase):
    def assertRefused(self, absorbed, into, text):
        response = self.merge(absorbed, into)
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn(text, str(response.data["into"]))
        self.assertTrue(Lexeme.objects.filter(pk=absorbed.pk).exists())

    def test_scope_is_enforced(self):
        zero, verb = self.lex("leeʹd", pos="ZERO"), self.lex("leeʹd", pos="V")
        self.assertRefused(zero, zero, "itself")
        self.assertRefused(zero, self.lex("leeʹd", "fin", "V"), "same language")
        self.assertRefused(zero, self.lex("other", pos="V"), "same headword")
        self.assertRefused(verb, self.lex("leeʹd", pos="N"), "different parts of speech")

    def test_refuses_when_an_unhandled_model_references_lexemes(self):
        zero, verb = self.lex("leeʹd", pos="ZERO"), self.lex("leeʹd", pos="V")
        with mock.patch("api.merge.HANDLED_RELATIONS", set()):
            self.assertRefused(zero, verb, "not available")

    def test_rolls_back_completely_on_failure(self):
        zero, verb = self.lex("leeʹd", pos="ZERO"), self.lex("leeʹd", pos="V")
        relation = self.rel(zero, self.lex("olla", "fin", "V"))
        with mock.patch("api.merge.child_counts", side_effect=[{"x": 0}, {"x": 0}, {"x": 1}]):
            response = self.merge(zero, verb)
        self.assertEqual(response.status_code, 400)
        relation.refresh_from_db()
        self.assertEqual(relation.lexeme_from_id, zero.pk, "a failed merge leaves the data untouched")

    def test_staff_only(self):
        zero, verb = self.lex("leeʹd", pos="ZERO"), self.lex("leeʹd", pos="V")
        reader = User.objects.create_user("reader")
        self.client.credentials(HTTP_AUTHORIZATION="Token " + Token.objects.create(user=reader).key)
        self.assertEqual(self.merge(zero, verb).status_code, 403)
        self.assertEqual(self.client.get("/api/v1/lexemes/merge-candidates/").status_code, 403)
