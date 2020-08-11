import re
from django import template
from manageXML.constants import SPECIFICATION
from manageXML.inflector import Inflector
from collections import defaultdict
from django.conf import settings
import os
import hfst
from uralicNLP import uralicApi
import csv
from manageXML.utils import *

register = template.Library()
_inflector = Inflector()
transducer_path = os.path.join(settings.BASE_DIR, '../local/transducers/generator-dict-gt-norm.hfstol')
if os.path.exists(transducer_path) and os.path.isfile(transducer_path):
    input_stream = hfst.HfstInputStream(transducer_path)
    synthetiser = input_stream.read()


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


nti_ids = read_first_ids_from(os.path.join(settings.BASE_DIR, '../local/data/not-to-inflect.csv'))


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
        'A': ['A+Attr'],
        'Prop': ['N+Prop+Sg+Loc', 'N+Prop+Sem/Mal+Sg+Loc', 'N+Prop+Sem/Fem+Sg+Loc', 'N+Prop+Sem/Plc+Sg+Loc']
    }

    contelex_inflexType_cases = {
        'V': {
            r'(YD,1)': ['V+Ind+Prs+Sg1', 'V+Ind+Prs+Sg3'],
            r'(AD,1)': ['V+Ind+Prs+Sg1', 'V+Ind+Prt+Sg1'],
            r'(ED,1)': ['V+Ind+Prs+Sg1', 'V+Ind+Prt+Sg1', 'V+Ind+Prt+Sg3'],
            r'(,[2-4])': ['V+Ind+Prs+ConNeg']
        },
        'N': {
            r'(Q[^,\n]*)(,1)': ['N+Sg+Loc', 'N+Sg+Ill', 'N+Pl+Gen'],
            r'(_[^Q,\n]*)(,1)': ['N+Sg+Loc', 'N+Sg+Ill'],
            r'(,3|[^D],2|ID,2)': ['N+Sg+Gen', 'N+Sg+IllN+Sg+Gen', 'N+Sg+Ill'],
            r'(,4|[YAE]D,2)': ['N+Sg+Loc', 'N+Sg+Ill'],
        }
    }

    relations = list(
        sorted(relations, key=lambda r: (r.relationmetadata_set.all().count() != 0, r.lexeme_to.lexeme_lang,))
    )
    for r in relations:
        translation = r.lexeme_to
        pos = '' if translation.pos == lexeme_from.pos else translation.pos

        # LaTeX escape the content
        inflections = []
        MP_forms = translation.miniparadigm_set.all()
        existing_MP_forms = defaultdict(list)
        for form in MP_forms:
            existing_MP_forms[form.msd].append(form.wordform)

        if translation.id not in nti_ids:  # ignore certain translations
            # custom transducer
            generated_MP_forms = defaultdict(list)
            if synthetiser:
                try:
                    queries, _ = _inflector.__generator_queries__(translation.lexeme, translation.pos)
                    for i in range(len(queries)):
                        MP_form = '+'.join(queries[i].split('+')[1:])
                        try:
                            generated_MP_forms[MP_form].append(synthetiser.lookup(queries[i])[0][0].split("@")[0])
                        except:
                            raise
                except:  # POS is empty or no queries
                    pass
            else:  # default (uralicNLP)
                generated_MP_forms = _inflector.generate(translation.language, translation.lexeme, translation.pos)

            if translation.pos in inflection_table:
                inflection_forms = inflection_table[translation.pos]  # default inflections

                # specific inflections based on contlex
                if translation.contlex and translation.pos in contelex_inflexType_cases:
                    for re_pattern, _inflections in contelex_inflexType_cases[translation.pos].items():
                        if re.search(re_pattern, "{},{}".format(translation.contlex, translation.inflexType_str())):
                            inflection_forms = _inflections
                            break

                for inflection_form in inflection_forms:
                    generated_form = None
                    if inflection_form in existing_MP_forms:
                        generated_form = existing_MP_forms[inflection_form]
                    elif inflection_form in generated_MP_forms:
                        generated_form = generated_MP_forms[inflection_form]

                    if generated_form:
                        if inflection_form == 'A+Attr':
                            generated_form = ["#{}".format(gf) for gf in generated_form]
                        elif inflection_form == 'V+Ind+Prs+ConNeg':
                            generated_form[0] = "ij {}".format(generated_form[0])
                        inflections.extend(generated_form)

            if not inflections and translation.pos == 'N' and re.match(r'[A-Z](.+)', translation.lexeme):
                for inflection_form in inflection_table['Prop']:
                    generated_results = uralicApi.generate("{}+{}".format(translation.lexeme, inflection_form),
                                                           translation.language)
                    generated_form = [gr[0].split('@')[0] for gr in generated_results]
                    if generated_form:
                        inflections.extend(generated_form)
                        break

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
                   translation.specification,
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
            "\\translation{%s}{%s}{%s}{%s}{%s}{%s}{%s}{%s}{%s}" % content
        )

    return "\n".join(dictionary_entry_text)


@register.simple_tag(name='dictionary_chapter')
def dictionary_chapter(key):
    return "\includedictionary{%s}{chapter-%s.tex}" % (key, key,)
