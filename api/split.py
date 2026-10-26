"""Split one lexeme in two: the inverse of a merge.

A new lexeme of the same language is created (by default with the same headword and POS and
the next free homonym number) and the chosen relations and usage examples move onto it. A
relation moves whole, with its sources, metadata and translated examples. Relations that
have a mirror (synonyms, antonyms, ...) move together with it. Forms, stems, metadata and
affiliations stay on the original entry. Both entries are left unapproved so they are
reviewed again. A dry run executes the same code and rolls it back.
"""

from collections import defaultdict

from django.db import transaction
from django.db.models import Max

from manageXML.constants import REVERSE_RELATION_MAPPING
from manageXML.models import Example, Lexeme, Relation

from .merge import lexeme_summary

MAX_LEXEME = 250
MAX_POS = 25


class SplitError(Exception):
    pass


def _stamp(obj, user):
    obj.changed_by = user


def _new_fields(source, new):
    lexeme = (new.get("lexeme") or "").strip() or source.lexeme
    pos = (new.get("pos") or "").strip() or source.pos
    if not pos:
        raise SplitError("The new entry needs a part of speech.")
    if len(lexeme) > MAX_LEXEME:
        raise SplitError("The headword is longer than %d characters." % MAX_LEXEME)
    if len(pos) > MAX_POS:
        raise SplitError("The part of speech is longer than %d characters." % MAX_POS)

    same = Lexeme.objects.filter(lexeme=lexeme, pos=pos, language=source.language)
    if new.get("homoId") is not None:
        homo = new["homoId"]
        clash = same.filter(homoId=homo).first()
        if clash:
            raise SplitError(
                "Entry #%s already is %s (%s) homonym %s; choose another homonym number."
                % (clash.pk, lexeme, pos, homo)
            )
    else:
        highest = same.aggregate(top=Max("homoId"))["top"]
        homo = 0 if highest is None else highest + 1
    return lexeme, pos, homo


def _load(model, ids, owns, label):
    ids = list(dict.fromkeys(ids))
    found = {obj.pk: obj for obj in model.objects.filter(pk__in=ids)}
    for pk in ids:
        if pk not in found:
            raise SplitError("%s #%s does not exist." % (label, pk))
        if not owns(found[pk]):
            raise SplitError("%s #%s does not belong to this entry." % (label, pk))
    return [found[pk] for pk in ids]


def _mirror_of(relation):
    kind = REVERSE_RELATION_MAPPING.get(relation.type)
    if kind is None or relation.lexeme_to_id is None:
        return None
    return Relation.objects.filter(
        lexeme_from_id=relation.lexeme_to_id, lexeme_to_id=relation.lexeme_from_id, type=kind
    ).first()


def _repoint(relation, source, target, user):
    if relation.lexeme_from_id == source.pk:
        relation.lexeme_from = target
    if relation.lexeme_to_id == source.pk:
        relation.lexeme_to = target
    _stamp(relation, user)
    relation.save()


def _move_relation(relation, source, target, user):
    """Repoint a relation; saving a mirrored relation creates its mirror, so the existing
    mirror moves first and the stand-in that creates is removed before the relation follows."""
    mirror = _mirror_of(relation)
    if mirror is not None:
        _repoint(mirror, source, target, user)
        new_from = target if relation.lexeme_from_id == source.pk else relation.lexeme_from
        new_to = target if relation.lexeme_to_id == source.pk else relation.lexeme_to
        stand_ins = Relation.objects.filter(
            lexeme_from=new_from, lexeme_to=new_to, type=relation.type
        ).exclude(pk=relation.pk)
        for stand_in in list(stand_ins):  # the target is new, so only that save can have made one
            _stamp(stand_in, user)
            stand_in.delete()
    _repoint(relation, source, target, user)
    return mirror


def split_lexeme(source, user, new=None, relations=(), examples=(), dry_run=False):
    """Move the given relations and examples of `source` onto a new lexeme; returns a report."""
    new = new or {}
    lexeme, pos, homo = _new_fields(source, new)

    chosen = _load(
        Relation,
        relations,
        lambda r: source.pk in (r.lexeme_from_id, r.lexeme_to_id),
        "Relation",
    )
    chosen_examples = _load(Example, examples, lambda e: e.lexeme_id == source.pk, "Example")
    if not chosen and not chosen_examples:
        raise SplitError("Choose at least one translation, relation or example to move to the new entry.")
    if any(r.lexeme_from_id == r.lexeme_to_id for r in chosen):
        raise SplitError("A relation that links the entry to itself cannot be moved.")

    report = {
        "dry_run": dry_run,
        "moved": defaultdict(int),
        "notes": [],
        "source_unapproved": bool(source.checked),
    }
    with transaction.atomic():
        target = Lexeme(lexeme=lexeme, pos=pos, language=source.language, homoId=homo)
        _stamp(target, user)
        target.save()

        done = set()
        chosen_ids = {r.pk for r in chosen}
        for relation in chosen:
            if relation.pk in done:
                continue
            relation.refresh_from_db()  # an earlier mirror move may have saved it
            mirror = _move_relation(relation, source, target, user)
            done.add(relation.pk)
            report["moved"]["relations"] += 1
            if mirror is not None:
                done.add(mirror.pk)
                report["moved"]["relations" if mirror.pk in chosen_ids else "mirror_relations"] += 1

        for example in chosen_examples:
            example.lexeme = target
            _stamp(example, user)
            example.save()
            report["moved"]["examples"] += 1

        if source.checked:
            source.checked = False
            _stamp(source, user)
            source.save()

        remaining = lexeme_summary(source)
        if remaining["empty"]:
            report["notes"].append("Nothing is left on the original entry.")
        report["source"] = remaining
        report["new"] = lexeme_summary(target)
        if dry_run:
            report["new"]["id"] = None  # rolled back below, so there is no such entry
            transaction.set_rollback(True)
    report["moved"] = dict(report["moved"])
    return report
