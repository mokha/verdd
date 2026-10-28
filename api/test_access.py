from django.contrib.auth.models import User
from django.core.cache import cache
from rest_framework.authtoken.models import Token

from manageXML.constants import TRANSLATION
from manageXML.models import Example, Language, LanguageAccess, Lexeme, Relation, RelationExample

from .test_merge import MergeTestCase


class AccessTestCase(MergeTestCase):
    """The setUp language set (sms, fin, nob) plus myv; `limited` may work on sms <-> fin only."""

    def setUp(self):
        super().setUp()
        Language.objects.create(id="myv", name="Erzya")
        self.limited = User.objects.create_user("helper", email="helper@example.org", password="pw-helper", is_staff=True)
        self.limited_token = Token.objects.create(user=self.limited)
        LanguageAccess.objects.create(user=self.limited, language_a_id="sms", language_b_id="fin")

        self.sms = self.lex("pӧla", "sms", "N")
        self.fin = self.lex("puoli", "fin", "N")
        self.myv = self.lex("пель", "myv", "N")
        self.sms_fin = self.rel(self.sms, self.fin)
        self.sms_myv = self.rel(self.sms, self.myv)
        self.as_limited()

    def as_limited(self):
        self.client.credentials(HTTP_AUTHORIZATION="Token " + self.limited_token.key)

    def as_editor(self):
        self.client.credentials(HTTP_AUTHORIZATION="Token " + self.token.key)

    def ids(self, url, **params):
        return {row["id"] for row in self.client.get(url, params).data["results"]}


