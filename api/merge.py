"""Join two lexemes of one language into one.

Scope is deliberately narrow. Both lexemes must share their language and have compatible
parts of speech: equal, or at least one undetermined (empty, ZERO or UND). Different
headwords and different determined POS are refused unless the caller confirms them, which
is how a misspelt or decorated headword such as "( ) word", or an entry given the wrong POS,
is folded into the right one; the kept entry's headword and POS win. Everything attached to the
absorbed lexeme moves to the survivor; rows the survivor already has are folded together
instead of duplicated. The survivor keeps its own headword and homonym number, and takes
over the absorbed lexeme's POS when its own is undetermined. A dry run executes the same
code and rolls it back, so the preview is exactly what a real merge would do.
"""

from collections import defaultdict

from django.db import transaction
from django.db.models import Count, Exists, IntegerField, OuterRef, Q, Subquery
from django.db.models.functions import Coalesce

from manageXML.constants import DESC_TRANSLATION, TRANSLATION

from .access import relation_q, scope_for
from manageXML.models import (
    Affiliation,
    Example,
    Lexeme,
    LexemeMetadata,
    MiniParadigm,
    Relation,
    RelationExample,
    RelationExampleRelation,
    RelationMetadata,
    Source,
    Stem,
    StemMetadata,
)

# Exact values, so the database can use the POS index on a table of millions of lexemes.
UNDETERMINED_POS = ("", "ZERO", "UND")

# Every foreign key that points at Lexeme and is handled below. Anything else found on the
# model makes the merge refuse to run rather than cascade-delete data it does not know about.
HANDLED_RELATIONS = {
    ("Relation", "lexeme_from"),
    ("Relation", "lexeme_to"),
    ("Example", "lexeme"),
    ("MiniParadigm", "lexeme"),
    ("Affiliation", "lexeme"),
    ("LexemeMetadata", "lexeme"),
    ("Stem", "lexeme"),
}

COPIED_FIELDS = ("contlex", "type", "specification", "notes", "lemmaId", "inflexId")


class MergeError(Exception):
    pass


def is_undetermined(pos):
    return (pos or "") in UNDETERMINED_POS


def undetermined_q():
    return Q(pos__in=UNDETERMINED_POS)


def siblings_of(lexeme):
    """Same-string, same-language lexemes that have a determined POS."""
    return (
        Lexeme.objects.filter(lexeme=lexeme.lexeme, language=lexeme.language)
        .exclude(undetermined_q())
        .order_by("homoId", "id")
    )


CHILD_LOOKUPS = (
    (Relation, "lexeme_from"),
    (Relation, "lexeme_to"),
    (Example, "lexeme"),
    (LexemeMetadata, "lexeme"),
    (MiniParadigm, "lexeme"),
    (Affiliation, "lexeme"),
    (Stem, "lexeme"),
)


def with_merge_info(queryset):
    """Annotate lexemes in one query with `sibling_count` (same-string, same-language lexemes
    that have a determined POS) and `has_children` (anything attached to the lexeme)."""
    siblings = (
        Lexeme.objects.filter(lexeme=OuterRef("lexeme"), language=OuterRef("language"))
        .exclude(undetermined_q())
        .order_by()
        .values("language")
        .annotate(n=Count("pk"))
        .values("n")
    )
    names = {}
    for index, (model, field) in enumerate(CHILD_LOOKUPS):
        names["has_child_%d" % index] = Exists(model.objects.filter(**{field: OuterRef("pk")}))
    queryset = queryset.annotate(
        sibling_count=Coalesce(Subquery(siblings, output_field=IntegerField()), 0), **names
    )
    has_children = Q(**{"has_child_0": True})
    for name in list(names)[1:]:
        has_children |= Q(**{name: True})
    return queryset, has_children


def merge_candidates_queryset(language=None):
    siblings = Lexeme.objects.filter(
        lexeme=OuterRef("lexeme"), language=OuterRef("language")
    ).exclude(undetermined_q())
    queryset = Lexeme.objects.filter(undetermined_q()).filter(Exists(siblings))
    if language:
        queryset = queryset.filter(language_id=language)
    return queryset.order_by("language_id", "lexeme", "id")


