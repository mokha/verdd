"""Split one lexeme in two: the inverse of a merge.

A new lexeme of the same language is created (by default with the same headword and POS and
the next free homonym number) and the chosen relations and usage examples move onto it. A
relation moves whole, with its sources, metadata and translated examples. Relations that
have a mirror (synonyms, antonyms, ...) move together with it. Forms, stems, metadata and
affiliations stay on the original entry. Both entries are left unapproved so they are
reviewed again. A dry run executes the same code and rolls it back.

With copy=True nothing moves: the chosen relations (with their sources, metadata, translated
examples and the links between those) and usage examples are duplicated onto the new entry and
the original keeps its own, for the case where both new entries share the same translations,
such as a headword written "gluck(s)en" becoming glucksen and glucken.
"""

from collections import defaultdict

from django.db import transaction
from django.db.models import Max

from manageXML.constants import REVERSE_RELATION_MAPPING
from manageXML.models import (
    Example,
    Lexeme,
    Relation,
    RelationExample,
    RelationExampleRelation,
    RelationMetadata,
    Source,
)

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


def _copy_relation(relation, source, target, user):
    """Duplicate a relation (with what hangs off it) so that `target` stands where `source` stood.
    Saving a mirrored relation creates its mirror, which is returned (or None)."""
    clone = Relation(
        lexeme_from=target if relation.lexeme_from_id == source.pk else relation.lexeme_from,
        lexeme_to=target if relation.lexeme_to_id == source.pk else relation.lexeme_to,
        type=relation.type,
        notes=relation.notes,
        checked=False,
    )
    _stamp(clone, user)
    clone.save()
    for row in relation.source_set.all():
        Source.objects.create(
            relation=clone, name=row.name, page=row.page, type=row.type, notes=row.notes, changed_by=user
        )
    for row in relation.relationmetadata_set.all():
        RelationMetadata.objects.create(
            relation=clone, text=row.text, language=row.language, type=row.type, changed_by=user
        )
    copies = {}
    for row in relation.relationexample_set.all():
        copies[row.pk] = RelationExample.objects.create(
            relation=clone, text=row.text, language=row.language, source=row.source, notes=row.notes, changed_by=user
        )
    for link in RelationExampleRelation.objects.filter(example_from_id__in=copies, example_to_id__in=copies):
        duplicate = RelationExampleRelation(
            example_from=copies[link.example_from_id], example_to=copies[link.example_to_id], notes=link.notes
        )
        _stamp(duplicate, user)
        duplicate.save()
    return clone, _mirror_of(clone)


def split_lexeme(source, user, new=None, relations=(), examples=(), dry_run=False, copy=False):
    """Move (or, with copy=True, duplicate) the given relations and examples of `source` onto a new lexeme; returns a report."""
    new = new or {}
    lexeme, pos, homo = _new_fields(source, new)

    chosen = _load(
        Relation,
        relations,
        lambda r: source.pk in (r.lexeme_from_id, r.lexeme_to_id),
        "Relation",
    )
    chosen_examples = _load(Example, examples, lambda e: e.lexeme_id == source.pk, "Example")
    if not chosen and not chosen_examples and (lexeme, pos) == (source.lexeme, source.pos):
        raise SplitError(
            "Choose at least one translation, relation or example to move to the new entry, "
            "or give it a different headword or part of speech."
        )
    if any(r.lexeme_from_id == r.lexeme_to_id for r in chosen):
        raise SplitError("A relation that links the entry to itself cannot be moved.")

    report = {
        "dry_run": dry_run,
        "moved": defaultdict(int),
        "copied": defaultdict(int),
        "notes": [],
        "source_unapproved": bool(source.checked) and not copy,
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
            if copy:
                _, mirror = _copy_relation(relation, source, target, user)
                done.add(relation.pk)
                report["copied"]["relations"] += 1
                original_mirror = _mirror_of(relation)
                if mirror is not None:
                    report["copied"]["relations" if original_mirror and original_mirror.pk in chosen_ids else "mirror_relations"] += 1
                if original_mirror is not None:
                    done.add(original_mirror.pk)  # its copy was made with the relation's own
                continue
            mirror = _move_relation(relation, source, target, user)
            done.add(relation.pk)
            report["moved"]["relations"] += 1
            if mirror is not None:
                done.add(mirror.pk)
                report["moved"]["relations" if mirror.pk in chosen_ids else "mirror_relations"] += 1

        for example in chosen_examples:
            if copy:
                Example.objects.create(
                    lexeme=target, text=example.text, source=example.source, notes=example.notes, changed_by=user
                )
                report["copied"]["examples"] += 1
                continue
            example.lexeme = target
            _stamp(example, user)
            example.save()
            report["moved"]["examples"] += 1

        if source.checked and not copy:
            source.checked = False
            _stamp(source, user)
            source.save()

        remaining = lexeme_summary(source, user)
        if remaining["empty"]:
            report["notes"].append("Nothing is left on the original entry.")
        report["source"] = remaining
        report["new"] = lexeme_summary(target, user)
        if dry_run:
            report["new"]["id"] = None  # rolled back below, so there is no such entry
            transaction.set_rollback(True)
    report["moved"] = dict(report["moved"])
    report["copied"] = dict(report["copied"])
    return report
