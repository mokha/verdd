import re
from django import template
from manageXML.constants import SPECIFICATION
from collections import defaultdict
from uralicNLP import uralicApi
from django.core.cache import cache  # Cache mini paradigms per language

register = template.Library()


# Ensure the uralicNLP model is installed
def ensure_model_is_installed(language):
    if not uralicApi.is_language_installed(language):
        uralicApi.download(language)


@register.filter(name="tex_escape")
def tex_escape(text):
    """
    Escapes LaTeX special characters in the provided text.
    """
    conv = {
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\\textasciitilde{}",
        "^": r"\\^{}",
        "\\": r"\\textbackslash{}",
        "<": r"\\textless{}",
        ">": r"\\textgreater{}",
    }

    regex = re.compile(
        "|".join(
            re.escape(key) for key in sorted(conv.keys(), key=lambda item: -len(item))
        )
    )
    return regex.sub(lambda match: conv[match.group()], text)


def load_mini_paradigms(language):
    cache_key = f"language_paradigms_{language}"
    paradigms = cache.get(cache_key)
    if not paradigms:
        paradigms = language.paradigms.filter(mini=True).all()
        cache.set(cache_key, paradigms, timeout=3600)  # Cache for 1 hour
    return paradigms


@register.simple_tag(name="dictionary_entry")
def dictionary_entry(grouped_relation):
    """
    Generates a dictionary entry LaTeX string for the given lexeme and its relations.
    """

    lexeme_from_id, relations = grouped_relation
    relations = list(relations)
    lexeme_from = relations[0].lexeme_from

    dictionary_entry_text = []

    # Entry for the lexeme from
    entry_content = (
        lexeme_from.lexeme,
        lexeme_from.pos,
        lexeme_from.specification,
    )
    entry_content = tuple([tex_escape(c) for c in entry_content])
    dictionary_entry_text.append(r"\entry{%s}{%s}{%s}" % entry_content)

    # Sort relations for processing
    relations = list(
        sorted(
            relations,
            key=lambda r: (
                r.relationmetadata_set.all().count() != 0,
                r.lexeme_to.lexeme_lang,
            ),
        )
    )

    for r in relations:
        translation = r.lexeme_to

        paradigms = load_mini_paradigms(translation.language)

        translation_text = translation.lexeme
        pos = "" if translation.pos == lexeme_from.pos else translation.pos

        # Use uralicNLP to generate inflected forms
        ensure_model_is_installed(translation.language.id)

        generated_forms = []
        for paradigm in paradigms:
            if translation.pos == paradigm.pos:
                _generation_forms = uralicApi.generate(
                    f"{translation.lexeme}+{translation.pos}+{paradigm.form}",
                    translation.language.id,
                    dictionary_forms=True,
                )
                generated_forms.extend(_generation_forms)

        inflections = (
            [form[0].split("@")[0] for form in generated_forms if form]
            if generated_forms
            else []
        )

        MP_forms = translation.miniparadigm_set.all()
        existing_MP_forms = defaultdict(list)
        for form in MP_forms:
            existing_MP_forms[form.msd].append(form.wordform)

        for form in existing_MP_forms:
            if existing_MP_forms[form]:
                inflections.extend(existing_MP_forms[form])

        source_specification = (
            r.relationmetadata_set.values_list("text", flat=True)
            .filter(type=SPECIFICATION, language=lexeme_from.language)
            .order_by("text")
            .all()
        )
        target_specification = (
            r.relationmetadata_set.values_list("text", flat=True)
            .filter(type=SPECIFICATION, language=translation.language)
            .order_by("text")
            .all()
        )
        source_example = (
            r.relationexample_set.values_list("text", flat=True)
            .filter(language=lexeme_from.language)
            .order_by("text")
            .all()
        )
        target_example = (
            r.relationexample_set.values_list("text", flat=True)
            .filter(language=translation.language)
            .order_by("text")
            .all()
        )

        content = (
            translation_text,
            translation.specification,
            pos,
            ", ".join(inflections),
            ", ".join(source_specification),
            ", ".join(target_specification),
            ", ".join(source_example),
            ", ".join(target_example),
            "",
        )
        content = tuple([tex_escape(c) for c in content])
        dictionary_entry_text.append(
            "\\translation{%s}{%s}{%s}{%s}{%s}{%s}{%s}{%s}{%s}" % content
        )

    return "\n".join(dictionary_entry_text)


@register.simple_tag(name="dictionary_chapter")
def dictionary_chapter(key):
    """
    Generate a LaTeX chapter for the dictionary entry.
    """
    return r"\\includedictionary{%s}{chapter-%s.tex}" % (key, key)
