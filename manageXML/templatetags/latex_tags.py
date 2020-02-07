import re
from django import template

register = template.Library()


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
def dictionary_entry(relation):
    '''

    :param relation: a single Relation object
    :return: A latex string to represent the relation as an entry in the dictionary
    '''

    # LaTeX escape the content
    content = (relation.lexeme_from.lexeme, relation.lexeme_to.lexeme, relation.lexeme_to.pos, "",)
    content = (tex_escape(c) for c in content)
    content = tuple(content)

    return "\entry{%s}{%s}{%s}{%s}" % content
