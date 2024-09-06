import re
from django import template
from manageXML.constants import SPECIFICATION
from collections import defaultdict
from manageXML.inflector import generate_inflections

register = template.Library()


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

        translation_text = translation.lexeme
        pos = "" if translation.pos == lexeme_from.pos else translation.pos

        generated_forms = generate_inflections(translation)
        inflections = [_m for m in generated_forms.values() for _m in m]

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