def starts_with_capital(text):
    """True when the first letter of the headword is upper case ("Kala", "(Pietari)")."""
    first = next((char for char in text or "" if char.isalpha()), "")
    return first.isupper()


def capitalised_noun_ids(language):
    """Ids of the noun (POS N) lexemes of one language whose headword begins with a capital,
    in headword order: names written like proper nouns but tagged as common nouns. Whether
    that is wrong depends on the language (weekdays and months are common nouns in many), so
    this always works on one language. Judged in Python, not SQL: SQLite lowercases only
    ASCII and MySQL's collation may ignore case, so the database cannot tell reliably."""
    rows = (
        Lexeme.objects.filter(language_id=language, pos="N")
        .order_by("lexeme", "id")
        .values_list("pk", "lexeme")
    )
    return [pk for pk, text in rows if starts_with_capital(text)]


def counterparts_of(lexeme):
    """Other lexemes of the same language to join a capitalised noun with: the same headword
    written with a lower-case initial or entirely in lower case (kala for Kala), and
    the same headword under another POS (Pietari as Prop beside Pietari as N)."""
    text = lexeme.lexeme
    spellings = {text, text[:1].lower() + text[1:], text.lower()}
    return (
        Lexeme.objects.filter(language=lexeme.language, lexeme__in=spellings)
        .exclude(pk=lexeme.pk)
        .order_by("homoId", "id")
    )


def child_counts(lexeme):
    return {
        "relations_from": lexeme.lexeme_from_lexeme_set.count(),
        "relations_to": lexeme.lexeme_to_lexeme_set.count(),
        "examples": lexeme.example_set.count(),
        "metadata": lexeme.lexememetadata_set.count(),
        "paradigms": lexeme.miniparadigm_set.count(),
        "affiliations": lexeme.affiliation_set.count(),
        "stems": lexeme.stem_set.count(),
    }


def lexeme_summary(lexeme, user=None):
    """The lexeme with its attachments counted and a few of its translations. For a user limited
    to some language pairs the translations shown are only those of the pairs they may see."""
    counts = child_counts(lexeme)
    scope = scope_for(user)
    translations = lexeme.lexeme_from_lexeme_set.filter(type__in=[TRANSLATION, DESC_TRANSLATION])
    if scope.restricted:
        translations = translations.filter(relation_q(scope))
    translations = translations.select_related("lexeme_to").order_by("id")[:5]
    return {
        "id": lexeme.pk,
        "lexeme": lexeme.lexeme,
        "language": lexeme.language_id,
        "pos": lexeme.pos,
        "homoId": lexeme.homoId,
        "checked": lexeme.checked,
        "counts": counts,
        "empty": not any(counts.values()),
        "translations": [r.lexeme_to.lexeme for r in translations if r.lexeme_to_id],
    }


def _validate(absorbed, keeper, allow_different_headword=False, allow_different_pos=False):
    if absorbed.pk == keeper.pk:
        raise MergeError("A lexeme cannot be merged into itself.")
    if absorbed.language_id != keeper.language_id:
        raise MergeError("Only lexemes of the same language can be merged.")
    if absorbed.lexeme != keeper.lexeme and not allow_different_headword:
        raise MergeError(
            "Only lexemes with the same headword can be merged unless you confirm that the "
            "headwords differ ('%s' and '%s')." % (absorbed.lexeme, keeper.lexeme)
        )
    if differing_pos(absorbed, keeper) and not allow_different_pos:
        raise MergeError(
            "The entries have different parts of speech (%s and %s), so they may be different "
            "entries. Confirm that the absorbed entry has the wrong POS to merge them anyway."
            % (absorbed.pos, keeper.pos)
        )
    if adopted_pos(absorbed, keeper):
        clash = (
            Lexeme.objects.filter(
                lexeme=keeper.lexeme,
                language=keeper.language,
                pos=absorbed.pos,
                homoId=keeper.homoId,
            )
            .exclude(pk__in=[absorbed.pk, keeper.pk])
            .first()
        )
        if clash:
            raise MergeError(
                "The kept entry would become %s homonym %s, which entry #%s already is."
                % (absorbed.pos, keeper.homoId, clash.pk)
            )

    found = {(r.related_model.__name__, r.field.name) for r in Lexeme._meta.related_objects}
    unknown = found - HANDLED_RELATIONS
    if unknown:
        raise MergeError(
            "Merging is not available: lexemes are also referenced by %s."
            % ", ".join("%s.%s" % pair for pair in sorted(unknown))
        )


