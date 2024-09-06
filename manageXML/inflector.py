from uralicNLP import uralicApi
from manageXML.models import Lexeme
from django.core.cache import cache  # Cache mini paradigms per language


# Ensure the uralicNLP model is installed
def ensure_model_is_installed(language):
    if not uralicApi.is_language_installed(language):
        uralicApi.download(language)


def load_mini_paradigms(language):
    cache_key = f"language_paradigms_{language}"
    paradigms = cache.get(cache_key)
    if not paradigms:
        paradigms = language.paradigms.filter(mini=True).all()
        cache.set(cache_key, paradigms, timeout=3600)  # Cache for 1 hour
    return paradigms


def generate_inflections(lexeme: Lexeme, dictionary_forms=False) -> dict:

    # Use uralicNLP to generate inflected forms
    ensure_model_is_installed(lexeme.language.id)

    paradigms = load_mini_paradigms(lexeme.language)

    generated_forms = {}
    for paradigm in paradigms:
        if lexeme.pos == paradigm.pos:
            _generation_forms = uralicApi.generate(
                f"{lexeme.lexeme}+{paradigm.form}",
                lexeme.language.id,
                dictionary_forms=dictionary_forms,
            )

            generated_forms[paradigm.form] = [
                _generated_form[0] for _generated_form in _generation_forms
            ]
    print(generated_forms)
    return generated_forms