class ScopeTests(AccessTestCase):
    def test_pairs_are_stored_in_one_order(self):
        row = LanguageAccess.objects.create(user=self.staff, language_a_id="sms", language_b_id="fin")
        self.assertEqual((row.language_a_id, row.language_b_id), ("fin", "sms"))

    def test_a_staff_user_without_rows_and_a_superuser_are_not_limited(self):
        self.as_editor()
        self.assertEqual(self.ids("/api/v1/lexemes/"), {self.sms.pk, self.fin.pk, self.myv.pk})
        self.assertEqual(self.client.get("/api/v1/me/").data["access"], {"restricted": False, "pairs": []})
        boss = User.objects.create_user("boss", is_superuser=True, is_staff=True)
        LanguageAccess.objects.create(user=boss, language_a_id="sms", language_b_id="fin")
        token = Token.objects.create(user=boss)
        self.client.credentials(HTTP_AUTHORIZATION="Token " + token.key)
        self.assertIn(self.myv.pk, self.ids("/api/v1/lexemes/"))

    def test_me_and_languages_show_what_is_allowed(self):
        self.assertEqual(self.client.get("/api/v1/me/").data["access"], {"restricted": True, "pairs": [["fin", "sms"]]})
        self.assertEqual([l["id"] for l in self.client.get("/api/v1/languages/").data], ["fin", "sms"])

    def test_entries_of_other_languages_are_invisible(self):
        self.assertEqual(self.ids("/api/v1/lexemes/"), {self.sms.pk, self.fin.pk})
        self.assertEqual(self.client.get(f"/api/v1/lexemes/{self.myv.pk}/").status_code, 404)
        self.assertEqual(self.client.patch(f"/api/v1/lexemes/{self.myv.pk}/", {"notes": "x"}, format="json").status_code, 404)
        self.assertEqual(self.client.get("/api/v1/lexemes/", {"language": "myv"}).data["count"], 0)

    def test_entries_can_only_be_created_in_allowed_languages(self):
        ok = self.client.post("/api/v1/lexemes/", {"lexeme": "uusi", "language": "fin", "pos": "A"}, format="json")
        self.assertEqual(ok.status_code, 201, ok.data)
        refused = self.client.post("/api/v1/lexemes/", {"lexeme": "ший", "language": "myv", "pos": "A"}, format="json")
        self.assertEqual(refused.status_code, 400)
        self.assertIn("language", refused.data)
        move = self.client.patch(f"/api/v1/lexemes/{self.sms.pk}/", {"language": "myv"}, format="json")
        self.assertEqual(move.status_code, 400, "an entry cannot be moved out of the allowed languages")

    def test_translations_only_of_allowed_pairs(self):
        self.assertEqual(self.ids("/api/v1/relations/"), {self.sms_fin.pk})
        self.assertEqual(self.client.get(f"/api/v1/relations/{self.sms_myv.pk}/").status_code, 404)
        self.assertEqual(self.client.delete(f"/api/v1/relations/{self.sms_myv.pk}/").status_code, 404)
        other = self.lex("kala", "fin", "N")
        ok = self.client.post("/api/v1/relations/", {"lexeme_from": self.sms.pk, "lexeme_to": other.pk, "type": TRANSLATION}, format="json")
        self.assertEqual(ok.status_code, 201, ok.data)
        refused = self.client.post("/api/v1/relations/", {"lexeme_from": self.fin.pk, "lexeme_to": self.myv.pk, "type": TRANSLATION}, format="json")
        self.assertEqual(refused.status_code, 400, "fin entries may not be linked to myv ones")
        # the other pair the user has no access to, though sms is allowed in another pair
        self.assertEqual(self.client.post("/api/v1/relations/", {"lexeme_from": self.sms.pk, "lexeme_to": self.myv.pk, "type": TRANSLATION}, format="json").status_code, 400)

    def test_examples_follow_the_entry_or_relation(self):
        allowed_ex = Example.objects.create(lexeme=self.sms, text="a")
        Example.objects.create(lexeme=self.myv, text="b")
        self.assertEqual(self.ids("/api/v1/examples/"), {allowed_ex.pk})
        self.assertEqual(self.client.post("/api/v1/examples/", {"lexeme": self.myv.pk, "text": "x"}, format="json").status_code, 400)
        good = RelationExample.objects.create(relation=self.sms_fin, language_id="sms", text="r1")
        RelationExample.objects.create(relation=self.sms_myv, language_id="sms", text="r2")
        self.assertEqual(self.ids("/api/v1/relation-examples/"), {good.pk})
        bad = self.client.post("/api/v1/relation-examples/", {"relation": self.sms_myv.pk, "language": "sms", "text": "x"}, format="json")
        self.assertEqual(bad.status_code, 400)

    def test_the_send_endpoints_respect_the_pairs(self):
        def pair(target_lang):
            return {"source": {"lexeme": "pӧla", "language": "sms", "pos": "N"}, "target": {"lexeme": "x", "language": target_lang, "pos": "N"}}
        self.assertEqual(self.client.post("/api/v1/pairs/", pair("fin"), format="json").status_code, 201)
        refused = self.client.post("/api/v1/pairs/", pair("myv"), format="json")
        self.assertEqual(refused.status_code, 400)
        bulk = self.client.post("/api/v1/pairs/bulk/", {"pairs": [pair("fin"), pair("myv")]}, format="json").data["results"]
        self.assertEqual([r["ok"] for r in bulk], [True, False])

    def test_summaries_hide_translations_of_other_pairs(self):
        self.lex("pӧla", "sms", "UND", homo=2)
        und = Lexeme.objects.get(lexeme="pӧla", pos="UND")
        self.rel(und, self.myv)
        group = self.client.get("/api/v1/lexemes/merge-candidates/", {"language": "sms"}).data["results"][0]
        self.assertEqual(group["undetermined"]["translations"], [])
        self.assertEqual(group["candidates"][0]["translations"], ["puoli"])
        self.as_editor()
        group = self.client.get("/api/v1/lexemes/merge-candidates/", {"language": "sms"}).data["results"][0]
        self.assertEqual(group["undetermined"]["translations"], ["пель"])

    def test_candidate_lists_are_limited_to_allowed_languages(self):
        self.assertEqual(self.client.get("/api/v1/lexemes/merge-candidates/", {"language": "myv"}).status_code, 403)
        self.assertEqual(self.client.get("/api/v1/lexemes/merge-candidates/", {"language": "myv", "mode": "capitalised-noun"}).status_code, 403)
        self.lex("пель", "myv", "UND")
        self.assertEqual(self.client.get("/api/v1/lexemes/merge-candidates/").data["count"], 0)
        self.as_editor()
        self.assertEqual(self.client.get("/api/v1/lexemes/merge-candidates/").data["count"], 1)

    def test_merge_and_split_refuse_what_would_move_translations_out_of_reach(self):
        twin = self.lex("pӧla", "sms", "N", homo=3)
        refused = self.client.post(f"/api/v1/lexemes/{self.sms.pk}/merge/", {"into": twin.pk, "dry_run": True}, format="json")
        self.assertEqual(refused.status_code, 400)
        self.assertIn("do not have access", str(refused.data))
        split = self.client.post(f"/api/v1/lexemes/{self.sms.pk}/split/", {"relations": [self.sms_myv.pk], "dry_run": True}, format="json")
        self.assertEqual(split.status_code, 400)
        okay = self.client.post(f"/api/v1/lexemes/{self.sms.pk}/split/", {"relations": [self.sms_fin.pk], "dry_run": True}, format="json")
        self.assertEqual(okay.status_code, 200, okay.data)
        # an entry whose translations are all in allowed pairs merges normally
        clean = self.lex("kuõʹll", "sms", "N")
        keeper = self.lex("kuõʹll", "sms", "N", homo=1)
        self.assertEqual(self.client.post(f"/api/v1/lexemes/{clean.pk}/merge/", {"into": keeper.pk}, format="json").status_code, 200)

    def test_merging_into_an_entry_of_another_language_is_refused(self):
        refused = self.client.post(f"/api/v1/lexemes/{self.fin.pk}/merge/", {"into": self.myv.pk, "dry_run": True}, format="json")
        self.assertEqual(refused.status_code, 400)

    def test_a_single_language_row_allows_that_language_alone(self):
        LanguageAccess.objects.filter(user=self.limited).delete()
        LanguageAccess.objects.create(user=self.limited, language_a_id="myv", language_b_id="myv")
        self.assertEqual(self.ids("/api/v1/lexemes/"), {self.myv.pk})
        self.assertEqual(self.ids("/api/v1/relations/"), set())
        mono = self.rel(self.myv, self.lex("пелькс", "myv", "N"), type=TRANSLATION)
        self.assertEqual(self.ids("/api/v1/relations/"), {mono.pk})


