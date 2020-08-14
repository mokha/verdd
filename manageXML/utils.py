import os
import csv
from django.db.models import Model, Count, Max


def read_first_ids_from(file_path, delimiter=',', id_in_col=0, cast=int):
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
        with open(file_path, 'r', encoding='utf-8') as fp:
            reader = csv.reader(fp, delimiter=delimiter)
            rows = list(reader)
            rows = [r for r in rows if len(r) > 0]
            ids = [cast(r[id_in_col]) for r in rows]
    return list(set(ids))


def get_duplicate_objects(model: Model, unique_fields=()):
    """
    Finds {model} objects in the database that have identical values of {unique_fields}.

    :param model: Django model.
    :param unique_fields: A tuple containing the name of the unique fields.
    :return Model:
    """
    return model.objects.values(*unique_fields).order_by() \
        .annotate(max_id=Max('id'), count_id=Count('id')).filter(count_id__gt=1)


def obj_to_txt(obj: object, delimiter: str = ',', fields=()):
    """

    :param obj: The object to convert its fields into text.
    :param delimiter: Use to separate/join the fields.
    :param fields: Field names to get from the object.
    :return str: The content of the passed fields of the object, joined by the delimiter.
    """
    return delimiter.join([str(getattr(obj, _f)) for _f in fields])
