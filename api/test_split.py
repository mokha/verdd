from manageXML.constants import ETYMOLOGY, LEXEME_TYPE, SYNONYM
from manageXML.models import (
    Example,
    Lexeme,
    LexemeMetadata,
    MiniParadigm,
    Relation,
    RelationExample,
    RelationExampleRelation,
)

from .test_merge import MergeTestCase


class SplitTestCase(MergeTestCase):
    def split(self, source, dry_run=False, **body):
        return self.client.post(
            f"/api/v1/lexemes/{source.pk}/split/", {"dry_run": dry_run, **body}, format="json"
        )


class SplitTests(SplitTestCase):
    def setUp(self):
        super().setUp()
        self.source = self.lex("pӧla", "sms", "N", checked=True)
        self.beside = self.lex("vieressä", "fin", "Adv")
        self.side = self.lex("puoli", "fin", "N")
        self.to_beside = self.rel(self.source, self.beside)
        self.to_side = self.rel(self.source, self.side)

    def test_moves_chosen_translations_to_a_new_homonym(self):
        incoming = self.rel(self.lex("борт", "fin", "N"), self.source)
        response = self.split(self.source, relations=[self.to_side.pk, incoming.pk])
        self.assertEqual(response.status_code, 201, response.data)
        new = Lexeme.objects.get(pk=response.data["new"]["id"])
        self.assertEqual((new.lexeme, new.pos, new.language_id, new.homoId), ("pӧla", "N", "sms", 1))
        self.assertFalse(new.checked)
        self.to_side.refresh_from_db(); incoming.refresh_from_db(); self.to_beside.refresh_from_db()
        self.assertEqual(self.to_side.lexeme_from_id, new.pk)
        self.assertEqual(incoming.lexeme_to_id, new.pk)
        self.assertEqual(self.to_beside.lexeme_from_id, self.source.pk, "what was not chosen stays")
        self.assertEqual(response.data["moved"], {"relations": 2})
        self.assertTrue(response.data["source_unapproved"])
        self.source.refresh_from_db()
        self.assertFalse(self.source.checked)
        self.assertEqual(self.to_side.changed_by, self.staff)

    def test_can_change_headword_and_pos_of_the_new_entry(self):
        response = self.split(self.source, lexeme="pӧla-2", pos="V", relations=[self.to_side.pk])
        self.assertEqual(response.status_code, 201, response.data)
        new = Lexeme.objects.get(pk=response.data["new"]["id"])
        self.assertEqual((new.lexeme, new.pos, new.homoId), ("pӧla-2", "V", 0))

    def test_relation_examples_travel_with_their_relation(self):
        src = RelationExample.objects.create(relation=self.to_side, language_id="sms", text="Pӧla.")
        tgt = RelationExample.objects.create(relation=self.to_side, language_id="fin", text="Puoli.")
        RelationExampleRelation.objects.create(example_from=src, example_to=tgt)
        response = self.split(self.source, relations=[self.to_side.pk])
        self.assertEqual(response.status_code, 201, response.data)
        self.to_side.refresh_from_db()
        self.assertEqual(self.to_side.relationexample_set.count(), 2)
        self.assertEqual(RelationExampleRelation.objects.count(), 1)

    def test_lexeme_examples_move_but_forms_stay(self):
        keep = Example.objects.create(lexeme=self.source, text="Keep.")
        move = Example.objects.create(lexeme=self.source, text="Move.")
        MiniParadigm.objects.create(lexeme=self.source, msd="Sg+Nom", wordform="pӧla")
        LexemeMetadata.objects.create(lexeme=self.source, type=LEXEME_TYPE, text="y")
        response = self.split(self.source, examples=[move.pk])
        self.assertEqual(response.status_code, 201, response.data)
        move.refresh_from_db(); keep.refresh_from_db()
        self.assertEqual(move.lexeme_id, response.data["new"]["id"])
        self.assertEqual(keep.lexeme_id, self.source.pk)
        self.assertEqual(self.source.miniparadigm_set.count(), 1)
        self.assertEqual(self.source.lexememetadata_set.count(), 1)

    def test_mirrored_relations_move_together_without_duplicates(self):
        other = self.lex("pieli", "sms", "N")
        self.rel(self.source, other, type=SYNONYM)          # saving also made other -> source
        forward = Relation.objects.get(lexeme_from=self.source, lexeme_to=other)
        response = self.split(self.source, relations=[forward.pk])
        self.assertEqual(response.status_code, 201, response.data)
        new_id = response.data["new"]["id"]
        pairs = sorted(
            Relation.objects.filter(type=SYNONYM).values_list("lexeme_from_id", "lexeme_to_id")
        )
        self.assertEqual(pairs, sorted([(new_id, other.pk), (other.pk, new_id)]))
        self.assertEqual(response.data["moved"], {"relations": 1, "mirror_relations": 1})

    def test_choosing_both_mirrored_rows_moves_each_once(self):
        other = self.lex("pieli", "sms", "N")
        self.rel(self.source, other, type=SYNONYM)
        ids = list(Relation.objects.filter(type=SYNONYM).values_list("pk", flat=True))
        response = self.split(self.source, relations=ids)
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(Relation.objects.filter(type=SYNONYM).count(), 2)
        self.assertEqual(response.data["moved"], {"relations": 2})

    def test_dry_run_reports_without_changing_anything(self):
        before = (Lexeme.objects.count(), Lexeme.history.count(), Relation.history.count())
        response = self.split(self.source, dry_run=True, relations=[self.to_side.pk])
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIsNone(response.data["new"]["id"])
        self.assertEqual(response.data["new"]["counts"]["relations_from"], 1)
        self.assertEqual(response.data["source"]["counts"]["relations_from"], 1)
        self.assertEqual(before, (Lexeme.objects.count(), Lexeme.history.count(), Relation.history.count()))
        self.to_side.refresh_from_db(); self.source.refresh_from_db()
        self.assertEqual(self.to_side.lexeme_from_id, self.source.pk)
        self.assertTrue(self.source.checked)

    def test_a_new_headword_alone_is_enough_when_nothing_needs_to_move(self):
        response = self.split(self.source, lexeme="pӧla2")
        self.assertEqual(response.status_code, 201, response.data)
        created = Lexeme.objects.get(pk=response.data["new"]["id"])
        self.assertEqual((created.lexeme, created.pos), ("pӧla2", self.source.pos))
        self.assertEqual(sum(response.data["moved"].values()), 0)

    def test_the_whole_entry_can_be_moved_and_says_so(self):
        response = self.split(self.source, relations=[self.to_side.pk, self.to_beside.pk])
        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(response.data["source"]["empty"])
        self.assertIn("Nothing is left", " ".join(response.data["notes"]))


