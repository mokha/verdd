from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from manageXML.constants import TRANSLATION
from manageXML.models import (
    Language,
    Lexeme,
    Relation,
    RelationExample,
    RelationExampleRelation,
)

PAIR = {
    "source": {"lexeme": "muõrr", "language": "sms", "pos": "N"},
    "target": {"lexeme": "puu", "language": "fin"},
    "examples": [
        {
            "source_text": "Muõrr lij nåkam.",
            "target_text": "Puu on sellainen.",
            "source": "https://example.org/page",
        }
    ],
}


class ApiTestCase(APITestCase):
    def setUp(self):
        for code, name in (("sms", "Skolt Sami"), ("fin", "Finnish"), ("nob", "Bokmål")):
            Language.objects.create(id=code, name=name)
        self.staff = User.objects.create_user("editor", is_staff=True)
        self.token = Token.objects.create(user=self.staff)
        self.client.credentials(HTTP_AUTHORIZATION="Token " + self.token.key)

    def make_lexeme(self, text, language, pos="N", **kwargs):
        return Lexeme.objects.create(
            lexeme=text, language_id=language, pos=pos, **kwargs
        )


class AccessTests(ApiTestCase):
    def test_token_required(self):
        self.client.credentials()
        self.assertEqual(self.client.get("/api/v1/me/").status_code, 401)

    def test_non_staff_refused(self):
        user = User.objects.create_user("reader")
        token = Token.objects.create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION="Token " + token.key)
        self.assertEqual(self.client.get("/api/v1/lexemes/").status_code, 403)

    def test_me(self):
        response = self.client.get("/api/v1/me/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["username"], "editor")

    def test_create_api_token_command(self):
        out = StringIO()
        call_command("create_api_token", "editor", "--reset", stdout=out)
        new_key = out.getvalue().strip()
        self.assertNotEqual(new_key, self.token.key)
        self.assertEqual(Token.objects.get(user=self.staff).key, new_key)


class PairTests(ApiTestCase):
    def test_pair_creates_everything_unchecked_and_attributed(self):
        response = self.client.post("/api/v1/pairs/", PAIR, format="json")
        self.assertEqual(response.status_code, 201, response.data)

        source = Lexeme.objects.get(lexeme="muõrr")
        target = Lexeme.objects.get(lexeme="puu")
        self.assertEqual(target.pos, "N")  # defaults to the source's POS
        self.assertEqual(target.language_id, "fin")
        for lexeme in (source, target):
            self.assertFalse(lexeme.checked)
            self.assertEqual(lexeme.changed_by, self.staff)
            self.assertEqual(lexeme.history.first().history_user, self.staff)

        relation = Relation.objects.get()
        self.assertEqual(
            (relation.lexeme_from, relation.lexeme_to, relation.type),
            (source, target, TRANSLATION),
        )
        self.assertFalse(relation.checked)

        src_ex = RelationExample.objects.get(language_id="sms")
        tgt_ex = RelationExample.objects.get(language_id="fin")
        self.assertEqual(src_ex.source, "https://example.org/page")
        self.assertEqual(src_ex.changed_by, self.staff)
        link = RelationExampleRelation.objects.get()
        self.assertEqual((link.example_from, link.example_to), (src_ex, tgt_ex))
        self.assertEqual(link.history.first().history_user, self.staff)

        self.assertEqual(response.data["source"]["id"], source.pk)
        self.assertEqual(response.data["examples"][0]["link"], link.pk)

    def test_pair_is_idempotent(self):
        self.client.post("/api/v1/pairs/", PAIR, format="json")
        counts = (Lexeme.objects.count(), Relation.objects.count(),
                  RelationExample.objects.count(), RelationExampleRelation.objects.count())
        response = self.client.post("/api/v1/pairs/", PAIR, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["created"])
        self.assertEqual(
            counts,
            (Lexeme.objects.count(), Relation.objects.count(),
             RelationExample.objects.count(), RelationExampleRelation.objects.count()),
        )

    def test_resend_does_not_clobber_approval(self):
        self.client.post("/api/v1/pairs/", PAIR, format="json")
        Lexeme.objects.update(checked=True)
        Relation.objects.update(checked=True)
        self.client.post("/api/v1/pairs/", PAIR, format="json")
        self.assertFalse(Lexeme.objects.filter(checked=False).exists())
        self.assertFalse(Relation.objects.filter(checked=False).exists())

    def test_single_existing_homonym_is_reused(self):
        existing = self.make_lexeme("muõrr", "sms", homoId=1)
        response = self.client.post("/api/v1/pairs/", PAIR, format="json")
        self.assertEqual(response.data["source"]["id"], existing.pk)
        self.assertFalse(response.data["source"]["created"])

    def test_ambiguous_homonyms_need_homoid(self):
        self.make_lexeme("muõrr", "sms", homoId=0)
        second = self.make_lexeme("muõrr", "sms", homoId=1)
        response = self.client.post("/api/v1/pairs/", PAIR, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("source", response.data)
        self.assertEqual(Relation.objects.count(), 0)

        explicit = {**PAIR, "source": {**PAIR["source"], "homoId": 1}}
        response = self.client.post("/api/v1/pairs/", explicit, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["source"]["id"], second.pk)

    def test_invalid_pairs_are_rejected_without_side_effects(self):
        cases = {
            "unknown language": {**PAIR, "target": {"lexeme": "puu", "language": "xxx"}},
            "same language": {**PAIR, "target": {"lexeme": "puu", "language": "sms"}},
            "text too long": {
                **PAIR,
                "examples": [{"source_text": "x" * 251}],
            },
        }
        for name, payload in cases.items():
            response = self.client.post("/api/v1/pairs/", payload, format="json")
            self.assertEqual(response.status_code, 400, name)
        self.assertEqual(Lexeme.objects.count(), 0)

    def test_example_without_translation_has_no_link(self):
        payload = {**PAIR, "examples": [{"source_text": "Muõrr."}]}
        response = self.client.post("/api/v1/pairs/", payload, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(RelationExample.objects.count(), 1)
        self.assertEqual(RelationExampleRelation.objects.count(), 0)

    def test_bulk_reports_each_pair(self):
        bad = {"source": {"lexeme": "a", "language": "xxx", "pos": "N"}, "target": {}}
        response = self.client.post(
            "/api/v1/pairs/bulk/", {"pairs": [PAIR, bad]}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        ok, failed = response.data["results"]
        self.assertTrue(ok["ok"])
        self.assertFalse(failed["ok"])
        self.assertEqual(Relation.objects.count(), 1)

    def test_bulk_rejects_non_list(self):
        response = self.client.post("/api/v1/pairs/bulk/", {"pairs": PAIR}, format="json")
        self.assertEqual(response.status_code, 400)


class EditTests(ApiTestCase):
    def test_editing_approved_lexeme_unchecks_it(self):
        lexeme = self.make_lexeme("muõrr", "sms", checked=True)
        response = self.client.patch(
            f"/api/v1/lexemes/{lexeme.pk}/", {"notes": "tree"}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.data)
        lexeme.refresh_from_db()
        self.assertEqual(lexeme.notes, "tree")
        self.assertFalse(lexeme.checked)
        self.assertEqual(lexeme.history.first().history_user, self.staff)

    def test_unchanged_values_keep_approval(self):
        lexeme = self.make_lexeme("muõrr", "sms", notes="tree", checked=True)
        self.client.patch(
            f"/api/v1/lexemes/{lexeme.pk}/", {"notes": "tree"}, format="json"
        )
        lexeme.refresh_from_db()
        self.assertTrue(lexeme.checked)

    def test_checked_is_read_only(self):
        lexeme = self.make_lexeme("muõrr", "sms")
        self.client.patch(
            f"/api/v1/lexemes/{lexeme.pk}/", {"checked": True}, format="json"
        )
        lexeme.refresh_from_db()
        self.assertFalse(lexeme.checked)

    def test_lexeme_cannot_be_deleted(self):
        lexeme = self.make_lexeme("muõrr", "sms")
        response = self.client.delete(f"/api/v1/lexemes/{lexeme.pk}/")
        self.assertEqual(response.status_code, 405)
        self.assertTrue(Lexeme.objects.filter(pk=lexeme.pk).exists())

    def test_duplicate_lexeme_is_rejected(self):
        self.make_lexeme("muõrr", "sms")
        payload = {"lexeme": "muõrr", "language": "sms", "pos": "N"}
        response = self.client.post("/api/v1/lexemes/", payload, format="json")
        self.assertEqual(response.status_code, 400)

    def test_relation_delete_records_who_deleted(self):
        a, b = self.make_lexeme("muõrr", "sms"), self.make_lexeme("puu", "fin")
        relation = Relation.objects.create(lexeme_from=a, lexeme_to=b, changed_by=None)
        response = self.client.delete(f"/api/v1/relations/{relation.pk}/")
        self.assertEqual(response.status_code, 204)
        deleted = Relation.history.filter(history_type="-").get()
        self.assertEqual(deleted.history_user, self.staff)

    def test_relation_example_language_must_belong_to_relation(self):
        a, b = self.make_lexeme("muõrr", "sms"), self.make_lexeme("puu", "fin")
        relation = Relation.objects.create(lexeme_from=a, lexeme_to=b)
        payload = {"relation": relation.pk, "language": "nob", "text": "Tre."}
        response = self.client.post("/api/v1/relation-examples/", payload, format="json")
        self.assertEqual(response.status_code, 400)
        payload["language"] = "fin"
        response = self.client.post("/api/v1/relation-examples/", payload, format="json")
        self.assertEqual(response.status_code, 201, response.data)

    def test_links_must_stay_within_one_relation(self):
        a, b = self.make_lexeme("muõrr", "sms"), self.make_lexeme("puu", "fin")
        c = self.make_lexeme("kuusk", "sms")
        r1 = Relation.objects.create(lexeme_from=a, lexeme_to=b)
        r2 = Relation.objects.create(lexeme_from=c, lexeme_to=b)
        e1 = RelationExample.objects.create(relation=r1, language_id="sms", text="x")
        e2 = RelationExample.objects.create(relation=r2, language_id="fin", text="y")
        payload = {"example_from": e1.pk, "example_to": e2.pk}
        response = self.client.post(
            "/api/v1/relation-example-links/", payload, format="json"
        )
        self.assertEqual(response.status_code, 400)


class ReadTests(ApiTestCase):
    def test_lexeme_filters(self):
        self.make_lexeme("muõrr", "sms")
        self.make_lexeme("puu", "fin")
        response = self.client.get("/api/v1/lexemes/", {"language": "sms", "lexeme": "muõrr"})
        self.assertEqual(response.data["count"], 1)
        response = self.client.get("/api/v1/lexemes/", {"q": "uu"})
        self.assertEqual([r["lexeme"] for r in response.data["results"]], ["puu"])

    def test_relations_expose_examples_and_links(self):
        self.client.post("/api/v1/pairs/", PAIR, format="json")
        source = Lexeme.objects.get(lexeme="muõrr")
        response = self.client.get(
            "/api/v1/relations/", {"lexeme_from": source.pk, "type": TRANSLATION}
        )
        self.assertEqual(response.data["count"], 1)
        examples = response.data["results"][0]["examples"]
        self.assertEqual({e["language"] for e in examples}, {"sms", "fin"})
        self.assertEqual(examples[0]["linked_to"], [examples[1]["id"]])

    def test_languages(self):
        response = self.client.get("/api/v1/languages/")
        self.assertEqual({r["id"] for r in response.data}, {"sms", "fin", "nob"})