class LoginTests(AccessTestCase):
    URL = "/api/v1/auth/login/"

    def setUp(self):
        super().setUp()
        cache.clear()
        self.client.credentials()

    def login(self, username="helper", password="pw-helper"):
        return self.client.post(self.URL, {"username": username, "password": password}, format="json")

    def test_a_staff_member_signs_in_with_username_or_email(self):
        for who in ("helper", "helper@example.org", "HELPER@example.org"):
            response = self.login(who)
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(response.data["token"], self.limited_token.key)
            self.assertEqual(response.data["access"], {"restricted": True, "pairs": [["fin", "sms"]]})

    def test_a_first_sign_in_creates_the_token(self):
        User.objects.create_user("new", password="pw-new", is_staff=True)
        response = self.login("new", "pw-new")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Token.objects.get(user__username="new").key, response.data["token"])

    def test_wrong_credentials_and_missing_fields(self):
        self.assertEqual(self.login(password="nope").status_code, 400)
        self.assertEqual(self.login("nobody").status_code, 400)
        self.assertEqual(self.login(password="").status_code, 400)
        self.assertNotIn("token", self.login(password="nope").data)

    def test_a_non_staff_account_cannot_use_the_workbench(self):
        User.objects.create_user("reader", password="pw-reader")
        self.assertEqual(self.login("reader", "pw-reader").status_code, 403)
        self.assertFalse(Token.objects.filter(user__username="reader").exists())

    def test_an_inactive_account_cannot_sign_in(self):
        self.limited.is_active = False
        self.limited.save()
        self.assertEqual(self.login().status_code, 400)

    def test_a_stale_token_in_the_header_does_not_block_sign_in(self):
        self.client.credentials(HTTP_AUTHORIZATION="Token stale")
        self.assertEqual(self.login().status_code, 200)

    def test_sign_in_attempts_are_throttled(self):
        statuses = [self.login(password="nope").status_code for _ in range(12)]
        self.assertEqual(statuses[:10], [400] * 10)
        self.assertEqual(statuses[10:], [429, 429])
        cache.clear()