class SplitGuardTests(SplitTestCase):
    def setUp(self):
        super().setUp()
        self.source = self.lex("pӧla", "sms", "N")
        self.target = self.lex("puoli", "fin", "N")
        self.relation = self.rel(self.source, self.target)

    def assertRefused(self, body, text, source=None):
        before = Lexeme.objects.count()
        response = self.split(source or self.source, **body)
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn(text, str(response.data))
        self.assertEqual(Lexeme.objects.count(), before, "nothing was created")
        self.relation.refresh_from_db()
        self.assertEqual(self.relation.lexeme_from_id, self.source.pk)

    def test_needs_something_to_move(self):
        self.assertRefused({}, "at least one")

    def test_refuses_foreign_and_missing_rows(self):
        stranger = self.rel(self.lex("a", "fin", "N"), self.lex("b", "fin", "N"), type=ETYMOLOGY)
        self.assertRefused({"relations": [stranger.pk]}, "does not belong")
        self.assertRefused({"relations": [99999]}, "does not exist")
        foreign_example = Example.objects.create(lexeme=self.target, text="x")
        self.assertRefused({"examples": [foreign_example.pk]}, "does not belong")

    def test_refuses_an_existing_homonym_slot(self):
        self.assertRefused(
            {"relations": [self.relation.pk], "homoId": 0, "lexeme": "pӧla", "pos": "N"}, "already is"
        )

    def test_refuses_a_missing_pos(self):
        blank = self.lex("nopos", "sms", "")
        rel = self.rel(blank, self.target)
        response = self.split(blank, relations=[rel.pk])
        self.assertEqual(response.status_code, 400)
        self.assertIn("part of speech", str(response.data))

    def test_staff_only(self):
        from django.contrib.auth.models import User
        from rest_framework.authtoken.models import Token

        reader = User.objects.create_user("reader")
        self.client.credentials(HTTP_AUTHORIZATION="Token " + Token.objects.create(user=reader).key)
        self.assertEqual(self.split(self.source, relations=[self.relation.pk]).status_code, 403)