def differing_pos(absorbed, keeper):
    """True when both entries have a real POS and it is not the same."""
    return (
        not is_undetermined(absorbed.pos)
        and not is_undetermined(keeper.pos)
        and absorbed.pos != keeper.pos
    )


def adopted_pos(absorbed, keeper):
    """The POS the keeper takes over, or None: only when it has none and the absorbed one does."""
    if is_undetermined(keeper.pos) and not is_undetermined(absorbed.pos):
        return absorbed.pos
    return None


def _stamp(obj, user):
    obj.changed_by = user


def _adopt(children, keeper, user, label, key, report, on_twin=None):
    """Move each child to the keeper unless the keeper already has an equal one."""
    for child in list(children):
        twin = type(child).objects.filter(lexeme=keeper, **key(child)).first()
        _stamp(child, user)
        if twin is None:
            child.lexeme = keeper
            child.save()
            report["moved"][label] += 1
        else:
            if on_twin:
                on_twin(child, twin)
            child.delete()
            report["deduplicated"][label] += 1


def _fold_stem(stem, twin, user, report):
    for meta in list(stem.stemmetadata_set.all()):
        _stamp(meta, user)
        if StemMetadata.objects.filter(stem=twin, type=meta.type, text=meta.text).exists():
            meta.delete()
            report["deduplicated"]["stem_metadata"] += 1
        else:
            meta.stem = twin
            meta.save()
            report["moved"]["stem_metadata"] += 1


def _repoint_links(example, survivor, user):
    """After `example` is folded into `survivor`, keep the pairs that linked it."""
    for link in list(RelationExampleRelation.objects.filter(Q(example_from=example) | Q(example_to=example))):
        a = survivor if link.example_from_id == example.pk else link.example_from
        b = survivor if link.example_to_id == example.pk else link.example_to
        if a.pk == b.pk or RelationExampleRelation.objects.filter(example_from=a, example_to=b).exclude(pk=link.pk).exists():
            link.delete()
        else:
            link.example_from, link.example_to = a, b
            _stamp(link, user)
            link.save()


def _fold_relation(relation, twin, user, report):
    """Move what hangs off a duplicate relation onto the relation that stays."""
    for source in list(relation.source_set.all()):
        _stamp(source, user)
        if Source.objects.filter(relation=twin, name=source.name).exists():
            source.delete()
        else:
            source.relation = twin
            source.save()

    for meta in list(relation.relationmetadata_set.all()):
        _stamp(meta, user)
        if RelationMetadata.objects.filter(relation=twin, language=meta.language, type=meta.type, text=meta.text).exists():
            meta.delete()
        else:
            meta.relation = twin
            meta.save()

    for example in list(relation.relationexample_set.all()):
        _stamp(example, user)
        survivor = RelationExample.objects.filter(relation=twin, language=example.language, text=example.text).first()
        if survivor is None:
            example.relation = twin
            example.save()
            report["moved"]["relation_examples"] += 1
        else:
            _repoint_links(example, survivor, user)
            example.delete()
            report["deduplicated"]["relation_examples"] += 1


