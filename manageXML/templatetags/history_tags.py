from django import template

register = template.Library()


@register.simple_tag(name="history_diff")
def history_diff(record):
    curr_record = record
    prev_record = record.prev_record
    if prev_record:
        delta = curr_record.diff_against(prev_record)
        return [
            c
            for c in delta.changes
            if c.field
            not in [
                "changed_by",
                "assonance",
                "assonance_rev",
                "consonance",
                "consonance_rev",
                "lexeme_lang",
            ]
        ]
    return []
