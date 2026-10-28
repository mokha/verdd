"""Which languages and language pairs a user may reach through the API.

Access is stored as language pairs (manageXML.LanguageAccess). The pair is unordered: sms and fin
covers sms->fin and fin->sms. A pair of one language twice means that language on its own.
A user with no rows is not limited, and neither is a superuser.

What follows from a pair:
- an entry (lexeme) or its examples: its language is in some allowed pair;
- a relation (translation) and its examples: its two languages form an allowed pair;
- merging or splitting an entry: its language is allowed and every relation it carries is of an
  allowed pair, because the operation moves those relations.
"""

from django.db.models import Q

from manageXML.models import LanguageAccess, Relation


class Scope:
    def __init__(self, pairs=None):
        self.pairs = None if pairs is None else {frozenset(p) for p in pairs}
        self.languages = None if pairs is None else {code for p in self.pairs for code in p}

    @property
    def restricted(self):
        return self.pairs is not None

    def language(self, code):
        return self.pairs is None or code in self.languages

    def pair(self, a, b):
        """Whether a relation between languages a and b (either order) is allowed."""
        if self.pairs is None:
            return True
        return frozenset((a, b)) in self.pairs

    def describe(self):
        if self.pairs is None:
            return {"restricted": False, "pairs": []}
        return {"restricted": True, "pairs": sorted(sorted(p) if len(p) > 1 else [*p, *p] for p in self.pairs)}


def scope_for(user):
    """The Scope of a user, computed once per user object."""
    cached = getattr(user, "_api_scope", None)
    if cached is not None:
        return cached
    if not user or not user.is_authenticated or user.is_superuser:
        scope = Scope()
    else:
        rows = list(LanguageAccess.objects.filter(user=user).values_list("language_a_id", "language_b_id"))
        scope = Scope(rows) if rows else Scope()
    try:
        user._api_scope = scope
    except AttributeError:
        pass
    return scope


def lexeme_q(scope, prefix=""):
    """Filter for rows whose lexeme (reached through `prefix`) is in an allowed language."""
    return Q(**{prefix + "language_id__in": sorted(scope.languages)})


def relation_q(scope, prefix=""):
    """Filter for relations (reached through `prefix`) whose two languages form an allowed pair."""
    q = Q(pk__in=[])
    for pair in scope.pairs:
        a, b = sorted(pair) if len(pair) > 1 else (next(iter(pair)),) * 2
        q |= Q(**{prefix + "lexeme_from__language_id": a, prefix + "lexeme_to__language_id": b})
        q |= Q(**{prefix + "lexeme_from__language_id": b, prefix + "lexeme_to__language_id": a})
    # a relation without a target is judged by its source language
    q |= Q(**{prefix + "lexeme_to__isnull": True, prefix + "lexeme_from__language_id__in": sorted(scope.languages)})
    return q


def relations_outside(scope, lexeme):
    """The relations of a lexeme (either direction) that the scope does not allow."""
    if not scope.restricted:
        return Relation.objects.none()
    mine = Relation.objects.filter(Q(lexeme_from=lexeme) | Q(lexeme_to=lexeme))
    return mine.exclude(relation_q(scope))
