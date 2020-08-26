from django.core.management.base import BaseCommand, CommandError
import io, csv, os
from django.db.models import *
from django.db.models.functions import *
from manageXML.utils import get_duplicate_objects, obj_to_txt
from django.apps import apps
import ast


class Command(BaseCommand):
    """
    This command finds all duplicate items and prints them.

    Usage: python manage.py find_duplicates -m manageXML.Lexeme -d ; --unique lexeme language --fields id lexeme language pos --filters language='fin'

    """

    help = 'This command finds all duplicate items and prints them.'

    def add_arguments(self, parser):
        parser.add_argument('-m', '--model', type=str, help='The model to search for duplicates in. '
                                                            'Format: app.model (e.g. manageXML.Lexeme).', )
        parser.add_argument('-d', '--delimiter', type=str, nargs='?', default=';',
                            help='The delimiter to use when joining fields of duplicate objects.', )
        parser.add_argument('--unique', type=str, nargs='+', help='The unique field names to find duplicates in.')
        parser.add_argument('--fields', type=str, nargs='+', default=('id',), help='Fields to display.')
        parser.add_argument('--filters', type=str, nargs='+', default=tuple(), help='Filters to apply on duplicates.')
        parser.add_argument('-s', '--sort', type=str, nargs='?', default='id',
                            help='Used to sort duplicates.', )

    def handle(self, *args, **options):
        try:
            app_name, model_name = options['model'].split('.')
            delimiter = options['delimiter']
            unique_fields = tuple(options['unique'])
            fields = tuple(options['fields'])
            filters = tuple(options['filters'])
            order_by = options['sort']

            _model = apps.get_model(app_name, model_name)

            duplicates = get_duplicate_objects(model=_model, unique_fields=unique_fields)

            if filters:
                filters = [_f.split('=') for _f in filters if '=' in _f]  # id__gt=1
                for _f in filters:
                    _f[1] = ast.literal_eval(_f[1])
                duplicates = duplicates.filter(**dict(filters))

            output = []
            for dd in duplicates:  # for each duplicate values
                dup_line = []
                d_objects = _model.objects.filter(**{x: dd[x] for x in unique_fields}) # get the objects that have them
                d_objects = d_objects.order_by(order_by)
                for _d in d_objects:
                    dup_line.append(obj_to_txt(_d, fields=fields, delimiter=delimiter))  # convert them to text
                output.append(delimiter.join(dup_line))  # add duplicate line

            self.stdout.write("\n".join(output))  # print final result
        except Exception as e:
            self.stderr.write(self.style.ERROR(str(e)))
