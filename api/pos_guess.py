"""Guess the POS of an undetermined lexeme from a UralicNLP analyzer.

Only readings whose lemma is exactly the headword count, so inflected forms of another
lemma (Portuguese `casa` is also a form of the verb `casar`) never compete with it. Gender,
number, case and other tags are ignored: only the first tag, the POS, matters.

Giella-style analyses look like `ребёнок+N+Msc+Anim+Sg+Nom`, Apertium-style ones like
`casa<n><f><sg>`. Both are mapped to Verdd's flat POS values.
"""

import re

# Giella tag -> Verdd POS. N+Prop and V+Aux are handled in parse_analysis.
GIELLA_POS = {
    "N": "N", "V": "V", "A": "A", "Adv": "Adv", "Pron": "Pron", "Num": "Num", "Po": "Po",
    "Pr": "Pr", "Pcle": "Pcle", "CC": "CC", "CS": "CS", "Interj": "Interj", "Det": "Det",
}

APERTIUM_POS = {
    "n": "N", "np": "Prop", "vblex": "V", "vbser": "V", "vbhaver": "V", "vbmod": "Aux",
    "vaux": "Aux", "adj": "A", "adv": "Adv", "pr": "Pr", "post": "Po", "prn": "Pron",
    "det": "Det", "num": "Num", "cnjcoo": "CC", "cnjsub": "CS", "cnjadv": "CS", "ij": "Interj",
    "pcle": "Pcle",
}


def parse_analysis(raw):
    """Return (lemma, verdd_pos) for one analysis string; verdd_pos is None for a POS tag
    that has no Verdd counterpart."""
    text = raw.strip().rstrip("ε")
    if "<" in text:
        lemma, _, rest = text.partition("<")
        tags = re.findall(r"<([^<>]*)>", "<" + rest)
        return lemma, APERTIUM_POS.get(tags[0]) if tags else None

    lemma, *tags = text.split("+")
    if not tags:
        return lemma, None
    if tags[0] == "N" and "Prop" in tags:
        return lemma, "Prop"
    if tags[0] == "V" and "Aux" in tags:
        return lemma, "Aux"
    return lemma, GIELLA_POS.get(tags[0])


def headword_pos(headword, analyses):
    """Return (pos_set, has_unmapped) over the readings whose lemma is the headword."""
    found, unmapped = set(), False
    for item in analyses:
        raw = item[0] if isinstance(item, (tuple, list)) else item
        lemma, pos = parse_analysis(raw)
        if lemma != headword:
            continue
        if pos is None:
            unmapped = True
        else:
            found.add(pos)
    return found, unmapped


def classify(found, unmapped):
    """single | ambiguous | unmapped | no reading"""
    if unmapped:
        return "unmapped"
    if not found:
        return "no reading"
    return "single" if len(found) == 1 else "ambiguous"


def models_installed(language):
    from uralicNLP import uralicApi

    return uralicApi.is_language_installed(language)


def analyze_word(word, language):
    from uralicNLP import uralicApi

    return uralicApi.analyze(word, language)
