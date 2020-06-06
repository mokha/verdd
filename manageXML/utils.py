import os
import csv


def read_first_ids_from(file_path, delimiter=',', id_in_col=0, cast=int):
    ids = []
    if os.path.exists(file_path) and os.path.isfile(file_path):
        with open(file_path, 'r', encoding='utf-8') as fp:
            reader = csv.reader(fp, delimiter=delimiter)
            rows = list(reader)
            rows = [r for r in rows if len(r) > 0]
            ids = [cast(r[id_in_col]) for r in rows]
    return set(ids)
