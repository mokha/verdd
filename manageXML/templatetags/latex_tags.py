import re
from django import template
from manageXML.constants import SPECIFICATION
from manageXML.inflector import Inflector

register = template.Library()
_inflector = Inflector()


@register.filter(name='tex_escape')
def tex_escape(text):
    """
        :param text: a plain text message
        :return: the message escaped to appear correctly in LaTeX
    """
    conv = {
        '&': r'\&',
        '%': r'\%',
        '$': r'\$',
        '#': r'\#',
        '_': r'\_',
        '{': r'\{',
        '}': r'\}',
        '~': r'\textasciitilde{}',
        '^': r'\^{}',
        '\\': r'\textbackslash{}',
        '<': r'\textless{}',
        '>': r'\textgreater{}',
    }

    regex = re.compile('|'.join(re.escape(key) for key in sorted(conv.keys(), key=lambda item: - len(item))))
    return regex.sub(lambda match: conv[match.group()], text)


@register.simple_tag(name='dictionary_entry')
def dictionary_entry(grouped_relation):
    '''

    :param grouped_relation: Lexeme ID with all Relation objects linked to it
    :return: A latex string to represent the relation as an entry in the dictionary
    '''

    lexeme_from_id, relations = grouped_relation
    relations = list(relations)
    lexeme_from = relations[0].lexeme_from

    dictionary_entry_text = []

    entry_content = (lexeme_from.lexeme, lexeme_from.pos, lexeme_from.specification,)
    entry_content = tuple([tex_escape(c) for c in entry_content])
    dictionary_entry_text.append(
        "\entry{%s}{%s}{%s}" % entry_content
    )

    inflection_table = {
        'V': ['V+Ind+Prs+ConNeg', 'V+Ind+Prs+Sg3', 'V+Ind+Prt+Sg1', 'V+Ind+Prt+Sg3'],
        'N': ['N+Sg+Loc', 'N+Sg+Ill', 'N+Pl+Gen'],
        'A': [],
    }
    relations = list(sorted(relations, key=lambda r: r.lexeme_to.lexeme_lang))
    for r in relations:
        translation = r.lexeme_to
        pos = '' if translation.pos == lexeme_from.pos else translation.pos

        # LaTeX escape the content
        inflections = []
        MP_forms = translation.miniparadigm_set.all()
        existing_MP_forms = {form.msd: form.wordform for form in MP_forms}
        generated_MP_forms = _inflector.generate(translation.language, translation.lexeme, translation.pos)
        if translation.pos in inflection_table:
            for inflection_form in inflection_table[translation.pos]:
                if inflection_form in existing_MP_forms:
                    inflections.append(existing_MP_forms[inflection_form])
                elif inflection_form in generated_MP_forms:
                    inflections.append(generated_MP_forms[inflection_form])

        source_specification = r.relationmetadata_set.values_list('text', flat=True) \
            .filter(type=SPECIFICATION, language=lexeme_from.language) \
            .order_by('text').all()
        target_specification = r.relationmetadata_set.values_list('text', flat=True) \
            .filter(type=SPECIFICATION, language=translation.language) \
            .order_by('text').all()
        source_example = r.relationexample_set.values_list('text', flat=True) \
            .filter(language=lexeme_from.language).order_by('text').all()
        target_example = r.relationexample_set.values_list('text', flat=True) \
            .filter(language=translation.language).order_by('text').all()

        content = (translation.lexeme,
                   pos,
                   ", ".join(inflections),
                   ", ".join(source_specification),
                   ", ".join(target_specification),
                   ", ".join(source_example),
                   ", ".join(target_example),
                   ""
                   )
        content = tuple([tex_escape(c) for c in content])
        dictionary_entry_text.append(
            "\\translation{%s}{%s}{%s}{%s}{%s}{%s}{%s}{%s}" % content
        )

    return "\n".join(dictionary_entry_text)


@register.simple_tag(name='dictionary_chapter')
def dictionary_chapter(key):
    return "\includedictionary{%s}{chapter-%s.tex}" % (key, key,)
