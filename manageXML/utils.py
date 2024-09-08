import os
import csv
import re
from django.db.models import Model, Count, Max, Value
import django.db.models.functions as model_functions
from django.db.models.functions import *
from typing import Dict, Tuple, List, Sequence, Type
from django.db.models.constants import LOOKUP_SEP
from collections import OrderedDict
from manageXML.constants import LEXEME_TYPE
from manageXML.models import Lexeme
from django.core.cache import cache


def get_all_used_languages():
    cache_key = "languages_sorted"
    result = cache.get(cache_key)

    if not result:
        result = (
            Lexeme.objects.values_list("language", flat=True)
            .distinct()
            .order_by(
                "language",
            )
        )
        cache.set(cache_key, result, timeout=3600 * 24)  # Cache for a day

    return result


def get_all_used_pos():
    cache_key = "pos_sorted"
    result = cache.get(cache_key)

    if not result:
        result = (
            Lexeme.objects.values_list("pos", flat=True)
            .distinct()
            .order_by(
                "pos",
            )
        )
        cache.set(cache_key, result, timeout=3600 * 24)  # Cache for a day

    return result


def read_first_ids_from(
    file_path: str, delimiter: str = ",", id_in_col: int = 0, cast=int
):
    """
    A function that loads a CSV file and returns the {id_in_col}th value of each row as {cast} type.

    The function is used to read exported CSV files that have been manually processed to be ignored in certain
    situations (e.g. LaTeX exports).

    :param file_path: Path to the CSV file to read.
    :param delimiter: CSV delimiter (default: ',').
    :param id_in_col: The index where the column contains the ID (default: 0).
    :param cast: What to case
    :return list: A list of values in the specified column casted to the input type.
    """
    ids = []
    if os.path.exists(file_path) and os.path.isfile(file_path):
        with open(file_path, "r", encoding="utf-8") as fp:
            reader = csv.reader(fp, delimiter=delimiter)
            rows = list(reader)
            rows = [r for r in rows if len(r) > 0]
            ids = [cast(r[id_in_col]) for r in rows]
    return list(set(ids))


def annotate_objects(model: Type[Model], annotations: Tuple = ()):
    possible_annotations = dir(model_functions)
    annotation_re = re.compile(r'(\w+)\((\'|")(.+)(\'|")\)', re.I | re.U)
    _annotations = [
        [
            _a[: _a.find("=")],
            _a[_a.find("=") + 1 :],
        ]
        for _a in annotations
        if "=" in _a
    ]

    model_objects = model.objects
    for _a in _annotations:
        matched = annotation_re.match(_a[1])
        if matched and matched.groups()[0] in possible_annotations:
            (
                func_name,
                _,
                _values,
                _,
            ) = matched.groups()
            _values = _values.split("##")
            for _i, _v in enumerate(_values):
                if _i == 0:
                    continue
                _values[_i] = Value(_v)
            _a[1] = getattr(model_functions, func_name)(*_values)
            model_objects = model_objects.annotate(**{_a[0]: _a[1]})
    return model_objects


def get_duplicate_objects(
    model: Type[Model], annotations: Tuple = (), unique_fields: Tuple = ()
):
    """
    Finds {model} objects in the database that have identical values of {unique_fields}.

    :param model: Django model.
    :param annotations: Annotations to apply before finding duplicates.
    :param unique_fields: A tuple containing the name of the unique fields.
    :return Model:
    """
    annotated_objects = annotate_objects(model, annotations)
    return (
        annotated_objects.values(*unique_fields)
        .order_by()
        .annotate(max_id=Max("id"), count_id=Count("id"))
        .filter(count_id__gt=1)
    )


def get_object_attribute(obj, attribute_query: str, separator: str = LOOKUP_SEP):
    """
    Gets an attribute of an object in Django-like fashion (e.g. relation__id)
    :param obj: The object to get the attribute from
    :param attribute_query: the attribute name in Django-like format.
    :param separator: The separator to indicate the recursive query (default is Django's LOOKUP_SEP).
    :return: Value of the attribute, otherwise None.
    """
    _query = attribute_query.split(separator)
    value = getattr(obj, _query.pop(0), None)
    while _query and value:
        value = getattr(value, _query.pop(0), None)
    return value


def obj_to_txt(obj: object, delimiter: str = ",", fields: Tuple = ()):
    """

    :param obj: The object to convert its fields into text.
    :param delimiter: Use to separate/join the fields.
    :param fields: Field names to get from the object.
    :return str: The content of the passed fields of the object, joined by the delimiter.
    """
    return delimiter.join([str(get_object_attribute(obj, _f)) for _f in fields])


def row_to_objects(
    model: Type[Model], row: List[str], fields_length: int = 4, id_in_col: int = 0
):
    """
    Returns a list of :model objects from a parsed row containing N objects, each with :fields_length values.
    :param model: Model type.
    :param row: A CSV parsed row.
    :param fields_length: The number of values representing each object in the row.
    :param id_in_col: Index where ID of objects is in.
    :return: A list of :model objects.
    """
    objects = [row[x : x + fields_length] for x in range(0, len(row), fields_length)]
    objects = [
        model.objects.get(pk=_o[id_in_col])
        for _o in objects
        if len(_o) == fields_length and _o[id_in_col]
    ]
    return objects


def contlex_to_pos(contlex: str):
    """
    Finds the POS from a contlex.
    :param contlex:
    :return: POS and a list
    """
    CONTLEX_MAP = OrderedDict(
        {
            r"_?INTERJ_?": "Interj",
            r"_?PRON_?": "Pron",
            r"_?PROP_?": "Prop",
            r"_?PCLE_?": "Pcle",
            r"_?ADV_?": "Adv",
            r"_?ADP_?": "Adp",
            r"_?NUM_?": "Num",
            r"_?DET_?": "Det",
            r"_?CC_?": "CC",
            r"_?CS_?": "CS",
            r"_?IV_?": "V",
            r"_?BV_?": "V",
            r"_?TV_?": "V",
            r"_?PO_?": "Po",
            r"_?PR_?": "Pr",
            r"_?A_?": "A",
            r"_?N_?": "N",
            r"_?V_?": "V",
        }
    )

    METADATA_MAP = {  # POS, [(METADATA_TYPE, METADATA_TEXT),]
        "Prop": (
            "N",
            [
                (LEXEME_TYPE, "Prop"),
            ],
        ),
    }

    pos = ""
    metadata = []
    for contlex_map in CONTLEX_MAP:
        if re.search(contlex_map, contlex, flags=re.I | re.U):
            pos = CONTLEX_MAP[contlex_map]
            if pos in METADATA_MAP:
                pos, metadata = METADATA_MAP[pos]
            break
    return pos, metadata
