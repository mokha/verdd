from django.test import TestCase

from .forms import LexemeCreateForm
from .models import Language


class LexemeCreateLanguageTests(TestCase):
    def setUp(self):
        Language.objects.create(id="myv", name="Erzya")
        Language.objects.create(id="sms", name="Skolt Sami")

    def form(self, language):
        return LexemeCreateForm({"lexeme": "кал", "language": language, "pos": "N", "homoId": 0})

    def test_a_typed_code_selects_the_language(self):
        form = self.form("myv")
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["language"].pk, "myv")

    def test_case_and_surrounding_spaces_do_not_matter(self):
        for typed in ("MYV", " Myv ", "mYv\n"):
            form = self.form(typed)
            self.assertTrue(form.is_valid(), (typed, form.errors))
            self.assertEqual(form.cleaned_data["language"].pk, "myv")

    def test_a_suggestion_with_its_name_and_the_plain_name_also_work(self):
        self.assertEqual(self.form("Skolt Sami (sms)").save(commit=False).language_id, "sms")
        self.assertEqual(self.form("erzya").save(commit=False).language_id, "myv")

    def test_an_unknown_code_is_refused_with_a_hint(self):
        form = self.form("xyz")
        self.assertFalse(form.is_valid())
        self.assertIn("three-letter ISO 639 code", form.errors["language"][0])

    def test_empty_is_refused(self):
        self.assertFalse(self.form("").is_valid())

    def test_the_page_offers_a_text_box_with_suggestions_not_a_select(self):
        html = str(self.form("")["language"])
        self.assertIn('<input type="text"', html)
        self.assertNotIn("<select", html)
        self.assertIn('list="id_language_codes"', html)
        self.assertIn('<datalist id="id_language_codes">', html)
        self.assertIn('<option value="myv">Erzya</option>', html)
        self.assertIn('autocapitalize="none"', html)

    def test_a_refused_entry_stays_in_the_box(self):
        self.assertIn('value="xyz"', str(self.form("xyz")["language"]))


class LexemeCreatePageTests(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User

        Language.objects.create(id="myv", name="Erzya")
        self.client.force_login(User.objects.create_user("editor", is_staff=True))

    def test_the_page_renders_the_code_box(self):
        response = self.client.get("/lexeme/add")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'list="id_language_codes"')
        self.assertContains(response, '<option value="myv">Erzya</option>')

    def test_a_lexeme_is_created_from_a_typed_code(self):
        from .models import Lexeme

        response = self.client.post("/lexeme/add", {"lexeme": "кал", "language": "MYV", "pos": "N", "homoId": 0})
        self.assertEqual(response.status_code, 302, getattr(response, "context", None) and response.context["form"].errors)
        self.assertEqual(Lexeme.objects.get(lexeme="кал").language_id, "myv")