def _merge_relations(absorbed, keeper, user, report):
    ids = list(
        Relation.objects.filter(Q(lexeme_from=absorbed) | Q(lexeme_to=absorbed))
        .order_by("id")
        .values_list("id", flat=True)
    )
    for pk in ids:
        # Saving a symmetric relation can create or fold its mirror, so re-read each row.
        relation = Relation.objects.filter(pk=pk).first()
        if relation is None:
            continue
        new_from = keeper if relation.lexeme_from_id == absorbed.pk else relation.lexeme_from
        new_to = keeper if relation.lexeme_to_id == absorbed.pk else relation.lexeme_to
        _stamp(relation, user)

        if new_to is not None and new_from.pk == new_to.pk:
            relation.delete()
            report["dropped"]["relations_between_the_two"] += 1
            continue

        twin = (
            Relation.objects.filter(lexeme_from=new_from, lexeme_to=new_to, type=relation.type)
            .exclude(pk=relation.pk)
            .first()
        )
        if twin is None:
            relation.lexeme_from, relation.lexeme_to = new_from, new_to
            relation.save()
            report["moved"]["relations"] += 1
        else:
            _fold_relation(relation, twin, user, report)
            relation.delete()
            report["deduplicated"]["relations"] += 1


def _copy_blank_fields(absorbed, keeper, report):
    for field in COPIED_FIELDS:
        theirs, ours = getattr(absorbed, field), getattr(keeper, field)
        if theirs and not ours:
            setattr(keeper, field, theirs)
            report["fields_copied"].append(field)
        elif theirs and ours and theirs != ours:
            report["notes"].append("%s: kept '%s', the absorbed entry had '%s'." % (field, ours, theirs))


def _run(absorbed, keeper, user, report):
    _adopt(absorbed.example_set.all(), keeper, user, "examples", lambda c: {"text": c.text}, report)
    _adopt(absorbed.lexememetadata_set.all(), keeper, user, "metadata", lambda c: {"type": c.type, "text": c.text}, report)
    _adopt(absorbed.miniparadigm_set.all(), keeper, user, "paradigms", lambda c: {"msd": c.msd, "wordform": c.wordform}, report)
    _adopt(
        absorbed.affiliation_set.all(), keeper, user, "affiliations",
        lambda c: {"title": c.title, "link": c.link, "type": c.type}, report,
    )
    _adopt(
        absorbed.stem_set.all(), keeper, user, "stems",
        lambda c: {"text": c.text, "contlex": c.contlex}, report,
        on_twin=lambda stem, twin: _fold_stem(stem, twin, user, report),
    )
    _merge_relations(absorbed, keeper, user, report)

    leftovers = {name: count for name, count in child_counts(absorbed).items() if count}
    if leftovers:
        raise MergeError("Could not move everything (%s); nothing was changed." % leftovers)

    _copy_blank_fields(absorbed, keeper, report)
    changed = bool(report["fields_copied"])
    new_pos = adopted_pos(absorbed, keeper)
    if absorbed.lexeme != keeper.lexeme:
        report["headword_dropped"] = absorbed.lexeme
    if differing_pos(absorbed, keeper):
        report["pos_dropped"] = absorbed.pos
    if new_pos:
        keeper.pos = new_pos
        report["pos_set"] = new_pos
        changed = True
    if (sum(report["moved"].values()) or new_pos) and keeper.checked:
        keeper.checked = False
        report["keeper_unapproved"] = True
        changed = True

    # The absorbed lexeme goes first: the keeper may take over its POS, and the two would
    # otherwise collide on (headword, POS, language, homonym).
    _stamp(absorbed, user)
    absorbed.delete()
    if changed:
        _stamp(keeper, user)
        keeper.save()


def merge_lexemes(
    absorbed, keeper, user, dry_run=False, allow_different_headword=False, allow_different_pos=False
):
    """Absorb `absorbed` into `keeper`; returns a report of what moved, folded or was dropped."""
    _validate(absorbed, keeper, allow_different_headword, allow_different_pos)
    report = {
        "dry_run": dry_run,
        "absorbed": lexeme_summary(absorbed, user),
        "into": lexeme_summary(keeper, user),
        "moved": defaultdict(int),
        "deduplicated": defaultdict(int),
        "dropped": defaultdict(int),
        "fields_copied": [],
        "notes": [],
        "keeper_unapproved": False,
        "headword_dropped": None,
        "pos_dropped": None,
        "pos_set": None,
    }
    with transaction.atomic():
        _run(absorbed, keeper, user, report)
        if dry_run:
            transaction.set_rollback(True)
    for name in ("moved", "deduplicated", "dropped"):
        report[name] = dict(report[name])
    return report
