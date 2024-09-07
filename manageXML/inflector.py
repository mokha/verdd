import threading

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
    if paradigms is None:
        paradigms = language.paradigms.filter(mini=True).all()
        cache.set(cache_key, paradigms, timeout=3600)  # Cache for 1 hour
    return paradigms


def generate_using_uralicNLP(query, language):
    cache_key = f"language_has_dictionary_forms_{language}"
    language_has_dictionary_forms = cache.get(cache_key)

    if language_has_dictionary_forms is None:
        try:
            # Attempt to generate with dictionary_forms=True
            uralicApi.generate(query, language, dictionary_forms=True)
            language_has_dictionary_forms = True
        except Exception:
            # If generating with dictionary_forms=True fails, assume it is not supported
            language_has_dictionary_forms = False
        cache.set(
            cache_key, language_has_dictionary_forms, timeout=3600
        )  # Cache for 1 hour

    try:
        forms = uralicApi.generate(
            query, language, dictionary_forms=language_has_dictionary_forms
        )
        return forms
    except Exception as e:
        # Handle or log the error as needed
        print(f"Error generating forms: {e}")
    return []


def _thread_wrapper(result_container, query, language):
    try:
        result = generate_using_uralicNLP(query, language)
        result_container.append(result)
    except Exception:
        result_container.append([])


def _call_uralicNLP_with_timeout(query, language, timeout=1):
    result_container = []
    thread = threading.Thread(
        target=_thread_wrapper, args=(result_container, query, language)
    )
    thread.start()
    thread.join(timeout=timeout)

    if thread.is_alive():
        print(
            "Timeout occurred while generating forms for query:",
            query,
            "language:",
            language,
        )
        thread.join()
        return []
    else:
        return result_container[0] if result_container else []


def generate_inflections(lexeme: Lexeme) -> dict:
    paradigms = load_mini_paradigms(lexeme.language)

    if not paradigms:
        return {}

    ensure_model_is_installed(lexeme.language.id)

    homonyms = Lexeme.objects.filter(
        lexeme=lexeme.lexeme, language=lexeme.language, pos=lexeme.pos
    ).count()

    query = lexeme.lexeme

    if homonyms > 1:
        query += f"+Hom{lexeme.homoId + 1}"

    generated_forms = {}
    for paradigm in paradigms:
        if lexeme.pos == paradigm.pos:
            query_with_paradigm = f"{query}+{paradigm.form}"
            _generation_forms = _call_uralicNLP_with_timeout(
                query_with_paradigm, lexeme.language.id
            )
            generated_forms[paradigm.form] = [
                _generated_form[0] for _generated_form in _generation_forms
            ]
    return generated_forms
