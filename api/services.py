from django.db import IntegrityError, transaction

from manageXML.models import (
    Lexeme,
    Relation,
    RelationExample,
    RelationExampleRelation,
)


class AmbiguousLexeme(Exception):
    def __init__(self, role, candidate_ids):
        self.role = role
        super().__init__(
            "Several homonyms match (ids %s); send homoId to choose one."
            % ", ".join(str(i) for i in candidate_ids)
        )


def resolve_lexeme(spec, user, role, default_pos=None):
    """Return (lexeme, created).

    With an explicit homoId the exact homonym is get-or-created. Without one, a single
    existing (lexeme, pos, language) match is reused, none creates homoId 0, and several
    is ambiguous.
    """
    text, language = spec["lexeme"], spec["language"]
    pos = spec.get("pos") or default_pos

    if "homoId" in spec:
        return Lexeme.objects.get_or_create(
            lexeme=text,
            pos=pos,
            language=language,
            homoId=spec["homoId"],
            defaults={"changed_by": user},
        )

    matches = _matching_lexemes(text, pos, language)
    if not matches:
        try:
            with transaction.atomic():  # savepoint: a race must not break the caller's transaction
                return Lexeme.objects.create(
                    lexeme=text, pos=pos, language=language, homoId=0, changed_by=user
                ), True
        except IntegrityError:  # created by a concurrent request in the meantime
            matches = _matching_lexemes(text, pos, language)
    if len(matches) == 1:
        return matches[0], False
    raise AmbiguousLexeme(role, [m.pk for m in matches])


def _matching_lexemes(text, pos, language):
    return list(
        Lexeme.objects.filter(lexeme=text, pos=pos, language=language).order_by("homoId")
    )


def _get_or_create_link(source_example, target_example, user):
    """Return (link, created); a link created concurrently is reused instead of failing."""
    link = RelationExampleRelation.objects.filter(
        example_from=source_example, example_to=target_example
    ).first()
    if link is not None:
        return link, False
    link = RelationExampleRelation(example_from=source_example, example_to=target_example)
    link.changed_by = user
    try:
        with transaction.atomic():
            link.save()
        return link, True
    except IntegrityError:
        return (
            RelationExampleRelation.objects.get(
                example_from=source_example, example_to=target_example
            ),
            False,
        )


def _lexeme_info(lexeme, created):
    return {
        "id": lexeme.pk,
        "created": created,
        "checked": lexeme.checked,
        "web_url": lexeme.get_absolute_url(),
    }


@transaction.atomic
def upsert_pair(user, data):
    """Idempotently store a translation pair with its usage-example pairs.

    Rows that already exist are left untouched, so re-sending a pair never overwrites
    edits or approvals made in Verdd.
    """
    source, source_created = resolve_lexeme(data["source"], user, "source")
    target, target_created = resolve_lexeme(
        data["target"], user, "target", default_pos=source.pos
    )
    relation, relation_created = Relation.objects.get_or_create(
        lexeme_from=source,
        lexeme_to=target,
        type=data["type"],
        defaults={"notes": data.get("notes", ""), "changed_by": user},
    )

    examples = []
    any_created = source_created or target_created or relation_created
    for item in data.get("examples", []):
        provenance = {
            "source": item.get("source", ""),
            "notes": item.get("notes", ""),
            "changed_by": user,
        }
        source_example, created = RelationExample.objects.get_or_create(
            relation=relation,
            language=source.language,
            text=item["source_text"],
            defaults=provenance,
        )
        result = {
            "source_example": source_example.pk,
            "target_example": None,
            "link": None,
        }
        if item.get("target_text"):
            target_example, target_example_created = (
                RelationExample.objects.get_or_create(
                    relation=relation,
                    language=target.language,
                    text=item["target_text"],
                    defaults=provenance,
                )
            )
            link, link_created = _get_or_create_link(source_example, target_example, user)
            created = created or target_example_created or link_created
            result["target_example"] = target_example.pk
            result["link"] = link.pk
        result["created"] = created
        any_created = any_created or created
        examples.append(result)

    return {
        "created": any_created,
        "source": _lexeme_info(source, source_created),
        "target": _lexeme_info(target, target_created),
        "relation": {
            "id": relation.pk,
            "created": relation_created,
            "checked": relation.checked,
        },
        "examples": examples,
    }
